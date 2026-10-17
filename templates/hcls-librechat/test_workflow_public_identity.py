"""A saved workflow is not a second public identity for its native jobs."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

import scientific_study as studies
import scientific_workflow_view as view
from scientific_receipts import load, save

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('public_workflow_execution', HERE / 'execution-mcp.py')
execution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(execution)


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    for name, value in {
        'SCIENTIFIC_WORKSPACE': str(tmp_path),
        'SCIENTIFIC_RECEIPT_LOCK_DIR': str(tmp_path / 'locks'),
        'SCIENTIFIC_EXECUTION_DIR': str(tmp_path / 'commands'),
        'SCIENTIFIC_MODELS_MCP_URL': 'https://fixture.invalid/mcp',
        'SCIENTIFIC_MODELS_API_KEY': 'fixture-owner-key',
        'SEED_DEFAULT_USER_EMAIL': 'fixture@example.test',
        'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance',
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'commands')
    return tmp_path


def plan():
    return {'schema': 'scientific-workflow/v2', 'title': 'Native job identity',
        'steps': [{'id': 'report', 'kind': 'analysis', 'method': 'write-json',
            'arguments': {'filename': 'report.json', 'value': {'measured': 1}}}],
        'deliverables': [{'name': 'report.json', 'role': 'report',
            'source': {'step': 'report', 'file': 'report.json'}}]}


def test_public_admission_has_location_but_no_invented_job_identity(mounted):
    args = {'study': plan(), 'output_directory': str(mounted / 'run')}
    first = execution.run_scientific_workflow(args)
    assert first['durable_workflow'] is True and first['operations'] == []
    assert first['state'] == 'queued' and first['study_admission'] == 'accepted'
    assert not {'id', 'job_id', 'study_id', 'operation_id'} & first.keys()
    internal = view.workflow_record(args['output_directory'])
    assert internal['id'] not in json.dumps(first)
    assert execution.read_scientific_workflow(first['next_observation']['arguments'])['operations'] == []
    repeated = execution.run_scientific_workflow(args)
    assert repeated['reused_existing_study'] is True
    assert len(studies.list_studies()) == 1
    with pytest.raises(ValueError, match='Unknown execution'):
        execution.read_job({'job_id': internal['id']})


def test_native_jobs_are_same_ids_without_a_root_alias(mounted):
    record = studies.submit(plan(), mounted / 'run')
    record['steps'] = {'simulate': {'state': 'running', 'operation_id': 'op-native-first'}}
    single = view.public_workflow(record)
    assert single['operation_id'] == 'op-native-first'
    assert single['operations'] == [{'step_id': 'simulate', 'operation_id': 'op-native-first', 'state': 'running'}]
    record['steps']['other'] = {'state': 'queued', 'operation_id': 'op-native-second'}
    multiple = view.public_workflow(record)
    assert 'operation_id' not in multiple
    assert [item['operation_id'] for item in multiple['operations']] == ['op-native-first', 'op-native-second']
    assert record['id'] not in json.dumps(multiple)


def test_existing_record_is_observed_without_rewriting_or_relaunching(mounted, monkeypatch):
    internal = studies.submit(plan(), mounted / 'run')
    path = studies.directory(internal['id']) / 'receipt.json'
    before = path.read_bytes()
    monkeypatch.setattr(studies, 'submit', lambda *a: pytest.fail('Status cannot submit work'))
    result = view.read_workflow(str(mounted / 'run'))
    assert result['state'] == 'queued' and path.read_bytes() == before
    assert internal['id'] not in json.dumps(result)


def test_output_binding_and_owner_are_required(mounted, monkeypatch):
    internal = studies.submit(plan(), mounted / 'owned')
    with pytest.raises((ValueError, FileNotFoundError)):
        view.read_workflow(str(mounted / internal['id']))
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'different-key')
    with pytest.raises(ValueError, match='different configured platform key'):
        view.read_workflow(str(mounted / 'owned'))


def test_cancellation_uses_owned_saved_work_and_retains_native_receipts(mounted):
    internal = studies.submit(plan(), mounted / 'cancel')
    result = view.cancel_workflow(str(mounted / 'cancel'))
    assert result['cancellation_requested'] is True
    assert internal['id'] not in json.dumps(result)
    assert (studies.directory(internal['id']) / 'cancel-request.json').exists()


def test_local_only_workflow_finishes_without_claiming_a_platform_job(mounted):
    internal = studies.submit(plan(), mounted / 'local')
    for _ in range(2):
        asyncio.run(studies.advance(internal['id']))
    result = view.read_workflow(str(mounted / 'local'))
    assert result['state'] == 'completed' and result['operations'] == []
    assert json.loads(Path(result['artifacts'][0]['path']).read_bytes()) == {'measured': 1}
    assert internal['id'] not in json.dumps(result)
