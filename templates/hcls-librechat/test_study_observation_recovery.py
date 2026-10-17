"""Known-operation recovery through the saved study, transport and queue."""
import asyncio
from pathlib import Path

import pytest
from anyio import EndOfStream

import scientific_study as study
from scientific_receipts import load, save
from test_study_admission_recovery import scenario, client, OP


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
    assert len(reads) == (1 if block == 'artifact' else 0)
    assert (len(calls), len(uploads)) == sent


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
