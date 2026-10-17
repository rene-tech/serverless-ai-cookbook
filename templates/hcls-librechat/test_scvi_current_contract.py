"""Run the shipped scVI REST/MCP clients against one current contract, offline."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest


ROOT = Path(__file__).with_name('scvi-client')


def module(name):
    spec = importlib.util.spec_from_file_location('current_scvi_' + name, ROOT / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize('lose_finalize', [False, True])
def test_upload_uses_upload_identity_and_recovers_lost_finalization(tmp_path, monkeypatch, lose_finalize):
    api = module('qualify_api')
    source = tmp_path / 'counts.h5ad'
    source.write_bytes(b'opaque HDF5 upload transport fixture')
    output = tmp_path / 'upload'
    calls, stored = [], {}
    fail_next = lose_finalize
    upload_id = '12345678-1234-4234-8234-123456789abc'
    reference = {'artifact_id': upload_id, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                 'size_bytes': source.stat().st_size, 'media_type': 'application/x-hdf5', 'compression': 'none'}

    def route(request):
        nonlocal fail_next
        calls.append((request.method, request.url.path))
        assert '/v1/operations/' not in request.url.path
        if request.method == 'GET':
            assert request.url.path == '/v1/me'
            return httpx.Response(200, json={'tenant_id': 'system', 'principal_id': 'qa'})
        if request.url.path == '/v1/scientific-artifacts/uploads':
            return httpx.Response(200, json={'upload_id': upload_id,
                'handle': {'headers': {'If-None-Match': '*'}, 'url': 'https://objects.test/input'}})
        if request.method == 'PUT':
            assert 'authorization' not in request.headers
            payload = request.read()
            if stored:
                return httpx.Response(412)
            stored['payload'] = payload
            return httpx.Response(200)
        assert request.url.path == '/v1/scientific-artifacts/uploads/' + upload_id + ':finalize'
        assert json.loads(request.content) == {}
        if fail_next:
            fail_next = False
            return httpx.Response(503, json={'error': 'lost finalize response'})
        assert hashlib.sha256(stored['payload']).hexdigest() == reference['sha256']
        return httpx.Response(200, json={'state': 'finalized', 'artifact': reference})

    original = httpx.Client
    monkeypatch.setattr(api.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(route), **kw))
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'internal-test-fixture')
    monkeypatch.setattr(sys, 'argv', ['scvi', '--origin', 'https://api.test', '--input', str(source),
                                   '--output', str(output), '--stage-only'])
    if lose_finalize:
        with pytest.raises(RuntimeError, match='HTTP 503'):
            api.main(require_qa=False)
    api.main(require_qa=False)
    assert json.loads((output / 'anndata-artifact.json').read_text()) == reference
    assert json.loads((output / 'anndata-upload.json').read_text()) == {'upload_id': upload_id}
    assert sum(method == 'PUT' for method, _ in calls) == 1


def test_mcp_submission_and_polling_use_one_current_contract(tmp_path, monkeypatch):
    hosted = module('qualify_hosted')
    request_path = tmp_path / 'request.json'
    body = {'schema': 'fs2-serve.nebius.ai/scientific-run-request/v1', 'parameters': {'fixture': True}}
    request_path.write_text(json.dumps(body))
    calls, submissions = [], []
    operation_id = 'op-0123456789abcdef'

    def route(request):
        if request.url.path == '/v1/me':
            return httpx.Response(200, json={'tenant_id': 'system', 'principal_id': 'qa'})
        assert request.url.path == '/mcp'
        rpc = json.loads(request.content)
        if rpc['method'] == 'notifications/initialized':
            return httpx.Response(202)
        if rpc['method'] == 'initialize':
            result = {'protocolVersion': '2025-06-18', 'capabilities': {}, 'serverInfo': {'name': 'fixture', 'version': '1'}}
        elif rpc['method'] == 'tools/list':
            result = {'tools': [{'name': 'submit_scvi_scanvi', 'inputSchema': {'properties': {'request': {'type': 'object'}}}}]}
        else:
            params = rpc['params']
            calls.append(params['name'])
            if params['name'] == 'submit_scvi_scanvi':
                assert params['arguments'] == {'request': body, 'idempotency_key': 'current-contract-fixture'}
                submissions.append(params['arguments'])
                value = {'operation': {'id': operation_id, 'reused': len(submissions) > 1}}
            elif params['name'] == 'get_operation':
                assert params['arguments'] == {'operation_id': operation_id}
                value = {'operation': {'id': operation_id, 'status': 'succeeded', 'result_available': True}}
            else:
                assert params['name'] == 'get_operation_result'
                value = {'operation_id': operation_id, 'status': 'succeeded'}
            result = {'structuredContent': value, 'content': []}
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': rpc['id'], 'result': result})

    original = httpx.Client
    monkeypatch.setattr(hosted.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(route), **kw))
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'internal-test-fixture')
    monkeypatch.setattr(sys, 'argv', ['scvi', '--origin', 'https://api.test', '--request', str(request_path),
        '--output', str(tmp_path / 'run'), '--protocol', 'mcp', '--idempotency-key', 'current-contract-fixture'])
    hosted.main(require_qa=False)
    assert calls == ['submit_scvi_scanvi', 'submit_scvi_scanvi', 'get_operation', 'get_operation_result']


@pytest.mark.parametrize('value', [{'artifact_id': 'old-flat'}, {'state': 'finalized', 'artifact': {'sha256': 'wrong', 'size_bytes': 1}}])
def test_finalize_rejects_old_envelope_and_wrong_bytes(value):
    api = module('qualify_api')
    class Client:
        def post(self, *args, **kwargs):
            return httpx.Response(200, json=value)
    with pytest.raises(ValueError):
        api.finalized_artifact(Client(), 'upload-fixture', 'a' * 64, 1)
