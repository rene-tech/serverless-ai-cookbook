"""Real command entrypoint, real MCP SDK, synthetic local HTTP fault injection.

The subprocess harness denies every model mutation and permits only the saved
operation's status/result and one synthetic artifact. No network is used.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from test_scientific_batch_client import client

OPERATION = 'op-4e333485573f42ac'
ENDPOINT = 'https://platform.example/mcp'
KEY = 'synthetic-key-never-in-output'
HELPER = Path(os.environ.get('SCIENTIFIC_BATCH_TEST_HELPER',
              Path(__file__).parent / 'scripts/scientific-batch-acceptance.py')).resolve()


def case(tmp_path, faults, **settings):
    source, parameters, output = tmp_path / 'source', tmp_path / 'params.json', tmp_path / 'original run'
    source.write_bytes(b'public synthetic source')
    parameters.write_text('{"seed":7}')
    identity = {'model_id': 'fixture', 'source_sha256': client.digest(source.read_bytes()),
                'parameters_sha256': client.digest(client.canonical({'seed': 7})),
                'endpoint': ENDPOINT, 'caller_fingerprint': client.digest(KEY.encode()),
                'idempotency_key': 'original-idempotency-key'}
    receipt = {'identity': identity, 'operation_id': OPERATION, 'state': 'running',
               'source_artifact': {'artifact_id': 'original-source'},
               'manifest_artifact': {'artifact_id': 'original-manifest'}}
    client.save(output / 'receipt.json', receipt)
    config = tmp_path / 'faults.json'
    client.save(config, {'faults': faults, **settings})
    arguments = ['--model', 'fixture', '--tool', 'submit_fixture', '--operation', 'simulate',
                 '--source', str(source), '--parameters', str(parameters), '--output', str(output),
                 '--media-type', 'text/plain', '--entry-name', 'input', '--semantic-type', 'fixture/v1',
                 '--idempotency-key', 'original-idempotency-key', '--display-name', 'synthetic',
                 '--wait-seconds', '180', '--poll-seconds', '0']
    return config, output, arguments, receipt


def invoke(config, arguments):
    env = {**os.environ, 'SCIENTIFIC_MODELS_MCP_URL': ENDPOINT, 'SCIENTIFIC_MODELS_API_KEY': KEY}
    process = subprocess.run([sys.executable, str(Path(__file__).resolve()), str(config),
                              str(HELPER), *arguments], env=env, capture_output=True, text=True, timeout=30)
    history = json.loads(config.with_suffix('.history.json').read_text())
    events = [json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
    assert KEY not in process.stdout + process.stderr
    assert all(item in {'get_operation', 'get_operation_result', 'artifact-read', 'session-close'}
               for item in history['calls']), 'No upload, admission, cancel, restart or new simulation.'
    return process, events, history


@pytest.mark.parametrize('fault', [429, 502, 503, 504, 'disconnect', 'nested_disconnect',
    {'code': 'upstream_unavailable', 'message': 'Temporary service outage', 'retryable': True,
     'retry_after_seconds': 2},
    {'rpc': {'code': -32603, 'message': 'Temporary service outage',
             'data': {'retryable': True, 'retry_after_seconds': 2}}}])
def test_actual_cli_recovers_transient_read_and_preserves_original_receipt(tmp_path, fault):
    config, output, arguments, original = case(tmp_path, [fault])
    process, events, history = invoke(config, arguments)
    assert process.returncode == 0, process.stderr
    assert events[-1]['state'] == 'verified' and events[-1]['operation_id'] == OPERATION
    assert 'Traceback' not in process.stderr
    assert history['calls'].count('get_operation') == 2
    assert history['calls'].count('get_operation_result') == 1
    saved = client.load_receipt(output / 'receipt.json')
    assert saved['observation_failure_count'] == 1
    for field in ('identity', 'operation_id', 'source_artifact', 'manifest_artifact'):
        assert saved[field] == original[field]
    assert saved.get('observation') is None


@pytest.mark.parametrize('recover_original_command', [False, True])
def test_exhausted_cli_reports_unknown_then_recovers_same_receipt(tmp_path, recover_original_command):
    config, output, arguments, original = case(tmp_path, [503] * 5)
    process, events, history = invoke(config, arguments)
    assert process.returncode == 75 and 'Traceback' not in process.stderr
    exhausted = events[-1]
    assert exhausted['outcome'] == 'observation_unavailable'
    assert exhausted['state'] == 'unknown' and exhausted['last_observed_state'] == 'running'
    assert exhausted['operation_id'] == OPERATION
    assert history['calls'] == ['get_operation'] * 5
    assert history['delays'] == [1, 2, 4, 8]
    saved = client.load_receipt(output / 'receipt.json')
    assert saved['state'] == 'running' and saved['identity'] == original['identity']
    recovery = shlex.split(exhausted['recovery_command'])
    assert recovery[:2] == [sys.executable, str(HELPER)]
    assert recovery[2:] == ['--observe-output', str(output.resolve())]
    client.save(config, {'faults': []})
    process, events, history = invoke(config, arguments if recover_original_command else recovery[2:])
    assert process.returncode == 0, process.stderr
    assert events[-1]['operation_id'] == OPERATION and events[-1]['state'] == 'verified'
    assert history['calls'].count('get_operation') == 1
    assert history['calls'].count('artifact-read') == 1


@pytest.mark.parametrize('fault,code,outcome', [
    (401, 77, 'authorization_failed'), (403, 77, 'authorization_failed'),
    (400, 65, 'observation_rejected'), (422, 65, 'observation_rejected'),
    ({'code': 'not_found', 'message': 'Operation not found', 'retryable': False},
     66, 'operation_not_found'),
    ({'code': 'forbidden', 'message': 'Access denied', 'retryable': True},
     77, 'authorization_failed'),
    ({'rpc': {'code': -32602, 'message': 'Invalid parameters'}}, 65, 'observation_rejected'),
])
def test_permanent_reads_remain_distinct_and_do_not_spin(tmp_path, fault, code, outcome):
    config, output, arguments, _ = case(tmp_path, [fault])
    process, events, history = invoke(config, arguments)
    assert process.returncode == code, process.stderr
    assert 'Traceback' not in process.stderr
    assert events[-1]['outcome'] == outcome and events[-1]['state'] == 'unknown'
    assert history['calls'] == ['get_operation'] and history['delays'] == []
    assert client.load_receipt(output / 'receipt.json')['state'] == 'running'


def test_missing_operation_http404_not_lost_mcp_session(tmp_path):
    # A plain RPC HTTP 404 means an expired MCP session to this SDK. Its exact
    # Session terminated signal reconnects, while initialize 404 is permanent.
    config, _, arguments, _ = case(tmp_path, [404], fault_tool='initialize')
    process, events, history = invoke(config, arguments)
    assert process.returncode == 66 and events[-1]['outcome'] == 'operation_not_found'
    assert history['calls'] == [] and history['delays'] == []


@pytest.mark.parametrize('hint', [45, 'date'])
def test_retry_after_is_not_capped_below_server_hint(tmp_path, hint):
    config, _, arguments, _ = case(tmp_path, [429], retry_after=hint)
    process, _, history = invoke(config, arguments)
    assert process.returncode == 0, process.stderr
    assert 43 <= history['delays'][0] <= 45


def test_hint_beyond_wait_deadline_returns_incomplete_without_early_retry(tmp_path):
    config, _, arguments, _ = case(tmp_path, [429], retry_after=300)
    process, events, history = invoke(config, arguments)
    assert process.returncode == 75 and events[-1]['state'] == 'unknown'
    assert history['calls'] == ['get_operation'] and history['delays'] == []


@pytest.mark.parametrize('state,action_required', [('failed', False), ('running', True)])
def test_scientific_error_is_not_a_read_failure(tmp_path, state, action_required):
    config, output, arguments, _ = case(tmp_path, [], state=state, action_required=action_required,
        scientific_error={'code': 'INVALID_INPUT', 'message': 'Synthetic topology atom count is inconsistent.',
                          'next_action': 'Regenerate a matching coordinate/topology pair.'})
    process, events, history = invoke(config, arguments)
    assert process.returncode == 1, process.stderr
    assert 'Traceback' not in process.stderr
    assert events[-1]['outcome'] == ('scientific_action_required' if action_required else 'scientific_failed')
    assert events[-1]['error']['code'] == 'INVALID_INPUT'
    assert events[-1]['message'] == 'Synthetic topology atom count is inconsistent.'
    assert history['calls'] == ['get_operation'] and not history['delays']
    assert client.load_receipt(output / 'receipt.json')['state'] == state


def test_unexpected_programming_error_keeps_traceback_even_in_mixed_group(tmp_path):
    config, _, arguments, _ = case(tmp_path, ['mixed_programming_error'])
    process, events, history = invoke(config, arguments)
    assert process.returncode != 0 and 'ValueError: synthetic programming error' in process.stderr
    assert 'Traceback' in process.stderr and history['delays'] == []
    assert not any(event.get('outcome') == 'observation_rejected' for event in events)


def test_saved_observation_does_not_require_input_files(tmp_path):
    config, output, _, _ = case(tmp_path, [])
    (tmp_path / 'source').unlink()
    (tmp_path / 'params.json').unlink()
    process, events, _ = invoke(config, ['--observe-output', str(output)])
    assert process.returncode == 0 and events[-1]['state'] == 'verified'


def offline_cli_harness():
    """Execute the real __main__ entrypoint with only the HTTP transport injected."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime
    import runpy
    import httpx2
    from mcp.shared.exceptions import MCPError
    from mcp_types import INVALID_PARAMS
    config_path, helper, *arguments = sys.argv[1:]
    config_path = Path(config_path)
    config = json.loads(config_path.read_text())
    faults, history = list(config['faults']), {'calls': [], 'delays': []}
    data = b'{"entries":[]}'
    payload = {'operation_id': OPERATION, 'terminal_status': 'succeeded',
               'semantic_validation': {'status': 'passed'}, 'output_manifest': {
                   'artifact_id': 'manifest', 'size_bytes': len(data),
                   'sha256': hashlib.sha256(data).hexdigest()}}

    def rpc(request, message, result, *, error=False):
        return httpx2.Response(200, request=request,
            json={'jsonrpc': '2.0', 'id': message['id'], 'error' if error else 'result': result})

    def fail(fault, request, message):
        if isinstance(fault, int):
            hint = config.get('retry_after', 2 if fault == 429 else 0)
            if hint == 'date':
                hint = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=45), usegmt=True)
            return httpx2.Response(fault, request=request, text='Synthetic non-sensitive error',
                                   headers={'retry-after': str(hint)})
        if fault == 'disconnect':
            raise httpx2.ReadError('Synthetic disconnect')
        if fault == 'nested_disconnect':
            raise ExceptionGroup('outer', [ExceptionGroup('inner', [httpx2.ReadError('disconnect')])])
        if fault == 'mixed_programming_error':
            raise ExceptionGroup('outer', [MCPError(INVALID_PARAMS, 'Invalid parameters'),
                                           ValueError('synthetic programming error')])
        if 'rpc' in fault:
            return rpc(request, message, fault['rpc'], error=True)
        return rpc(request, message, {'isError': True, 'content': [
            {'type': 'text', 'text': json.dumps({'error': fault})}]})

    def handle(request):
        if request.method == 'GET' and request.url.path == '/v1/artifacts/manifest/content':
            history['calls'].append('artifact-read')
            return httpx2.Response(200, stream=httpx2.ByteStream(data),
                                   headers={'content-length': str(len(data))})
        assert request.url.path == '/mcp', 'Forbidden mutation or unrelated read'
        if request.method == 'GET':
            return httpx2.Response(405)
        if request.method == 'DELETE':
            history['calls'].append('session-close')
            return httpx2.Response(200)
        assert request.method == 'POST'
        message = json.loads(request.content)
        if message['method'] == 'server/discover':
            return rpc(request, message, {'code': -32601, 'message': 'Use initialize'}, error=True)
        if message['method'] == 'initialize':
            if config.get('fault_tool') == 'initialize' and faults:
                return fail(faults.pop(0), request, message)
            return rpc(request, message, {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                                          'serverInfo': {'name': 'offline-client-test', 'version': '1'}})
        if message['method'] == 'notifications/initialized':
            return httpx2.Response(202)
        if message['method'] == 'tools/list':
            return rpc(request, message, {'tools': [{'name': name, 'inputSchema': {'type': 'object'}}
                for name in ('get_operation', 'get_operation_result')]})
        assert message['method'] == 'tools/call'
        name, arguments = message['params']['name'], message['params']['arguments']
        assert name in {'get_operation', 'get_operation_result'}
        assert arguments == {'operation_id': OPERATION}
        history['calls'].append(name)
        if name == config.get('fault_tool', 'get_operation') and faults:
            return fail(faults.pop(0), request, message)
        state = config.get('state', 'succeeded')
        document = ({'operation_id': OPERATION, 'model_id': 'fixture', 'status': state.upper(),
                     'operation': {'operation_id': OPERATION, 'status': state,
                                   'result_available': state == 'succeeded'},
                     'graph': {'action_required': config.get('action_required', False)}}
                    if name == 'get_operation' else payload)
        if config.get('scientific_error'):
            document['error'] = config['scientific_error']
        return rpc(request, message, {'content': [{'type': 'text', 'text': json.dumps(document)}]})

    original_http, original_sleep = httpx2.AsyncClient, asyncio.sleep
    def http(**kwargs):
        return original_http(**kwargs, transport=httpx2.MockTransport(handle))
    async def pause(delay):
        if delay:
            history['delays'].append(delay)
        await original_sleep(0)
    httpx2.AsyncClient, asyncio.sleep = http, pause
    sys.path.insert(0, str(Path(helper).parent))
    sys.argv = [helper, *arguments]
    try:
        runpy.run_path(helper, run_name='__main__')
    finally:
        config_path.with_suffix('.history.json').write_text(json.dumps(history))


if __name__ == '__main__':
    offline_cli_harness()
