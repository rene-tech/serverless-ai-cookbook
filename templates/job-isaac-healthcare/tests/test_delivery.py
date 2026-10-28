"""Request-byte preservation and explicit replay construction, without simulation."""

import io
import json
import os
import tarfile
from contextlib import contextmanager
from pathlib import Path

import h5py
import numpy as np
import pytest

from isaac_healthcare_runtime import runtime
from isaac_healthcare_runtime.audit import validate_delivery
from isaac_healthcare_runtime.contract import digest
from isaac_healthcare_runtime.validate import validate_hdf_closure, validate_recording


pytestmark = pytest.mark.skipif(
    not Path('/opt/i4h/arena/.venv/bin/python').exists(), reason='requires installed pinned Arena CPU environment')


def test_actual_inspect_preserves_exact_scenarios_for_input_absent_audit(tmp_path):
    original = tmp_path / 'renamed-input.json'
    raw = b'{ "schema":"isaac-healthcare-scenarios/v2",\n "scenarios":[{"name":"new label","seed":null}] }\n'
    original.write_bytes(raw)
    result = runtime.run(original, {}, tmp_path / 'output', operation='inspect')
    with tarfile.open(tmp_path / 'output/simulation.tar') as archive:
        assert archive.extractfile('request/scenarios.json').read() == raw
    identity = {'input_sha256': digest(original), 'project_sha256': None}
    original.unlink()
    checked = validate_delivery(
        operation='inspect', input_path=None, project_path=None, parameter_values={},
        result_path=tmp_path / 'output/result.json', archive_path=tmp_path / 'output/simulation.tar',
        input_identity=identity)
    assert checked['validation'] == 'passed'
    assert checked['input_sha256'] == result['input_sha256']


def test_explicit_replay_overrides_only_project_default_and_uses_actual_pinned_inspection(tmp_path, monkeypatch):
    from test_replay import recording

    dataset = tmp_path / 'recorded.hdf5'
    recording(dataset)
    project = tmp_path / 'project.tar'
    content = {
        'project.json': json.dumps({'schema': 'isaac-healthcare-project/v2',
                                   'default_workflow': 'scissor_pick_and_place',
                                   'default_mode': 'idle'}).encode(),
        'data/recorded.hdf5': dataset.read_bytes(),
    }
    with tarfile.open(project, 'w') as archive:
        for name, payload in content.items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    original_execute = runtime.execute
    calls = []

    class StopBeforeSimulation(Exception):
        pass

    def execute(argv, directory, **kwargs):
        calls.append(argv)
        if 'isaac_healthcare_runtime.inspection' in argv:
            return original_execute(argv, directory, **kwargs)
        assert argv[argv.index('--mode') + 1] == 'replay'
        assert argv[argv.index('--episode') + 1] == '1'
        selected = json.loads((directory.parent / 'inspection/registry.json').read_bytes())['selected']
        assert selected['mode'] == 'replay' and selected['lint']['ok']
        raise StopBeforeSimulation()

    monkeypatch.setenv('ACCEPT_EULA', 'Y')
    monkeypatch.setattr(runtime, 'execute', execute)
    values = {'dataset': 'data/recorded.hdf5', 'replay_episodes': [1, 0]}
    with pytest.raises(StopBeforeSimulation):
        runtime.run(None, values, tmp_path / 'replay', operation='replay', project_path=project)
    assert len(calls) == 2
    with pytest.raises(ValueError, match='requires the authored replay mode'):
        runtime.run(None, {**values, 'mode': 'idle'}, tmp_path / 'conflict',
                    operation='replay', project_path=project)
    assert len(calls) == 2


@contextmanager
def watch_canary(path):
    """Observe kernel opens/reads of an owned canary, without opening its data."""
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    descriptor = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    assert descriptor >= 0
    try:
        result = libc.inotify_add_watch(descriptor, os.fsencode(path), 0x20 | 0x1)  # IN_OPEN | IN_ACCESS
        assert result >= 0
        events = []
        yield events
        try:
            events.append(os.read(descriptor, 65536))
        except BlockingIOError:
            pass
    finally:
        os.close(descriptor)


def test_canary_observer_detects_a_real_open_and_read(tmp_path):
    canary = tmp_path / 'owned-canary'
    canary.write_bytes(b'only synthetic test data')
    with watch_canary(canary) as events:
        assert canary.read_bytes() == b'only synthetic test data'
    assert events and events[0]


@pytest.mark.parametrize('kind', ['external-link', 'indirect-external-link', 'external-raw', 'external-vds'])
def test_unbound_hdf_sources_fail_before_any_attribute_or_data_read(tmp_path, monkeypatch, kind):
    from test_runtime import recording, selected
    from isaac_healthcare_runtime.contract import parameters

    path, canary = tmp_path / 'recording.hdf5', tmp_path / 'owned-canary.h5'
    recording(path)
    if kind == 'external-raw':
        canary.write_bytes(np.arange(21, dtype=np.float32).tobytes())
    else:
        with h5py.File(canary, 'w') as secret:
            secret.create_dataset('owned_test_data', data=np.arange(21, dtype=np.float32).reshape(3, 7))
    with h5py.File(path, 'a') as source:
        demo = source['data/demo_0']
        del demo['actions']
        if kind == 'external-link':
            demo['actions'] = h5py.ExternalLink(str(canary), '/owned_test_data')
        elif kind == 'indirect-external-link':
            source['external-source'] = h5py.ExternalLink(str(canary), '/owned_test_data')
            demo['actions'] = h5py.SoftLink('/external-source')
        elif kind == 'external-raw':
            demo.create_dataset('actions', shape=(3, 7), dtype=np.float32,
                                external=[(str(canary), 0, 21 * 4)])
        else:
            layout = h5py.VirtualLayout(shape=(3, 7), dtype=np.float32)
            layout[:] = h5py.VirtualSource(str(canary), '/owned_test_data', shape=(3, 7))
            demo.create_virtual_dataset('actions', layout)

    def forbidden(*_args, **_kwargs):
        pytest.fail('Recording values or attributes were read before closure validation')

    monkeypatch.setattr(h5py.Dataset, '__getitem__', forbidden)
    monkeypatch.setattr(h5py.AttributeManager, '__getitem__', forbidden)
    with watch_canary(canary) as events:
        with pytest.raises(ValueError, match='external'):
            validate_recording(path, parameters({}), scene=selected())
    assert not events, 'The HDF5 library opened or read the external canary'


@pytest.mark.parametrize('virtual', [False, True])
def test_internal_links_hard_cycles_and_same_file_virtual_data_remain_valid(tmp_path, virtual):
    from test_runtime import recording, selected
    from isaac_healthcare_runtime.contract import parameters

    path = tmp_path / 'recording.hdf5'
    recording(path)
    with h5py.File(path, 'a') as source:
        meta = source.create_group('metadata')
        meta['source_actions'] = source['data/demo_0/actions']
        meta['same_object'] = meta['source_actions']
        meta['self'] = meta
        meta['parent'] = source
        meta['relative'] = h5py.SoftLink('./source_actions')
        meta['root'] = h5py.SoftLink('/')
        meta['root_twice'] = h5py.SoftLink('/metadata/root/metadata/root')
        # '..' is an ordinary HDF5 link name, not filesystem parent traversal.
        meta['..'] = meta['source_actions']
        meta['ordinary_dotdot_name'] = h5py.SoftLink('..')
        del source['data/demo_0/actions']
        if virtual:
            layout = h5py.VirtualLayout(shape=(3, 7), dtype=np.float32)
            layout[:] = h5py.VirtualSource('.', '/metadata/relative', shape=(3, 7))
            source['data/demo_0'].create_virtual_dataset('actions', layout)
        else:
            source['data/demo_0/actions'] = h5py.SoftLink('/metadata/relative')
    with h5py.File(path, 'r') as source:
        closure = validate_hdf_closure(source)
        assert closure['soft_links'] == (4 if virtual else 5)
        assert closure['virtual_datasets'] == int(virtual)
    validated = validate_recording(path, parameters({}), scene=selected())
    assert validated['samples'] == 3
    assert validated['episodes'][0]['shapes']['actions'] == [3, 7]


@pytest.mark.parametrize('kind', ['soft-cycle', 'dangling-soft', 'vds-cycle', 'vds-nondataset'])
def test_unresolved_or_recursive_dependencies_fail_before_values(tmp_path, monkeypatch, kind):
    from test_runtime import recording, selected
    from isaac_healthcare_runtime.contract import parameters

    path = tmp_path / 'recording.hdf5'
    recording(path)
    with h5py.File(path, 'a') as source:
        if kind == 'soft-cycle':
            source['cycle-a'] = h5py.SoftLink('/cycle-b')
            source['cycle-b'] = h5py.SoftLink('/cycle-a')
        elif kind == 'dangling-soft':
            source['dangling'] = h5py.SoftLink('/absent-object')
        else:
            layout = h5py.VirtualLayout(shape=(3, 7), dtype=np.float32)
            layout[:] = h5py.VirtualSource('.', '/vds-b' if kind == 'vds-cycle' else '/data', shape=(3, 7))
            source.create_virtual_dataset('vds-a', layout)
            if kind == 'vds-cycle':
                second = h5py.VirtualLayout(shape=(3, 7), dtype=np.float32)
                second[:] = h5py.VirtualSource('.', '/vds-a', shape=(3, 7))
                source.create_virtual_dataset('vds-b', second)

    def forbidden(*_args, **_kwargs):
        pytest.fail('Recording values or attributes were read before closure validation')

    monkeypatch.setattr(h5py.Dataset, '__getitem__', forbidden)
    monkeypatch.setattr(h5py.AttributeManager, '__getitem__', forbidden)
    with pytest.raises(ValueError, match='cyclic|dangling|not a dataset'):
        validate_recording(path, parameters({}), scene=selected())


def test_metadata_walk_is_finite_without_a_recursive_depth_limit(tmp_path):
    path = tmp_path / 'recording.hdf5'
    with h5py.File(path, 'w') as source:
        source.create_dataset('terminal', data=[1])
        source['hard-self'] = source
        for index in range(1500):
            target = f'/link-{index + 1}' if index < 1499 else '/terminal'
            source[f'link-{index}'] = h5py.SoftLink(target)
    with h5py.File(path, 'r') as source:
        assert validate_hdf_closure(source) == {'objects': 2, 'soft_links': 1500, 'virtual_datasets': 0}
