"""CPU contract tests; these do not establish simulator or trainer qualification."""

import io
import json
import tarfile
from pathlib import Path

import h5py
import numpy as np
import pytest

from isaac_healthcare_runtime.contract import json_loads, parameters, scenarios
from isaac_healthcare_runtime.project import extract_project, prepare_project
from isaac_healthcare_runtime.runtime import command, run
from isaac_healthcare_runtime.audit import validate_delivery
from isaac_healthcare_runtime.validate import validate_recording


def project_archive(path, *, name='unseen_probe', mode='measure', cap=1700, extra_files=None):
    files = {
        'project.json': json.dumps({'schema': 'isaac-healthcare-project/v2', 'default_workflow': name, 'default_mode': mode}),
        f'overlay/workflows/i4h_workflows/customer_authored/{name}.py': (
            'from i4h_engine.interface import Workflow\n'
            'from i4h_engine.graph import TaskGraph, node\n'
            'from i4h_tasks.basic.control.wait import Wait\n'
            'def authored(duration=0.5):\n'
            '    return TaskGraph().flow(node(Wait(duration)))\n'
            f'WORKFLOW=Workflow(scene="custom_probe", modes={{"{mode}": authored}}, default_mode="{mode}")\n'),
        'overlay/arena/i4h_arena/scenes/manifest/custom_probe.yaml': (
            'impl: custom_scene:Scene\nembodiment: laboratory_probe\naction_space: ee_pose\n'
            f'dof: 11\ncameras: [depth_left, infrared]\nmax_steps: {cap}\ncontrol_hz: 25.0\n'),
        'data/arbitrary-name.dat': 'not used by the CPU discovery test',
    }
    files.update(extra_files or {})
    with tarfile.open(path, 'w') as archive:
        for name, content in files.items():
            data = content.encode()
            item = tarfile.TarInfo(name)
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
    return path


def recording(path, *, success=False, cameras=True, workflow='unseen_probe', mode='measure', joints=11):
    with h5py.File(path, 'w') as f:
        data = f.create_group('data')
        data.attrs.update(workflow=workflow, mode=mode, scene='custom_probe')
        demo = data.create_group('demo_0')
        demo.attrs.update(num_samples=3, recording_version=1, success=success,
                          status='succeeded' if success else 'timed_out')
        demo.create_dataset('actions', data=np.ones((3, 7), dtype=np.float32))
        demo.create_dataset('obs/joint_pos', data=np.ones((3, joints), dtype=np.float32))
        demo.create_dataset('initial_state/robot/joint_pos', data=np.ones((1, joints)))
        dtype = np.dtype([('start', '<i8'), ('end', '<i8')])
        demo.create_dataset('segments', data=np.array([(0, 3)], dtype=dtype))
        demo.create_dataset('diagnostics/distance', data=np.array([np.nan, 0.5, 0.1]))
        if cameras:
            demo.create_dataset('obs/infrared', data=np.arange(3 * 5 * 7 * 3, dtype=np.uint8).reshape(3, 5, 7, 3))
            demo.create_dataset('obs/depth_left', data=np.ones((3, 12, 16), dtype=np.float32))


def selected():
    return {'workflow': 'unseen_probe', 'mode': 'measure', 'scene': 'custom_probe',
            'episode_step_cap': 1700, 'cameras': ['depth_left', 'infrared'],
            'declared_cameras': ['depth_left', 'infrared']}


def test_general_controls_preserve_explicit_values_and_no_global_cap(tmp_path):
    values = parameters({'workflow': 'novel_workflow', 'mode': 'custom_mode', 'envs': 3,
                         'episodes': 2, 'attempts': 3, 'episode_steps': 1700, 'physics': 'newton',
                         'cameras': False, 'workflow_args': {'duration': 2.3}})
    row = scenarios({'schema': 'isaac-healthcare-scenarios/v2', 'scenarios': [{'name': '../../label', 'seed': 1987}]})[0]
    argv = command(values, row, tmp_path)
    assert row['name'] not in argv
    for flag, expected in [('--workflow', 'novel_workflow'), ('--mode', 'custom_mode'), ('--envs', '3'),
                           ('--episode-steps', '1700'), ('--presets', 'newton'), ('--seed', '1987')]:
        assert argv[argv.index(flag) + 1] == expected
    assert '--no-cameras' in argv
    defaults = command(parameters({'workflow': 'x'}), {'name': 'new', 'seed': None}, tmp_path)
    assert '--episode-steps' not in defaults and '--presets' not in defaults and '--mode' not in defaults


@pytest.mark.parametrize('value', [{'episode_steps': 0}, {'episodes': True}, {'episodes': 0},
                                    {'envs': 0}, {'physics': 'imaginary'}, {'hidden_tuning': True}])
def test_invalid_controls_fail(value):
    with pytest.raises(ValueError, match='Invalid'):
        parameters(value)


def test_duplicate_json_and_scenarios_fail_closed():
    with pytest.raises(ValueError, match='Duplicate'):
        json_loads('{"workflow":"first","workflow":"second"}')
    with pytest.raises(ValueError, match='unique'):
        scenarios({'schema': 'isaac-healthcare-scenarios/v2', 'scenarios': [{'name': 'same'}, {'name': 'same'}]})


def test_explicit_null_seed_preserves_random_reset_while_omission_uses_request_default(tmp_path):
    values = parameters({'workflow': 'w', 'seed': 2915})
    rows = scenarios({'schema': 'isaac-healthcare-scenarios/v2', 'scenarios': [{'name': 'a'}, {'name': 'b', 'seed': None}]}, values['seed'])
    assert rows[0]['seed'] == 2915 and rows[1]['seed'] is None
    assert '--seed' in command(values, rows[0], tmp_path)
    assert '--seed' not in command(values, rows[1], tmp_path)


@pytest.mark.parametrize('kind,name', [('file', '../escape'), ('file', '/absolute'), ('symlink', 'data/link'),
                                      ('hardlink', 'data/hard'), ('fifo', 'fifo'), ('duplicate', 'data/value')])
def test_archive_paths_links_specials_and_duplicates_rejected(tmp_path, kind, name):
    archive_path = tmp_path / 'project.tar'
    with tarfile.open(archive_path, 'w') as archive:
        item = tarfile.TarInfo(name)
        item.size = 1
        if kind == 'symlink':
            item.type, item.linkname = tarfile.SYMTYPE, '/etc/passwd'
        elif kind == 'hardlink':
            item.type, item.linkname = tarfile.LNKTYPE, '../escape'
        elif kind == 'fifo':
            item.type = tarfile.FIFOTYPE
        archive.addfile(item, io.BytesIO(b'x') if item.isfile() else None)
        if kind == 'duplicate':
            archive.addfile(item, io.BytesIO(b'y'))
    with pytest.raises(ValueError):
        extract_project(archive_path, tmp_path / 'project')
    assert not (tmp_path / 'escape').exists()


def test_copy_on_write_overlay_preserves_base(tmp_path):
    base = tmp_path / 'base'
    (base / 'common').mkdir(parents=True)
    (base / 'engine').mkdir()
    (base / 'DESIGN.md').write_text('base')
    (base / 'common/kept.py').write_text('original')
    project = project_archive(tmp_path / 'project.tar')
    context = prepare_project(project, tmp_path / 'work', base)
    assert (Path(context['effective_root']) / 'common/kept.py').read_text() == 'original'
    assert (base / 'common/kept.py').read_text() == 'original'
    assert not (base / 'arena').exists()
    assert context['manifest']['default_workflow'] == 'unseen_probe'
    assert context['inventory']['data/arbitrary-name.dat']['size_bytes'] > 0


def test_dynamic_sensor_action_shapes_timeout_and_missing_diagnostics(tmp_path):
    path = tmp_path / 'recording.hdf5'
    recording(path)
    report = validate_recording(path, parameters({'workflow': 'unseen_probe', 'mode': 'measure'}),
                                tmp_path / 'previews', scene=selected())
    assert report['task_complete'] is False
    assert report['episodes'][0]['status'] == 'timed_out'
    assert report['episodes'][0]['shapes']['actions'] == [3, 7]
    assert report['episodes'][0]['shapes']['obs/joint_pos'] == [3, 11]
    assert report['episodes'][0]['cameras']['depth_left']['shape'] == [12, 16]
    assert report['episodes'][0]['diagnostics']['distance']['nonfinite_values'] == 1
    assert len(list((tmp_path / 'previews').glob('*.png'))) == 3


def test_nonfinite_action_missing_sensor_and_stale_boundary_rejected(tmp_path):
    path = tmp_path / 'recording.hdf5'
    values = parameters({'workflow': 'unseen_probe', 'mode': 'measure'})
    recording(path)
    with h5py.File(path, 'a') as f:
        f['data/demo_0/actions'][1, 0] = np.nan
    with pytest.raises(ValueError, match='nonfinite'):
        validate_recording(path, values, scene=selected())
    recording(path, cameras=False)
    with pytest.raises(ValueError, match='omits declared'):
        validate_recording(path, values, scene=selected())
    recording(path)
    with h5py.File(path, 'a') as f:
        f['data/demo_0'].attrs['recording_version'] = 0
    with pytest.raises(ValueError, match='reset'):
        validate_recording(path, values, scene=selected())


def test_camera_disable_and_explicit_scene_cap(tmp_path):
    path = tmp_path / 'recording.hdf5'
    values = parameters({'workflow': 'unseen_probe', 'mode': 'measure', 'cameras': False})
    recording(path, cameras=False)
    scene = {**selected(), 'cameras': []}
    assert validate_recording(path, values, scene=scene)['episodes'][0]['cameras'] == {}
    recording(path)
    with pytest.raises(ValueError, match='cameras were disabled'):
        validate_recording(path, values, scene=scene)
    recording(path, cameras=False)
    with pytest.raises(ValueError, match='scene cap'):
        validate_recording(path, {**values, 'episode_steps': 2}, scene=scene)


def test_integer_equivalent_cli_and_empty_input_guard(tmp_path):
    values = parameters({'workflow': 'unknown', 'episodes': 1.0, 'envs': 2.0, 'episode_steps': 701.0})
    argv = command(values, {'name': 'a', 'seed': 17}, tmp_path)
    for flag in ('--episodes', '--envs', '--episode-steps', '--seed'):
        assert str(int(argv[argv.index(flag) + 1])) == argv[argv.index(flag) + 1]
    with pytest.raises(ValueError, match='Provide scenarios'):
        run(None, {}, tmp_path / 'out', operation='simulate')


@pytest.mark.skipif(not Path('/opt/i4h/arena/.venv/bin/python').exists(), reason='requires pinned installed Arena CPU environment')
@pytest.mark.parametrize('name,mode,cap', [('unseen_probe', 'measure', 1700), ('different_name', 'calibrate', 9100)])
def test_actual_project_registry_lint_and_authored_limits(tmp_path, name, mode, cap):
    archive = project_archive(tmp_path / 'project.tar', name=name, mode=mode, cap=cap)
    report = run(None, {'episode_steps': cap, 'workflow_args': {'duration': 0.75}},
                 tmp_path / 'output', operation='lint', project_path=archive)
    resolved = report['capabilities']['registry']['selected']
    assert resolved['workflow'] == name and resolved['mode'] == mode
    assert resolved['scene_step_cap'] == cap and resolved['dof'] == 11
    assert resolved['cameras'] == ['depth_left', 'infrared']
    assert resolved['lint']['ok'] and report['task_complete'] is None
    assert report['scientific_validation'] == 'not_applicable'
    with pytest.raises(RuntimeError, match='discovery failed'):
        run(None, {'episode_steps': cap + 1}, tmp_path / 'over-cap', operation='lint', project_path=archive)
    with tarfile.open(tmp_path / 'output/simulation.tar') as result:
        assert 'inspection/registry.json' in result.getnames()
        assert not any('.runtime' in name or '.operator' in name for name in result.getnames())
    audited = validate_delivery(operation='lint', input_path=None, project_path=archive,
                                parameter_values={'episode_steps': cap, 'workflow_args': {'duration': 0.75}},
                                result_path=tmp_path / 'output/result.json', archive_path=tmp_path / 'output/simulation.tar')
    assert audited['validation'] == 'passed' and audited['task_complete'] is None
    report['provenance']['artifact_files']['inspection/registry.json']['sha256'] = '0' * 64
    bad = tmp_path / 'bad-result.json'
    bad.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='inventory'):
        validate_delivery(operation='lint', input_path=None, project_path=archive,
                          parameter_values={'episode_steps': cap, 'workflow_args': {'duration': 0.75}},
                          result_path=bad, archive_path=tmp_path / 'output/simulation.tar')


@pytest.mark.skipif(not Path('/opt/i4h/arena/.venv/bin/python').exists(), reason='requires pinned installed Arena CPU environment')
def test_actual_overlay_new_module_and_modified_base_workflow_precede_installed_sources(tmp_path):
    extra = {
        'overlay/tasks/basic/i4h_tasks/basic/control/custom_hold.py': (
            'from i4h_tasks.basic.control.wait import Wait\n'
            'class CustomHold(Wait):\n    pass\n'),
        'overlay/tasks/basic/i4h_tasks/basic/control/wait.py': (
            'from i4h_engine.task import Task\n'
            'from i4h_engine.status import Status\n'
            'class Wait(Task):\n'
            '    MARKER="project-owned"\n'
            '    def __init__(self,seconds=1,name=None):\n'
            '        super().__init__(name=name)\n'
            '    def tick(self,ctx):\n        return Status.SUCCESS\n'),
        'overlay/workflows/i4h_workflows/hospital-automation-robotics/scissor_pick_and_place.py': (
            'from i4h_engine.interface import Workflow\n'
            'from i4h_engine.graph import TaskGraph,node\n'
            'from i4h_tasks.basic.control.custom_hold import CustomHold\n'
            'assert CustomHold.MARKER == "project-owned"\n'
            'def overlay_mode():\n    return TaskGraph().flow(node(CustomHold()))\n'
            'WORKFLOW=Workflow(scene="custom_probe",modes={"authored":overlay_mode},default_mode="authored")\n'),
    }
    source = project_archive(tmp_path / 'project.tar', extra_files=extra)
    result = run(None, {'workflow': 'scissor_pick_and_place', 'mode': 'authored'},
                 tmp_path / 'output', operation='lint', project_path=source)
    selected = result['capabilities']['registry']['selected']
    assert selected['scene'] == 'custom_probe'
    assert selected['controller_modules'] == ['i4h_tasks.basic.control.custom_hold']
    sources = result['provenance']['resolved_sources']
    for name in ('tasks/basic/i4h_tasks/basic/control/custom_hold.py', 'tasks/basic/i4h_tasks/basic/control/wait.py'):
        assert sources[name]['sha256'] == result['provenance']['project_files']['overlay/' + name]['sha256']


@pytest.mark.skipif(not Path('/opt/i4h/arena/.venv/bin/python').exists(), reason='requires pinned installed Arena CPU environment')
def test_actual_remote_policy_inspection_does_not_import_backend_or_claim_it_ready(tmp_path):
    result = run(None, {'workflow': 'scissor_pick_and_place', 'mode': 'policy'},
                 tmp_path / 'output', operation='inspect')
    selected = result['capabilities']['registry']['selected']
    assert selected['lint']['ok']
    assert selected['backends']
    backend = selected['backends'][0]
    assert backend['environment_present'] == (Path('/opt/i4h') / backend['project'] / '.venv/bin/python').is_file()
    assert result['scientific_validation'] == 'not_applicable'
    assert result['task_complete'] is None


def test_training_public_inventory_is_rebuilt_after_operator_separation(tmp_path):
    from isaac_healthcare_runtime.runtime import curate_training
    from isaac_healthcare_runtime.contract import digest

    directory = tmp_path / 'training'
    (directory / 'artifacts').mkdir(parents=True)
    (directory / '.runtime').mkdir()
    (directory / '.runtime/cache').write_text('cache')
    (directory / 'artifacts/checkpoint.bin').write_bytes(b'unit-test-non-model')
    (directory / 'training-execution.log').write_text('GPU placement diagnostics\n')
    (directory / 'training-request.json').write_text('{"internal_path":"/internal"}')
    raw = {'operation': 'train', 'status': 'succeeded', 'scientific_execution': True,
           'engine_exit_code': 0, 'validation': {'status': 'validated'},
           'files': {'stale-cache-and-log': {}},
           'operator_diagnostics': ['training-execution.log', 'training-request.json']}
    (directory / 'training-result.json').write_text(json.dumps(raw))
    result = curate_training(directory, tmp_path / 'operator', 'train')
    assert result['files'] == {'artifacts/checkpoint.bin': {'sha256': digest(directory / 'artifacts/checkpoint.bin'), 'size_bytes': 19}}
    assert (tmp_path / 'operator/training-result.original.json').exists()
    assert (tmp_path / 'operator/runtime/cache').exists()
    assert not (directory / 'training-execution.log').exists()
    assert 'GPU' not in json.dumps(result)
    assert json.loads((directory / 'training-result.json').read_bytes()) == result
    raw['status'] = 'prepared'
    (directory / 'training-result.json').write_text(json.dumps(raw))
    with pytest.raises(RuntimeError, match='completed scientific'):
        curate_training(directory, tmp_path / 'other-operator', 'train')


@pytest.mark.skipif(not Path('/opt/i4h/arena/.venv/bin/python').exists(), reason='requires pinned Zenoh environment')
def test_actual_policy_unix_transport_under_offline_socket_filter():
    import subprocess
    import sys

    result = subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('probe_policy_transport.py'))],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=20)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)['sent_and_received'] is True


@pytest.mark.skipif(not Path('/opt/i4h/arena/.venv/bin/python').exists(), reason='requires pinned Zenoh environment')
def test_actual_policy_transport_uses_operator_session_root_and_removes_only_own_directory():
    import os
    import subprocess
    import sys
    import tempfile

    with tempfile.TemporaryDirectory(prefix='i4h-session-', dir='/tmp') as session_root:
        sentinel = Path(session_root) / 'owner-record'
        sentinel.write_text('preserve session owner files')
        result = subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('probe_policy_transport.py'))],
                                env={**os.environ, 'I4H_BUS_ROOT': session_root},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=20)
        assert result.returncode == 0, result.stdout
        proof = json.loads(result.stdout)
        assert proof['sent_and_received'] is True
        assert proof['bus_parent'] == session_root
        assert proof['private_directory_removed'] is True
        assert list(Path(session_root).iterdir()) == [sentinel]


def test_asset_localization_uses_provenance_for_independent_roots_and_preserves_project_override(tmp_path):
    from types import SimpleNamespace
    from isaac_healthcare_runtime.launch import localize_constants

    base, project = tmp_path / 'base', tmp_path / 'project'
    base.mkdir()
    project.mkdir()
    healthcare = 'https://assets.example/Healthcare/'
    robot = 'https://other.example/Isaac/Robots/robot.usd'
    (base / 'manifest.json').write_text(json.dumps({'files': [
        {'source_url': healthcare + 'scene.usd', 'path': 'health/scene.usd'},
        {'source_url': robot, 'path': 'independent/robot.usd'}]}))
    constants = SimpleNamespace(ASSET_PATH=healthcare, SCENE=healthcare + 'scene.usd', ROBOT=robot)
    localize_constants(constants, base_root=base)
    assert constants.SCENE == str(base / 'health/scene.usd')
    assert constants.ROBOT == str(base / 'independent/robot.usd')
    constants = SimpleNamespace(ASSET_PATH=healthcare, SCENE=healthcare + 'scene.usd', ROBOT=robot)
    localize_constants(constants, base_root=base, explicit_root=project)
    assert constants.SCENE == str(project / 'scene.usd')
    assert constants.ROBOT == str(base / 'independent/robot.usd')
    (project / 'manifest.json').write_text(json.dumps({'files': [{'source_url': robot, 'path': 'authored/robot.usd'}]}))
    constants = SimpleNamespace(ASSET_PATH=healthcare, ROBOT=robot)
    localize_constants(constants, base_root=base, explicit_root=project)
    assert constants.ROBOT == str(project / 'authored/robot.usd')


def test_interactive_hook_retains_requested_science_and_trusted_kit_arguments(tmp_path):
    from isaac_healthcare_runtime.runtime import interactive_command

    values = parameters({'workflow': 'authored', 'mode': 'observe', 'physics': 'newton',
                         'episode_steps': 1000, 'workflow_args': {'seconds': 7.5}})
    context = {'effective_root': str(tmp_path), 'project_dir': str(tmp_path),
               'python_paths': [], 'asset_root': None}
    selected = {'mode': 'observe', 'lint': {'ok': True}, 'backends': []}
    with interactive_command(values, {'name': 'session', 'seed': 73}, tmp_path / 'session',
                             context=context, selected=selected,
                             kit_arguments=['--/app/livestream/port=49100']) as (argv, env):
        assert '--headless' not in argv and '--no-sensor-view' not in argv
        assert argv[argv.index('--presets') + 1] == 'newton'
        assert argv[argv.index('--episode-steps') + 1] == '1000'
        assert argv[argv.index('--seed') + 1] == '73'
        source = json.loads(Path(argv[argv.index('--context') + 1]).read_bytes())
        assert source['kit_arguments'] == ['--/app/livestream/port=49100']
        assert source['parameters']['workflow_args'] == {'seconds': 7.5}
        assert env['I4H_WORKFLOWS'] == str(tmp_path)
