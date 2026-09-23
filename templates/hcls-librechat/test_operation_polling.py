"""Actual MCP 2.2 / HTTP transport faults, never another scientific admission."""
import argparse
import asyncio
import json
from types import SimpleNamespace

import pytest
from mcp.shared.exceptions import MCPError
from mcp_types import INTERNAL_ERROR, INVALID_PARAMS

from test_scientific_batch_client import client

OPERATION = '4e333485-573f-42ac-af81-a919cdf20913'


def resumed_run(tmp_path, monkeypatch, faults, *, fault_tool='get_scientific_status'):
    """Use the real SDK and an isolated mock HTTP server, including handshakes."""
    args = argparse.Namespace(source=tmp_path / 'source', parameters=tmp_path / 'parameters',
                              model='fixture', output=tmp_path / 'run', idempotency_key='original-key',
                              wait_seconds=3600, poll_seconds=0)
    args.source.write_bytes(b'original unchanged source')
    args.parameters.write_text('{"seed":7}')
    endpoint, key = 'https://platform.example/mcp', 'synthetic-key-never-in-receipts'
    identity = {'model_id': args.model, 'source_sha256': client.digest(args.source.read_bytes()),
                'parameters_sha256': client.digest(client.canonical({'seed': 7})),
                'endpoint': endpoint, 'caller_fingerprint': client.digest(key.encode()),
                'idempotency_key': args.idempotency_key}
    original = {'identity': identity, 'operation_id': OPERATION, 'state': 'running',
                'source_artifact': {'artifact_id': 'unchanged-source'},
                'manifest_artifact': {'artifact_id': 'unchanged-manifest'}}
    client.save(args.output / 'receipt.json', original)
    previous = {'operation': {'id': OPERATION, 'status': 'running'}, 'batch': {'result_published': False}}
    client.save(args.output / 'status.json', previous)
    data = json.dumps({'entries': []}).encode()
    result = {'operation_id': OPERATION, 'terminal_status': 'succeeded',
              'semantic_validation': {'status': 'passed'}, 'output_manifest': {
                  'artifact_id': 'manifest', 'sha256': client.digest(data), 'size_bytes': len(data)}}
    calls, sessions, delays = [], [], []
    fault_queue = list(faults)

    def rpc_response(request, message, body, *, error=False, headers=None):
        return client.httpx2.Response(200, request=request, headers=headers,
            json={'jsonrpc': '2.0', 'id': message['id'], 'error' if error else 'result': body})

    def handle(request):
        if request.method == 'GET' and request.url.path == '/v1/artifacts/manifest/content':
            calls.append('artifact-read')
            return client.httpx2.Response(200, stream=client.httpx2.ByteStream(data),
                                          headers={'content-length': str(len(data))})
        assert request.url.path == '/mcp', 'No upload/reservation path is allowed'
        if request.method == 'GET':
            return client.httpx2.Response(405)
        if request.method == 'DELETE':
            return client.httpx2.Response(200)
        assert request.method == 'POST'
        message = json.loads(request.content)
        if message['method'] == 'server/discover':
            return rpc_response(request, message, {'code': -32601, 'message': 'legacy handshake'}, error=True)
        if message['method'] == 'initialize':
            sessions.append('session-' + str(len(sessions) + 1))
            if fault_tool == 'initialize' and fault_queue:
                return client.httpx2.Response(fault_queue.pop(0), text='synthetic handshake failure')
            return rpc_response(request, message, {
                'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                'serverInfo': {'name': 'synthetic-read-only-server', 'version': '1'}},
                headers={'mcp-session-id': sessions[-1]})
        if message['method'] == 'notifications/initialized':
            return client.httpx2.Response(202)
        if message['method'] == 'tools/list':
            # The SDK reads metadata to validate a returned tool result.
            return rpc_response(request, message, {'tools': [{
                'name': name, 'inputSchema': {'type': 'object'}}
                for name in ('get_scientific_status', 'get_scientific_result')]})
        assert message['method'] == 'tools/call', 'No admission after saved operation'
        name, arguments = message['params']['name'], message['params']['arguments']
        assert name in {'get_scientific_status', 'get_scientific_result'}
        assert arguments == {'operation_id': OPERATION}
        calls.append(name)
        if name == fault_tool and fault_queue:
            fault = fault_queue.pop(0)
            if isinstance(fault, int):
                return client.httpx2.Response(fault, text='synthetic private error body',
                                              headers={'retry-after': '2' if fault == 429 else '0'})
            if isinstance(fault, Exception):
                raise fault
            if 'rpc' in fault:
                return rpc_response(request, message, fault['rpc'], error=True)
            return rpc_response(request, message, {'isError': True, 'content': [{
                'type': 'text', 'text': json.dumps({'error': fault})}]})
        document = ({'operation': {'id': OPERATION, 'status': 'succeeded'},
                     'batch': {'result_published': True}}
                    if name == 'get_scientific_status' else result)
        return rpc_response(request, message, {'content': [{'type': 'text', 'text': json.dumps(document)}]})

    original_http, original_sleep = client.httpx2.AsyncClient, asyncio.sleep
    def http(**kwargs):
        return original_http(**kwargs, transport=client.httpx2.MockTransport(handle))
    async def pause(delay):
        delays.append(delay)
        await original_sleep(0)
    async def forbidden_upload(*args, **kwargs):
        raise AssertionError('A status retry must never upload or reserve anything')
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', endpoint)
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', key)
    monkeypatch.setattr(client.httpx2, 'AsyncClient', http)
    monkeypatch.setattr(client.asyncio, 'sleep', pause)
    monkeypatch.setattr(client, 'upload', forbidden_upload)
    return args, original, previous, calls, sessions, delays


@pytest.mark.parametrize('fault', [408, 429, 500, 502, 503, 504, 404,
    client.httpx2.ReadError('connection reset'),
    {'rpc': {'code': -32001, 'message': 'Request timed out'}},
    {'rpc': {'code': -32603, 'message': 'temporary internal failure'}},
    {'code': 'runtime_unavailable', 'message': 'temporarily unavailable', 'retryable': True,
     'retry_after_seconds': 2, 'durable_admission': True, 'request_id': 'request-1'}])
def test_actual_sdk_transient_reconnect_preserves_operation_and_never_submits(tmp_path, monkeypatch, fault):
    args, original, _, calls, sessions, _ = resumed_run(tmp_path, monkeypatch, [fault])
    receipt = asyncio.run(client.run(args))
    assert receipt['state'] == 'verified' and len(sessions) == 2
    assert calls == ['get_scientific_status', 'get_scientific_status', 'get_scientific_result', 'artifact-read']
    for field in ('operation_id', 'identity', 'source_artifact', 'manifest_artifact'):
        assert receipt[field] == original[field]
    assert receipt['observation_failure_count'] == 1
    event = receipt['observation_errors'][0]
    assert event['retry_scheduled'] and event['consecutive_failures'] == 1
    if isinstance(fault, int):
        assert event['http_status'] == fault
    evidence = json.dumps(receipt)
    assert 'synthetic-key-never-in-receipts' not in evidence
    assert 'synthetic private error body' not in evidence


@pytest.mark.parametrize('fault', [400, 401, 403, 422,
    {'rpc': {'code': -32602, 'message': 'Invalid parameters'}},
    {'rpc': {'code': -32601, 'message': 'Unknown tool'}},
    {'code': 'not_found', 'message': 'No such operation', 'retryable': False},
    {'code': 'forbidden', 'message': 'Not allowed', 'retryable': True},
    {'code': 'invalid_tool_arguments', 'message': 'Invalid arguments', 'retryable': False},
    {'code': 'internal_tool_error', 'message': 'Non-retryable error', 'retryable': False},
    {'rpc': {'code': -32603, 'message': 'Permanent', 'data': {'retryable': False, 'code': 'not_found'}}}])
def test_permanent_error_stops_promptly_without_changing_saved_status(tmp_path, monkeypatch, fault):
    args, original, previous, calls, sessions, delays = resumed_run(tmp_path, monkeypatch, [fault])
    with pytest.raises(Exception):
        asyncio.run(client.run(args))
    receipt = client.load_receipt(args.output / 'receipt.json')
    assert len(sessions) == 1 and calls == ['get_scientific_status'] and not delays
    assert receipt['state'] == original['state'] and receipt['operation_id'] == OPERATION
    assert client.load_receipt(args.output / 'status.json') == previous
    assert not receipt['observation_errors'][0]['retry_scheduled']


def test_repeated_server_failures_have_fixed_budget_and_remain_resumable(tmp_path, monkeypatch):
    args, original, previous, calls, sessions, delays = resumed_run(tmp_path, monkeypatch, [503] * 5)
    receipt = asyncio.run(client.run(args))
    assert receipt['state'] == 'running' and len(sessions) == 5
    assert calls == ['get_scientific_status'] * 5 and delays == [1, 2, 4, 8]
    assert receipt['operation_id'] == OPERATION and receipt['identity'] == original['identity']
    assert client.load_receipt(args.output / 'status.json') == previous
    assert not receipt['observation_errors'][-1]['retry_scheduled']
    # A later invocation observes the same durable operation; no acceptance replay.
    recovered = asyncio.run(client.run(args))
    assert recovered['state'] == 'verified' and len(sessions) == 6


def test_deadline_prevents_retry_and_preserves_authoritative_state(tmp_path, monkeypatch):
    args, _, previous, calls, sessions, delays = resumed_run(tmp_path, monkeypatch, [503])
    args.wait_seconds = 0
    receipt = asyncio.run(client.run(args))
    assert receipt['state'] == 'running' and len(sessions) == 1 and not delays
    assert calls == ['get_scientific_status']
    assert client.load_receipt(args.output / 'status.json') == previous


def test_result_read_retries_but_successful_status_does_not_reset_its_failure_budget(tmp_path, monkeypatch):
    args, _, _, calls, sessions, _ = resumed_run(tmp_path, monkeypatch, [503] * 5,
                                               fault_tool='get_scientific_result')
    receipt = asyncio.run(client.run(args))
    assert receipt['state'] == 'succeeded', 'Published is not yet hash-verified client success'
    assert len(sessions) == 5 and calls == ['get_scientific_status', 'get_scientific_result'] * 5
    assert 'verified_artifacts' not in receipt


def test_completed_recovery_uses_same_bounded_read_only_path(tmp_path, monkeypatch):
    _, _, _, calls, sessions, _ = resumed_run(tmp_path, monkeypatch, [503])
    args = argparse.Namespace(recover_operation_id=OPERATION, output=tmp_path / 'fresh-recovery')
    receipt = asyncio.run(client.recover_completed(args))
    assert receipt['state'] == 'verified' and len(sessions) == 2
    assert calls == ['get_scientific_status', 'get_scientific_status', 'get_scientific_result', 'artifact-read']


def test_mixed_exception_group_cannot_hide_permanent_validation_failure():
    transient = MCPError(INTERNAL_ERROR, 'Server returned an error response')
    permanent = MCPError(INVALID_PARAMS, 'Invalid parameters')
    assert client.operation_read_failure(ExceptionGroup('transient', [transient]))['retryable']
    assert not client.operation_read_failure(ExceptionGroup('mixed', [transient, permanent]))['retryable']
    assert not client.operation_read_failure(ValueError('local failure'), {'http_status': 503})['retryable']


def test_generic_http_error_is_not_a_retryable_auth_error():
    generic = MCPError(INTERNAL_ERROR, 'Server returned an error response')
    assert not client.operation_read_failure(generic, {'http_status': 401})['retryable']
    assert not client.operation_read_failure(generic, {'http_status': 403})['retryable']
    assert not client.operation_read_failure(generic, {'http_status': 404})['retryable']
    assert client.operation_read_failure(generic, {'http_status': 503})['retryable']


@pytest.mark.parametrize('status', [400, 401, 403, 404, 422])
def test_permanent_handshake_errors_cannot_spin(tmp_path, monkeypatch, status):
    args, _, previous, calls, sessions, delays = resumed_run(tmp_path, monkeypatch, [status],
                                                           fault_tool='initialize')
    with pytest.raises(Exception):
        asyncio.run(client.run(args))
    assert not calls and not delays and len(sessions) == 1
    receipt = client.load_receipt(args.output / 'receipt.json')
    assert receipt['state'] == 'running' and receipt['operation_id'] == OPERATION
    assert client.load_receipt(args.output / 'status.json') == previous


def test_transient_handshake_can_reconnect_without_submission(tmp_path, monkeypatch):
    args, _, _, calls, sessions, _ = resumed_run(tmp_path, monkeypatch, [503], fault_tool='initialize')
    assert asyncio.run(client.run(args))['state'] == 'verified'
    assert len(sessions) == 2
    assert calls == ['get_scientific_status', 'get_scientific_result', 'artifact-read']


def test_ambiguous_mutation_is_never_retried_by_observation_policy(tmp_path, monkeypatch):
    args = argparse.Namespace(source=tmp_path / 'input', parameters=tmp_path / 'parameters',
        output=tmp_path / 'new', model='fixture', tool='submit_fixture', operation='simulate',
        idempotency_key='original-new-admission', media_type='application/json', compression='none',
        entry_name='input', semantic_type='fixture/v1', service_class='customer-batch', display_name='fixture')
    args.source.write_text('{}')
    args.parameters.write_text('{}')
    calls = []
    class Context:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name=args.tool,
                input_schema={'type': 'object', 'properties': {'parameters': {'type': 'object'}}},
                model_dump=lambda **kwargs: {'name': args.tool})])
    async def rpc(connection, name, arguments):
        calls.append(name)
        if name == 'get_model_schema':
            return {'contracts': [{'protocol': 'scientific-batch-v1'}]}
        assert name == args.tool
        raise MCPError(INTERNAL_ERROR, 'Server returned an error response')
    async def upload(http, model, source, media_type, compression, key):
        calls.append('upload')
        return {'artifact_id': 'source' if key.endswith('-source') else 'manifest',
                'sha256': client.digest(source), 'size_bytes': len(source),
                'media_type': media_type, 'compression': compression}
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.example/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-key')
    monkeypatch.setattr(client.httpx2, 'AsyncClient', lambda **kwargs: Context())
    monkeypatch.setattr(client, 'streamable_http_client', lambda *args, **kwargs: None)
    monkeypatch.setattr(client, 'Client', lambda *args, **kwargs: Context())
    monkeypatch.setattr(client, 'call', rpc)
    monkeypatch.setattr(client, 'upload', upload)
    with pytest.raises(MCPError):
        asyncio.run(client.run(args))
    assert calls == ['get_model_schema', 'upload', 'upload', 'submit_fixture']
    receipt = client.load_receipt(args.output / 'receipt.json')
    assert receipt['state'] == 'admission_unknown' and 'operation_id' not in receipt
    with pytest.raises(RuntimeError, match='ambiguous'):
        asyncio.run(client.run(args))
    assert calls == ['get_model_schema', 'upload', 'upload', 'submit_fixture']
