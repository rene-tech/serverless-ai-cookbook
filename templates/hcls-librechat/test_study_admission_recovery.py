"""Lost current batch admissions recover through the real saved-study layers."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
import scientific_study as study
from scientific_receipts import load, save
from test_current_batch_contracts import setup_submission, OP
from test_scientific_batch_client import client
from test_scientific_workflow import workflow


def scenario(tmp_path, monkeypatch):
    args, calls, uploads = setup_submission(tmp_path, monkeypatch, 'gromacs')
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'internal@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(workflow, 'batch', client)
    monkeypatch.setattr(study, 'workflow_module', lambda: workflow)
    step = {name: str(value) if isinstance(value, Path) else value
            for name, value in vars(args).items() if name not in {'output', 'wait_seconds', 'poll_seconds'}}
    step.update(id='simulate', kind='batch')
    plan = {'schema': study.SCHEMA, 'title': 'Admission recovery fixture', 'steps': [step,
        {'id': 'report', 'kind': 'analysis', 'method': 'write-json', 'arguments': {
            'filename': 'report.json', 'value': {'source': {'step': 'simulate', 'file': 'output-manifest.json'}}}}],
        'deliverables': [{'name': 'verified report', 'role': 'report',
                          'source': {'step': 'report', 'file': 'report.json'}}]}
    first = study.submit(plan, tmp_path / 'first')
    second = study.submit(plan, tmp_path / 'second')
    async def old_call(connection, name, arguments):
        if name == args.tool:
            raise client.httpx2.ReadError('Old client lost acknowledgement')
        return await original(connection, name, arguments)
    original = client.call
    monkeypatch.setattr(client, 'call', old_call)
    async def old_runner(step, record):
        selected = argparse.Namespace(**vars(args))
        selected.output = Path(record['output_directory']) / 'steps/simulate/operation'
        await client._run(selected)  # Previous client stopped before exact replay.
    result = asyncio.run(study.advance(first['id'], model_runner=old_runner))
    assert result['state'] == 'needs_attention' and result['admission_unknown']
    monkeypatch.setattr(client, 'call', original)
    spec = importlib.util.spec_from_file_location('recovery_worker',
        Path(__file__).with_name('scientific-study-worker.py'))
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return first, second, worker, calls, uploads


def test_saved_study_recovers_and_releases_next_workflow(tmp_path, monkeypatch):
    first, second, worker, calls, uploads = scenario(tmp_path, monkeypatch)
    assert worker.next_study(study.list_studies()) == (first['id'], None)
    recovered = asyncio.run(worker.reconcile(first['id']))
    assert recovered['steps']['simulate']['operation_id'] == OP
    assert not recovered['queue_blocked'] and not recovered['admission_unknown']
    async def observed(args, http, endpoint, headers, receipt, path, **kwargs):
        # Scientific artifacts are synthetic here; the integration is receipt/
        # replay/queue behavior, not a scientific validity or live model claim.
        save(args.output / 'output-manifest.json', {'operation_id': receipt['operation_id']})
        receipt['state'] = 'verified'
        save(path, receipt)
        return receipt
    monkeypatch.setattr(client, 'observe_operation', observed)
    result = asyncio.run(study.advance(first['id']))
    assert result['steps']['simulate']['operation_id'] == OP
    assert not result['queue_blocked'] and not result['admission_unknown']
    for _ in range(2):
        result = asyncio.run(study.advance(first['id']))
    assert result['state'] == 'completed'
    saved = load(study.directory(first['id']) / 'receipt.json')
    assert saved['recovered_failures'] and 'failure' not in saved
    assert worker.next_study(study.list_studies()) == (second['id'], None)
    assert len(uploads) == 2  # No replacement uploads on reconciliation.
    assert [name for name, _ in calls].count('get_model_schema') == 1


@pytest.mark.parametrize('block', ['budget', 'cancel', 'owner', 'input'])
def test_reconciliation_does_not_ignore_saved_identity_or_cancel(tmp_path, monkeypatch, block):
    first, _, worker, calls, uploads = scenario(tmp_path, monkeypatch)
    if block == 'budget':
        target = tmp_path / 'first/steps/simulate/operation/receipt.json'
        value = load(target)
        save(target, {**value, 'admission_replay_attempts': client.ADMISSION_REPLAY_ATTEMPTS})
        assert worker.next_study(study.list_studies()) == (None, first['id'])
    elif block == 'cancel':
        study.request_cancel(first['id'])
        assert worker.next_study(study.list_studies()) == (None, first['id'])
    elif block == 'owner':
        monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'different-owner')
    else:
        (tmp_path / 'parameters.json').write_text(json.dumps({'changed': True}))
    before = len(calls)
    if block in {'owner', 'input'}:
        with pytest.raises((ValueError, RuntimeError)):
            asyncio.run(worker.reconcile(first['id']))
    else:
        assert asyncio.run(worker.reconcile(first['id'])) is None
    result = study.view(load(study.directory(first['id']) / 'receipt.json'))
    assert result['state'] == 'needs_attention' and result['queue_blocked']
    assert len(calls) == before and len(uploads) == 2


def test_recovery_after_child_ack_before_study_write_does_not_admit_again(tmp_path, monkeypatch):
    first, _, worker, calls, uploads = scenario(tmp_path, monkeypatch)
    original = worker.save
    def died(path, value):
        if path == study.directory(first['id']) / 'receipt.json' and value.get('phase') == 'admission_recovered':
            raise SystemExit('process died after child ACK')
        return original(path, value)
    monkeypatch.setattr(worker, 'save', died)
    with pytest.raises(SystemExit):
        asyncio.run(worker.reconcile(first['id']))
    sent = len(calls)
    monkeypatch.setattr(worker, 'save', original)
    assert worker.next_study(study.list_studies()) == (first['id'], None)
    assert asyncio.run(worker.reconcile(first['id']))['phase'] == 'admission_recovered'
    assert len(calls) == sent and len(uploads) == 2
