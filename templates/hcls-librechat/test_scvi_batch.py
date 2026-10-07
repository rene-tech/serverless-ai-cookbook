import importlib.util
import json
from pathlib import Path
import types

import pytest

spec = importlib.util.spec_from_file_location('scvi_batch', Path(__file__).with_name('scvi-batch.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def args(tmp_path):
    parameters = tmp_path / 'parameters.json'
    parameters.write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/scvi-workflow-request/v1', 'method': 'scvi'}))
    source = tmp_path / 'counts.h5ad'
    source.write_bytes(b'input fixture; transport mocked')
    return types.SimpleNamespace(output=tmp_path / 'run', input=source, parameters=parameters,
                                 reference=None, idempotency_key='retained-study-1', protocol='mcp',
                                 wait_seconds=1, recover_only=False)


@pytest.fixture(autouse=True)
def caller(monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_BASE_URL', 'https://example.org/v1')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'unit-test-not-a-real-key')


@pytest.mark.parametrize('state,published,expected', [
    ('queued', False, 75), ('running', False, 75), ('succeeded', False, 75),
    ('failed', False, 75), ('failed', True, 1), ('cancelled', True, 1),
])
def test_pending_and_recovery_preserve_operation(tmp_path, state, published, expected):
    value = args(tmp_path)
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        if 'qualify_hosted' in command:
            pipeline.save(value.output / 'run/admission.json', {'operation': {'id': 'op-1'}})
            pipeline.save(value.output / 'run/status.json', {'batch': {'status': state, 'result_published': published}})
            return types.SimpleNamespace(returncode=1)
        return types.SimpleNamespace(returncode=0)

    result, code = pipeline.run(value, runner)
    assert code == expected and result['operation_id'] == 'op-1'
    assert len(commands) == 2
    value.recover_only = True
    value.input = value.parameters = value.idempotency_key = value.protocol = None
    result, code = pipeline.run(value, runner)
    assert code == expected and len(commands) == 3
    assert '--operation-id' in commands[-1] and '--request' not in commands[-1]
    assert commands[-1][commands[-1].index('--protocol') + 1] == 'mcp'


def test_existing_owner_and_arguments_are_bound(tmp_path, monkeypatch):
    value = args(tmp_path)
    pipeline.run(value, lambda *a, **kw: types.SimpleNamespace(returncode=1))
    value.input = tmp_path / 'different.h5ad'
    with pytest.raises(ValueError, match='retained run'):
        pipeline.run(value)
    value.input = None
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'another-unit-test-key')
    with pytest.raises(ValueError, match='different endpoint/key'):
        pipeline.run(value)


def test_unknown_admission_never_submits_on_recovery(tmp_path):
    value = args(tmp_path)
    value.recover_only = True
    with pytest.raises(ValueError, match='New runs require'):
        pipeline.run(value)


def test_pinned_clients_and_source_are_present():
    pipeline.verify_client()
    assert (pipeline.CLIENT / 'LICENSE').exists()


def test_directory_build_context_includes_runtime_verifier():
    root = Path(__file__).parent
    ignored = (root / 'Dockerfile.single-cell.dockerignore').read_text().splitlines()
    assert '!templates/hcls-librechat/verify-single-cell-runtime.py' in ignored
    assert (root / 'verify-single-cell-runtime.py').is_file()


def test_recovery_never_appends_or_replaces_prior_logs(tmp_path, monkeypatch):
    value = args(tmp_path)
    original_open = Path.open

    def bucket_open(path, mode='r', *args, **kwargs):
        if 'a' in mode and path.is_relative_to(value.output):
            raise PermissionError('Object storage does not support append')
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', bucket_open)
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        kwargs['stdout'].write('attempt ' + str(len(calls)) + '\n')
        if 'qualify_hosted' in command:
            pipeline.save(value.output / 'run/admission.json', {'operation': {'id': 'op-retained'}})
            pipeline.save(value.output / 'run/status.json', {'batch': {'status': 'running'}})
            return types.SimpleNamespace(returncode=1)
        return types.SimpleNamespace(returncode=0)

    first, code = pipeline.run(value, runner)
    assert code == 75
    before = Path(first['log']).read_bytes()
    legacy = value.output / 'client.log'
    legacy.write_text('Older client evidence; do not truncate')
    value.recover_only = True
    value.input = value.parameters = value.idempotency_key = value.protocol = None
    second, code = pipeline.run(value, runner)
    assert code == 75 and second['operation_id'] == 'op-retained'
    assert first['log'] != second['log']
    assert Path(first['log']).read_bytes() == before
    assert legacy.read_text() == 'Older client evidence; do not truncate'
    assert len(calls) == 3 and '--operation-id' in calls[-1]
    assert pipeline.load(value.output / 'workbench.json')['log'] == second['log']


def test_success_requires_output_validation(tmp_path, monkeypatch):
    value = args(tmp_path)
    import sys
    verified = []
    fake = types.ModuleType('qualify_outputs')
    fake.validate = lambda result, data: verified.append((result, data)) or {'all_rows': True}
    monkeypatch.setitem(sys.modules, 'qualify_outputs', fake)

    def runner(command, **kwargs):
        if 'qualify_hosted' in command:
            pipeline.save(value.output / 'run/admission.json', {'operation': {'id': 'op-1'}})
        return types.SimpleNamespace(returncode=0)

    result, code = pipeline.run(value, runner)
    assert code == 0 and result['validation']['all_rows']
    assert verified == [(value.output / 'run/worker-result.json', value.output / 'run/data')]


def test_skill_uses_real_batch_contract():
    root = Path(__file__).resolve().parents[2]
    text = (root / 'skills/scientific-ai/single-cell-analysis/SKILL.md').read_text()
    for required in ('scientific-batch-v1', 'submit_scvi_scanvi', '--recover-only',
                     'method: scanvi', 'mode: map-query', 'not biological accuracy'):
        assert required in text
    assert 'scvi_train' not in text and 'map_query' not in text
