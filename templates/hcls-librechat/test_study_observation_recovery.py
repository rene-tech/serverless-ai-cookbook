"""Known-operation recovery through the saved study, transport and queue."""
import asyncio
from pathlib import Path

import pytest
from anyio import EndOfStream

import scientific_study as study
from scientific_receipts import load, save
from test_study_admission_recovery import scenario, client, OP, WORKER_PATH


def interrupted(tmp_path, monkeypatch):
    first, second, worker, calls, uploads = scenario(tmp_path, monkeypatch)
    asyncio.run(worker.reconcile(first['id']))
    async def lost(*args, **kwargs):
        raise ExceptionGroup('unhandled errors in a TaskGroup', [EndOfStream()])
    monkeypatch.setattr(client, 'observe_operation', lost)
    result = asyncio.run(study.advance(first['id']))
    assert result['state'] == 'needs_attention' and not result['admission_unknown']
    return first, second, worker, calls, uploads


def observe(state='running'):
    async def read(args, http, endpoint, headers, receipt, path, **kwargs):
        assert args.observe_only
        assert receipt['operation_id'] == OP
        receipt['state'] = state
        save(path, receipt)
        return receipt
    return read


def test_known_job_recovers_without_upload_or_admission_and_queue_is_fair(tmp_path, monkeypatch):
    first, second, worker, calls, uploads = interrupted(tmp_path, monkeypatch)
    sent = list(calls), list(uploads)
    # Later admission must not wait for a long remote simulation to finish.
    assert worker.next_study(study.list_studies()) == (second['id'], None)
    monkeypatch.setattr(client, 'observe_operation', observe())
    result = asyncio.run(worker.reconcile_observation(first['id']))
    assert result['state'] == 'running' and not result['queue_blocked']
    assert result['steps']['simulate']['operation_id'] == OP
    record = load(study.directory(first['id']) / 'receipt.json')
    assert record['recovered_failures'] and not record.get('failure')
    transport = load(tmp_path / 'first/steps/simulate/workflow/receipt.json')
    assert transport['state'] == 'running' and transport['recovered_failures']
    assert (calls, uploads) == sent
    # Observe normally again, from precisely the original operation receipt.
    async def complete(args, http, endpoint, headers, receipt, path, **kwargs):
        assert receipt['operation_id'] == OP
        save(args.output / 'output-manifest.json', {'operation_id': OP})
        receipt['state'] = 'verified'
        save(path, receipt)
        return receipt
    monkeypatch.setattr(client, 'observe_operation', complete)
    for _ in range(3):
        result = asyncio.run(study.advance(first['id']))
    assert result['state'] == 'completed'
    assert (calls, uploads) == sent


def test_read_outage_is_backed_off_and_does_not_block_other_saved_requests(tmp_path, monkeypatch):
    first, second, worker, calls, uploads = interrupted(tmp_path, monkeypatch)
    sent = len(calls), len(uploads)
    asyncio.run(worker.reconcile_observation(first['id']))
    record = load(study.directory(first['id']) / 'receipt.json')
    assert record['observation_recovery']['retryable']
    assert record['observation_recovery']['error_type'] == 'EndOfStream'
    assert not record['queue_blocked']
    assert worker.next_study([study.view(record)]) == (None, None)
    assert worker.next_study(study.list_studies()) == (second['id'], None)
    assert (len(calls), len(uploads)) == sent


@pytest.mark.parametrize('block', ['owner', 'input', 'artifact', 'cancel', 'terminal'])
def test_recovery_never_retries_invalid_science_or_changed_identity(tmp_path, monkeypatch, block):
    first, second, worker, calls, uploads = interrupted(tmp_path, monkeypatch)
    reads = []
    async def invalid(*args, **kwargs):
        reads.append(1)
        raise ValueError('Artifact checksum mismatch')
    monkeypatch.setattr(client, 'observe_operation', invalid)
    if block == 'owner':
        monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'different')
    elif block == 'input':
        (tmp_path / 'parameters.json').write_text('{"changed":true}')
    elif block == 'cancel':
        study.request_cancel(first['id'])
    elif block == 'terminal':
        target = tmp_path / 'first/steps/simulate/operation/receipt.json'
        save(target, {**load(target), 'state': 'failed'})
    sent = len(calls), len(uploads)
    result = asyncio.run(worker.reconcile_observation(first['id']))
    if block in {'cancel', 'terminal'}:
        assert result is None
    else:
        record = load(study.directory(first['id']) / 'receipt.json')
        assert record['observation_recovery']['retryable'] is False
        assert worker.observation_step(record) is None
        assert worker.next_study(study.list_studies()) == (None if block == 'owner' else second['id'], None)
        # The customer view omits private retry metadata. With no other work,
        # the failed record must not spin forever in the worker selector.
        assert worker.next_study([study.view(record)]) == (None, None)
    assert len(reads) == (1 if block == 'artifact' else 0)
    assert (len(calls), len(uploads)) == sent


def test_native_operation_uses_recover_only_and_preserves_selector(tmp_path, monkeypatch):
    import importlib.util
    from test_scientific_study import plan
    from test_scientific_workflow import workflow
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'unit-test-key')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'internal@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    prepared = plan()
    prepared['steps'][1]['tool_name'] = 'infer_example'
    first = study.submit(prepared, tmp_path / 'native')
    asyncio.run(study.advance(first['id']))
    async def disconnected(step, record):
        save(tmp_path / 'native/steps/model/operation/receipt.json', {'state':'running','operation_id':OP})
        raise ConnectionError('observer disconnected')
    asyncio.run(study.advance(first['id'], model_runner=disconnected))
    seen = []
    async def read(args):
        assert args.recover_only and args.tool == 'infer_example'
        seen.append(args.idempotency_key)
        return {'state':'running','operation_id':OP}
    monkeypatch.setattr(workflow.native, 'run', read)
    monkeypatch.setattr(study, 'workflow_module', lambda:workflow)
    spec=importlib.util.spec_from_file_location('native_recovery', WORKER_PATH)
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    assert asyncio.run(worker.reconcile_observation(first['id']))['state']=='running'
    assert seen==['unchanged-study-input']


def test_crash_after_child_observation_cannot_create_another_operation(tmp_path, monkeypatch):
    first, _, worker, calls, uploads = interrupted(tmp_path, monkeypatch)
    monkeypatch.setattr(client, 'observe_operation', observe())
    original = worker.save
    def crash(path, value):
        if path == study.directory(first['id']) / 'receipt.json':
            raise SystemExit('crash before parent acknowledgement')
        return original(path, value)
    monkeypatch.setattr(worker, 'save', crash)
    sent = len(calls), len(uploads)
    with pytest.raises(SystemExit):
        asyncio.run(worker.reconcile_observation(first['id']))
    monkeypatch.setattr(worker, 'save', original)
    assert asyncio.run(worker.reconcile_observation(first['id']))['state'] == 'running'
    assert (len(calls), len(uploads)) == sent
