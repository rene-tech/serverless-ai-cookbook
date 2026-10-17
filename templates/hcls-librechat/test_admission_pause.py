"""Current marked refusal is retryable; a plain 503 never proves non-admission."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('pause_workflow', Path(__file__).with_name('scientific-workflow.py'))
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class ToolResponse:
    def __init__(self, error, encoding='structured', is_error=False):
        self.value = {'isError': is_error}
        self.value['structuredContent' if encoding == 'structured' else 'content'] = (
            {'error': error} if encoding == 'structured'
            else [{'type': 'text', 'text': json.dumps({'error': error})}])

    def model_dump(self, **_kwargs):
        return self.value


def paused(**changes):
    return {'code': 'ADMISSION_PAUSED', 'admission': 'not-submitted',
            'retryable': True, 'retry_after_seconds': 30, **changes}


@pytest.mark.parametrize('encoding', ['structured', 'text'])
@pytest.mark.parametrize('is_error', [False, True])
@pytest.mark.parametrize('code', ['ADMISSION_PAUSED', 'ADMISSION_LIMIT_REACHED', 'MODEL_MAINTENANCE'])
def test_current_sdk_error_envelopes_preserve_exact_definitive_refusal(encoding, is_error, code):
    error = paused(code=code)
    response = ToolResponse(error, encoding, is_error)
    with pytest.raises(workflow.batch.ExplicitRejection) as caught:
        workflow.batch.unpack(response)
    assert caught.value.error == error
    assert workflow.native.explicit_rejection(response) == error
    assert workflow.admission_retryable(error)


@pytest.mark.parametrize('error', [
    paused(admission='unknown'), paused(admission='not-confirmed'),
    {'code': 'ADMISSION_PAUSED', 'retryable': True},
    {'code': 'SERVERLESS_REQUEST_FAILED', 'retryable': True, 'status_code': 503, 'admission': 'unknown'},
    {'code': 'ADMISSION_LIMIT_REACHED', 'retryable': True},
    paused(operation_id='op-existing'), paused(operation_id=None),
])
def test_ambiguous_or_contradictory_errors_cannot_enter_admission_retry(error):
    response = ToolResponse(error)
    assert workflow.native.explicit_rejection(response) is None
    assert not workflow.admission_retryable(error)
    with pytest.raises(workflow.batch.ToolReadError):
        workflow.batch.unpack(response)


@pytest.mark.parametrize('error', [paused(retryable=False), paused(code='INVALID_INPUT')])
def test_nonretryable_refusal_stays_a_refusal_without_automatic_retry(error):
    assert not workflow.admission_retryable(error)
    assert workflow.native.explicit_rejection(ToolResponse(error)) == error


def plan(root):
    return {'steps': [{'id': 'md', 'model': 'gromacs', 'tool': 'submit_gromacs_workflow',
        'operation': 'run-workflow', 'source': str(root / 'source.tar.gz'),
        'parameters': str(root / 'parameters.json'), 'output': str(root / 'step'),
        'media_type': 'application/gzip', 'entry_name': 'source', 'semantic_type': 'gromacs-source/v1',
        'idempotency_key': 'immutable-request-key', 'display_name': 'Pause fixture'}]}


@pytest.mark.parametrize('wrapped', [False, True])
def test_marked_pause_waits_and_resubmits_only_same_request_with_original_key(tmp_path, wrapped):
    calls, delays = [], []

    async def step(args):
        calls.append(vars(args).copy())
        if len(calls) == 1:
            try:
                workflow.batch.unpack(ToolResponse(paused()))
            except workflow.batch.ExplicitRejection as error:
                if wrapped:
                    raise ExceptionGroup('MCP teardown', [error])
                raise
        return {'state': 'verified', 'operation_id': 'op-current'}

    async def sleep(delay):
        delays.append(delay)

    result = asyncio.run(workflow.run(plan(tmp_path), tmp_path / 'workflow', run_step=step, sleep=sleep))
    assert result['state'] == 'completed'
    assert len(calls) == 2 and calls[0] == calls[1]
    assert calls[0]['idempotency_key'] == 'immutable-request-key' and delays == [30]


def test_pause_wait_is_bounded_and_keeps_original_request_recoverable(tmp_path):
    calls = []

    async def step(args):
        calls.append(args.idempotency_key)
        workflow.batch.unpack(ToolResponse(paused()))

    result = asyncio.run(workflow.run(plan(tmp_path), tmp_path / 'workflow', wait_seconds=1,
        run_step=step, clock=iter((0, 0, 2)).__next__))
    assert result['state'] == 'waiting_admission'
    assert result['completed_steps'] == []
    assert calls == ['immutable-request-key']
    assert result['step_states']['md']['error'] == paused()


def test_unmarked_503_never_resubmits_unknown_admission(tmp_path):
    calls = []

    async def step(args):
        calls.append(args.idempotency_key)
        workflow.save(args.output / 'receipt.json', {'state': 'admission_unknown'})
        workflow.batch.unpack(ToolResponse({'code': 'SERVERLESS_REQUEST_FAILED', 'status_code': 503,
                                            'admission': 'unknown', 'retryable': True}))

    with pytest.raises(workflow.batch.ToolReadError):
        asyncio.run(workflow.run(plan(tmp_path), tmp_path / 'workflow', run_step=step))
    assert calls == ['immutable-request-key']
    assert workflow.load(tmp_path / 'workflow/receipt.json')['state'] == 'admission_unknown'
