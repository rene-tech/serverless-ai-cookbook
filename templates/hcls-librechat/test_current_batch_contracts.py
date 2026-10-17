"""Current batch families: exact published schemas, native status and lost ACKs.

The JSON fixtures are generated from gateway.Submit / the staged compiler, not
invented shared envelopes. The optional source comparison runs in backend CI.
No server, customer identity or inference is used by these transport tests.
"""
import argparse
import asyncio
import copy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, ValidationError

from test_scientific_batch_client import client

CONTRACTS = json.loads((Path(__file__).parent / 'tests/fixtures/current-batch-contracts.json').read_text())
OP = 'op-batch-current-1'


def parameters(model):
    if model == 'gromacs':
        return {'schema': 'fs2-serve.nebius.ai/gromacs-workflow-request/v1',
                'jobs': [{'id': 'md', 'steps': [{'id': 'simulate', 'command': 'mdrun',
                                               'args': ['-s', 'simulation.tpr']}]}]}
    return {'checkpoint': 'protenix-v2', 'msa_mode': 'none', 'sample_count': 1, 'model_seeds': [7]}


def status(model, state='QUEUED'):
    # Gateway._status and StageGateway.status both expose this current shape.
    # Neither echoes the idempotency key or protocol inside operation.
    return {'id': OP, 'operation_id': OP, 'model_id': model, 'status': state, 'state': state.lower(),
            'operation': {'operation_id': OP, 'status': state.lower(),
                          'result_available': state == 'SUCCEEDED'}}


def setup_submission(tmp_path, monkeypatch, model):
    contract = CONTRACTS[model]
    args = argparse.Namespace(model=model, tool=contract['tool_name'],
        operation='run-workflow' if model == 'gromacs' else 'predict-complex-structure',
        source=tmp_path / 'source', parameters=tmp_path / 'parameters.json', output=tmp_path / 'run',
        media_type='application/gzip' if model == 'gromacs' else 'application/json',
        compression='gzip' if model == 'gromacs' else 'none', entry_name='scientific-input',
        semantic_type='fixture/v1', idempotency_key='retained-submission-key',
        service_class='customer-batch', display_name='Internal contract test', wait_seconds=0, poll_seconds=0)
    args.source.write_bytes(gzip.compress(b'synthetic native bytes') if model == 'gromacs' else b'{}')
    args.parameters.write_text(json.dumps(parameters(model)))
    calls, uploads = [], []
    class Context:
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return False
        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name=args.tool, input_schema=contract['input_schema'],
                model_dump=lambda **kwargs: {'name': args.tool, 'inputSchema': contract['input_schema']})])
    async def call(connection, name, arguments):
        calls.append((name, copy.deepcopy(arguments)))
        if name == 'get_model_schema':
            assert arguments == {'model_id': model, 'protocol': 'scientific-batch-v1', 'tool_name': args.tool}
            return {'model_id': model, 'contracts': [{'protocol': 'scientific-batch-v1', **contract}]}
        if name == args.tool:
            Draft202012Validator(contract['input_schema']).validate(arguments)
            assert ('request' in arguments) == (model == 'gromacs')
        else:
            assert name == 'get_operation' and arguments == {'operation_id': OP}
        return status(model)
    async def upload(http, model_id, source, media_type, compression, key):
        uploads.append(key)
        return {'artifact_id': '00000000-0000-4000-8000-' + str(len(uploads)).zfill(12),
                'sha256': client.digest(source), 'size_bytes': len(source),
                'media_type': media_type, 'compression': compression}
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://internal.example/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-owner-key')
    monkeypatch.setattr(client.httpx2, 'AsyncClient', lambda **kwargs: Context())
    monkeypatch.setattr(client, 'streamable_http_client', lambda *args, **kwargs: None)
    monkeypatch.setattr(client, 'Client', lambda *args, **kwargs: Context())
    monkeypatch.setattr(client, 'call', call)
    monkeypatch.setattr(client, 'upload', upload)
    return args, calls, uploads


@pytest.mark.parametrize('model', CONTRACTS)
def test_exact_current_schema_submission_and_native_status(tmp_path, monkeypatch, model):
    args, calls, uploads = setup_submission(tmp_path, monkeypatch, model)
    receipt = asyncio.run(client.run(args))
    assert receipt['operation_id'] == OP and receipt['state'] == 'queued'
    assert [name for name, _ in calls] == ['get_model_schema', args.tool, 'get_operation']
    assert len(uploads) == 2
    request = client.load_receipt(args.output / 'request.json')
    assert ('request' in request) == (model == 'gromacs')
    ack = client.load_receipt(args.output / 'admission.json')
    assert ack['binding'] == client.admission_binding(args, receipt)
    assert ack['response'] == status(model)
    assert 'synthetic-owner-key' not in json.dumps(ack)
    # The wrong family's envelope is invalid, never retried as a fallback.
    wrong = ({**request['request'], 'idempotency_key': args.idempotency_key} if model == 'gromacs'
             else {'request': request, 'idempotency_key': args.idempotency_key})
    with pytest.raises(ValidationError):
        Draft202012Validator(CONTRACTS[model]['input_schema']).validate(wrong)


@pytest.mark.parametrize('model', CONTRACTS)
def test_current_families_preflight_reject_before_any_upload(tmp_path, monkeypatch, model):
    args, calls, uploads = setup_submission(tmp_path, monkeypatch, model)
    args.parameters.write_text('{}')
    with pytest.raises(client.ParameterPreflightError):
        asyncio.run(client.run(args))
    assert [name for name, _ in calls] == ['get_model_schema'] and uploads == []


@pytest.mark.parametrize('model', CONTRACTS)
def test_saved_ack_recovers_after_receipt_write_loss_without_resubmitting(tmp_path, monkeypatch, model):
    args, calls, uploads = setup_submission(tmp_path, monkeypatch, model)
    save = client.save
    def interrupted(path, value):
        if path.name == 'receipt.json' and value.get('operation_id'):
            raise OSError('synthetic power loss after ACK publication')
        return save(path, value)
    monkeypatch.setattr(client, 'save', interrupted)
    with pytest.raises(OSError, match='power loss'):
        asyncio.run(client.run(args))
    assert client.load_receipt(args.output / 'receipt.json')['state'] == 'submitting'
    monkeypatch.setattr(client, 'save', save)
    recovered = asyncio.run(client.run(args))
    assert recovered['operation_id'] == OP and recovered['recovered_saved_admission']
    assert [name for name, _ in calls].count(args.tool) == 1 and len(uploads) == 2
    assert calls[-1] == ('get_operation', {'operation_id': OP})


@pytest.mark.parametrize('model', CONTRACTS)
def test_lost_response_without_ack_never_resubmits(tmp_path, monkeypatch, model):
    args, calls, uploads = setup_submission(tmp_path, monkeypatch, model)
    call = client.call
    async def disconnected(connection, name, arguments):
        result = await call(connection, name, arguments)
        if name == args.tool:
            raise client.httpx2.ReadError('synthetic lost response')
        return result
    monkeypatch.setattr(client, 'call', disconnected)
    with pytest.raises(client.httpx2.ReadError):
        asyncio.run(client.run(args))
    assert client.load_receipt(args.output / 'receipt.json')['state'] == 'admission_unknown'
    original_calls = copy.deepcopy(calls)
    with pytest.raises(RuntimeError, match='ambiguous'):
        asyncio.run(client.run(args))
    assert calls == original_calls and len(uploads) == 2


@pytest.mark.parametrize('model', CONTRACTS)
@pytest.mark.parametrize('terminal', ['TIMED_OUT', 'EXPORT_FAILED'])
def test_native_terminal_failures_stop_instead_of_polling_forever(tmp_path, monkeypatch, model, terminal):
    args, calls, uploads = setup_submission(tmp_path, monkeypatch, model)
    call = client.call
    async def terminal_status(connection, name, arguments):
        result = await call(connection, name, arguments)
        return status(model, terminal) if name == 'get_operation' else result
    monkeypatch.setattr(client, 'call', terminal_status)
    with pytest.raises(RuntimeError, match=terminal.lower()):
        asyncio.run(client.run(args))
    receipt = client.load_receipt(args.output / 'receipt.json')
    assert receipt['state'] == terminal.lower() and receipt['operation_id'] == OP
    assert [name for name, _ in calls] == ['get_model_schema', args.tool, 'get_operation']
    assert len(uploads) == 2


@pytest.mark.parametrize('model', CONTRACTS)
@pytest.mark.parametrize('change', ['owner', 'model', 'key', 'operation', 'tool', 'request', 'response', 'missing'])
def test_ack_requires_exact_caller_request_and_current_response(tmp_path, monkeypatch, model, change):
    args, calls, uploads = setup_submission(tmp_path, monkeypatch, model)
    receipt = asyncio.run(client.run(args))
    receipt.pop('operation_id')
    receipt['state'] = 'submitting'
    ack = client.load_receipt(args.output / 'admission.json')
    if change in {'owner', 'model', 'key'}:
        field = {'owner': 'caller_fingerprint', 'model': 'model_id', 'key': 'idempotency_key'}[change]
        receipt['identity'][field] = 'not-the-original'
    elif change in {'operation', 'tool'}:
        setattr(args, change, 'different')
    elif change == 'request':
        request = client.load_receipt(args.output / 'request.json')
        request['idempotency_key'] = 'different-request-key'
        client.save(args.output / 'request.json', request)
    elif change == 'response':
        ack['response']['model_id'] = 'different-model'
        client.save(args.output / 'admission.json', ack)
    else:
        # A raw response is evidence, but is not a request-bound ACK.
        client.save(args.output / 'admission.json', ack['response'])
    with pytest.raises(RuntimeError, match='ambiguous'):
        client.recover_saved_admission(args, receipt)
    assert [name for name, _ in calls].count(CONTRACTS[model]['tool_name']) == 1 and len(uploads) == 2


@pytest.mark.parametrize('change', ['top-id', 'nested-id', 'model', 'state', 'old-id', 'published'])
def test_status_rejects_mixed_identity_and_noncurrent_shape(change):
    document = status('gromacs')
    if change == 'top-id': document['operation_id'] = 'op-someone-else'
    elif change == 'nested-id': document['operation']['operation_id'] = 'op-someone-else'
    elif change == 'model': document['model_id'] = 'other-model'
    elif change == 'state': document['operation']['status'] = 'succeeded'
    elif change == 'published': document['operation']['result_available'] = 'true'
    else: document['operation']['id'] = document['operation'].pop('operation_id')
    with pytest.raises(ValueError):
        client.batch_operation(document, operation_id=OP, model_id='gromacs')


def test_current_pending_admission_is_observable_not_permission_to_resubmit():
    document = {'operation_id': OP, 'model_id': 'protenix-v2', 'status': 'ADMISSION_PENDING',
                'state': 'admission-unknown', 'retry_same_idempotency_key': True}
    assert client.batch_operation(document) == {'operation_id': OP, 'status': 'admission_pending',
                                               'result_available': False}


def test_fixture_schemas_match_current_backend_sources_when_available():
    pytest.importorskip('scientific_ai')
    from scientific_ai.gateway import Submit
    from scientific_ai.scientific_stages.compiler import request_schema, profile
    from mcp.server.mcpserver.utilities.func_metadata import func_metadata
    def submit_gromacs_workflow(request: Submit, idempotency_key: str): pass
    assert func_metadata(submit_gromacs_workflow).arg_model.model_json_schema() == CONTRACTS['gromacs']['input_schema']
    assert request_schema('protenix-v2', surface='mcp') == CONTRACTS['protenix-v2']['input_schema']
    assert profile('protenix-v2')['interface']['mcp']['tool_name'] == CONTRACTS['protenix-v2']['tool_name']


def test_all_current_backend_families_select_without_model_name_heuristics():
    pytest.importorskip('scientific_ai')
    from scientific_ai.gateway import Submit
    from scientific_ai.native_md_gateway import submission_type as md_type
    from scientific_ai.scvi_gateway import submission_type as scvi_type
    from scientific_ai.gromacs_mpi.gateway_contract import submission_type as mpi_type
    from scientific_ai.scientific_stages.compiler import CANONICAL, request_schema
    from mcp.server.mcpserver.utilities.func_metadata import func_metadata
    for request_type in [Submit, scvi_type(Submit), mpi_type(Submit),
                         *(md_type(engine, Submit) for engine in ('amber', 'namd', 'lammps'))]:
        def submit(request, idempotency_key: str): pass
        submit.__annotations__['request'] = request_type
        schema = func_metadata(submit).arg_model.model_json_schema()
        assert client.submission_contract(schema)[0] is True
    for model in set(CANONICAL.values()):
        assert client.submission_contract(request_schema(model, surface='mcp'))[0] is False


@pytest.mark.parametrize('schema', [
    {'properties': {}},
    {'properties': {'request': {}, 'parameters': {}}},
    {'properties': {'request': {'$ref': '#/$defs/self'}}, '$defs': {'self': {'$ref': '#/$defs/self'}}},
])
def test_missing_ambiguous_and_cyclic_schemas_never_select_an_alternate_shape(schema):
    with pytest.raises((ValueError, RuntimeError)):
        client.submission_contract(schema)
