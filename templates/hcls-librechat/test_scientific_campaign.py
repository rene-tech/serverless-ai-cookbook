"""Portable campaigns retain the existing admission and observation owner."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('campaign', ROOT / 'scripts/scientific-campaign.py')
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)
batch = campaign.batch


def prepared(tmp_path, count, *, seed=8100, chunk_size=64):
    source, parameters = tmp_path / 'source.txt', tmp_path / 'parameters.json'
    source.write_text('Unconditional backbone campaign; no binding claim.\n')
    parameters.write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/rfdiffusion-parameters/v1',
        'operation': 'design-backbone', 'contigs': ['80-80'], 'num_designs': 1,
        'seed': seed, 'diffuser_T': 50}))
    args = argparse.Namespace(designs=count, chunk_size=chunk_size, source=source, parameters=parameters,
        operation='design-backbone', idempotency_key='research-campaign-001',
        display_name='Backbone campaign', service_class='customer-batch', media_type='text/plain',
        compression='none', entry_name='design_constraint',
        semantic_type='rfdiffusion-design-constraint/v1', output=tmp_path / 'campaign',
        source_artifact=None, action='run', wait_seconds=0, poll_seconds=0)
    campaign.plan_campaign(args)
    return args


@pytest.mark.parametrize('count,sizes', [(1, [1]), (64, [64]), (65, [64, 1]),
                                      (1000, [64] * 15 + [40])])
def test_offline_partition_seed_identity_and_immutable_restart(tmp_path, count, sizes):
    args = prepared(tmp_path, count)
    plan = campaign.read_plan(args.output)
    assert [child['parameters']['num_designs'] for child in plan['children']] == sizes
    seeds = [seed for child in plan['children'] for seed in range(child['parameters']['seed'],
             child['parameters']['seed'] + child['parameters']['num_designs'])]
    assert seeds == list(range(8100, 8100 + count))
    keys = [child['idempotency_key'] for child in plan['children']]
    assert len(set(keys)) == len(keys)
    before = (args.output / 'campaign.json').read_bytes()
    campaign.plan_campaign(args)
    assert (args.output / 'campaign.json').read_bytes() == before
    assert not (args.output / 'receipt.json').exists()  # No credentials/admission.
    changed = json.loads(args.parameters.read_text())
    changed['contigs'] = ['90-90']
    args.parameters.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='different immutable campaign'):
        campaign.plan_campaign(args)
    args.output = tmp_path / 'different-science'
    campaign.plan_campaign(args)
    assert campaign.read_plan(args.output)['children'][0]['idempotency_key'] != keys[0]


def test_existing_seed_ceiling_stops_before_plan_or_upload(tmp_path):
    with pytest.raises(ValueError, match='seed range'):
        prepared(tmp_path, 65, seed=1000000 - 63)
    assert not (tmp_path / 'campaign/campaign.json').exists()


def test_bounded_pilot_uses_same_child_contract_without_raising_native_limit(tmp_path):
    args = prepared(tmp_path, 3, chunk_size=2)
    assert [c['parameters']['num_designs'] for c in campaign.read_plan(args.output)['children']] == [2, 1]
    with pytest.raises(ValueError, match='1..64'):
        campaign.children({**campaign.read_plan(args.output)['identity'], 'chunk_size': 65})


class Transport:
    """Synthetic server outcomes around the REAL batch run/admit/receipt code."""
    def __init__(self, monkeypatch, *, entry=None):
        self.uploads, self.submissions, self.observations = [], [], []
        self.unknown, self.pending, self.failed = set(), set(), set()
        self.ids = {}
        self.entry = entry or {'name': 'design_constraint',
                              'semantic_type': 'rfdiffusion-design-constraint/v1',
                              'media_type': 'text/plain', 'compression': 'none'}
        schema = {'type': 'object', 'required': ['parameters', 'idempotency_key'],
            'properties': {'parameters': {'type': 'object', 'required': ['num_designs', 'seed'],
                'properties': {'num_designs': {'type': 'integer', 'minimum': 1, 'maximum': 64},
                               'seed': {'type': 'integer', 'minimum': 0, 'maximum': 1000000}}},
                'idempotency_key': {'type': 'string'}}}
        tool = SimpleNamespace(name='submit_rfdiffusion', input_schema=schema,
                               model_dump=lambda **kwargs: {'name': 'submit_rfdiffusion',
                                                            'inputSchema': schema})
        class Context:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def list_tools(self): return SimpleNamespace(tools=[tool])
        monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://fixture.invalid/mcp')
        monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-test-only-key')
        monkeypatch.setattr(batch.httpx2, 'AsyncClient', lambda **kwargs: Context())
        monkeypatch.setattr(batch, 'streamable_http_client', lambda *args, **kwargs: None)
        monkeypatch.setattr(batch, 'Client', lambda *args, **kwargs: Context())
        monkeypatch.setattr(batch, 'call', self.call)
        monkeypatch.setattr(batch, 'upload', self.upload)
        monkeypatch.setattr(batch, 'observe_operation', self.observe)

    async def call(self, client, name, arguments):
        if name == 'get_model_schema':
            return {'contracts': [{'protocol': 'scientific-batch-v1'}],
                'input_artifact_contract': {'entry': self.entry}}
        assert name == 'submit_rfdiffusion'
        self.submissions.append(arguments)
        key = arguments['idempotency_key']
        if key in self.unknown:
            raise RuntimeError('Synthetic lost acknowledgement; outcome remains unknown.')
        operation = self.ids.setdefault(key, f'op-fixture-{len(self.ids):06d}')
        return {'operation_id': operation, 'model_id': 'rfdiffusion', 'status': 'QUEUED',
                'operation': {'operation_id': operation, 'status': 'queued', 'result_available': False}}

    async def upload(self, http, model, data, media_type, compression, key):
        self.uploads.append((media_type, key))
        return {'artifact_id': f'artifact-{len(self.uploads)}', 'sha256': batch.digest(data),
                'size_bytes': len(data), 'media_type': media_type, 'compression': compression}

    async def observe(self, args, http, endpoint, headers, receipt, receipt_path, **kwargs):
        self.observations.append(receipt['operation_id'])
        key = receipt['identity']['idempotency_key']
        if key in self.failed:
            receipt['state'] = 'failed'
            batch.save(receipt_path, receipt)
            raise batch.ScientificOperationFailed(receipt, args.output)
        receipt['state'] = 'queued' if key in self.pending else 'verified'
        if receipt['state'] == 'verified':
            receipt.update(output_manifest={'sha256': 'a' * 64, 'size_bytes': 12,
                                             'artifact_id': 'manifest-' + receipt['operation_id']},
                           verified_artifacts=[])
        batch.save(receipt_path, receipt)
        return receipt


def test_real_receipt_executor_reuses_one_source_and_verified_outputs(tmp_path, monkeypatch):
    args = prepared(tmp_path, 65)
    transport = Transport(monkeypatch)
    result = asyncio.run(campaign.execute(args))
    assert result['state'] == 'verified'
    assert result['design_counts']['submitted'] == result['design_counts']['succeeded'] == 65
    assert len(transport.submissions) == 2
    assert [kind for kind, _ in transport.uploads].count('text/plain') == 1
    assert len(transport.uploads) == 3  # One source, one manifest per exact request.
    references = [child['source_artifact'] for child in result['children']]
    assert references[0] == references[1]
    assert all(child['operation_id'] for child in result['children'])
    assert result['cost'] is None
    observed = list(transport.observations)
    args.source.unlink()  # Completed receipts do not depend on retaining input paths.
    asyncio.run(campaign.execute(args))
    assert len(transport.submissions) == 2 and len(transport.uploads) == 3
    assert transport.observations == observed  # No re-download of verified children.


def test_unknown_fences_new_children_but_known_sibling_is_observed(tmp_path, monkeypatch):
    args = prepared(tmp_path, 193)
    plan = campaign.read_plan(args.output)
    transport = Transport(monkeypatch)
    first, _, third, _ = plan['children']
    transport.unknown.add(first['idempotency_key'])
    with pytest.raises(RuntimeError, match='lost acknowledgement'):
        asyncio.run(campaign.execute(args))
    assert len(transport.submissions) == 1
    summary = batch.load_receipt(args.output / 'summary.json')
    assert summary['design_counts']['unknown'] == 64
    # A retained accepted sibling is observed even while another ACK is unknown.
    local = campaign.child_args(args, plan, third)
    transport.pending.add(third['idempotency_key'])
    asyncio.run(batch.run(local))
    third_id = batch.load_receipt(local.output / 'receipt.json')['operation_id']
    transport.pending.clear()
    with pytest.raises(RuntimeError, match='lost acknowledgement'):
        asyncio.run(campaign.execute(args))
    assert transport.observations.count(third_id) == 2
    assert {r['idempotency_key'] for r in transport.submissions} == {
        first['idempotency_key'], third['idempotency_key']}
    # Explicit resume reconciles the SAME request/key, not a replacement.
    original = transport.submissions[0]
    transport.unknown.clear()
    result = asyncio.run(campaign.execute(args))
    assert transport.submissions[-1] == original
    assert result['design_counts']['not_submitted'] == 65
    result = asyncio.run(campaign.execute(args))
    assert result['state'] == 'verified' and result['design_counts']['succeeded'] == 193
    assert [kind for kind, _ in transport.uploads].count('text/plain') == 1


def test_failure_and_manual_stop_never_replay_or_cancel_accepted_science(tmp_path, monkeypatch):
    args = prepared(tmp_path, 65)
    transport = Transport(monkeypatch)
    first = campaign.read_plan(args.output)['children'][0]
    transport.failed.add(first['idempotency_key'])
    with pytest.raises(batch.ScientificOperationFailed):
        asyncio.run(campaign.execute(args))
    result = asyncio.run(campaign.execute(args))
    assert result['design_counts']['failed'] == 64 and len(transport.submissions) == 1
    args.action = 'stop'
    assert asyncio.run(campaign.execute(args))['admission_stopped']
    args.action = 'run'
    asyncio.run(campaign.execute(args))
    assert len(transport.submissions) == 1


def test_changed_caller_or_plan_cannot_adopt_campaign(tmp_path, monkeypatch):
    args = prepared(tmp_path, 1)
    transport = Transport(monkeypatch)
    asyncio.run(campaign.execute(args))
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'another-synthetic-owner')
    with pytest.raises(ValueError, match='different plan, endpoint or caller'):
        asyncio.run(campaign.execute(args))
    assert len(transport.submissions) == 1
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-test-only-key')
    plan = campaign.read_plan(args.output)
    plan['source_path'] = str(tmp_path / 'another-location.txt')
    (args.output / 'campaign.json').write_text(json.dumps(plan))
    with pytest.raises(ValueError, match='different plan, endpoint or caller'):
        asyncio.run(campaign.execute(args))


def test_stop_fences_new_chunks_after_accepted_work_finishes(tmp_path, monkeypatch):
    args = prepared(tmp_path, 65)
    transport = Transport(monkeypatch)
    first = campaign.read_plan(args.output)['children'][0]
    transport.pending.add(first['idempotency_key'])
    asyncio.run(campaign.execute(args))
    observed = list(transport.observations)
    args.action = 'stop'
    asyncio.run(campaign.execute(args))
    assert transport.observations == observed  # Stop is local, not a remote control.
    transport.pending.clear()
    args.action = 'run'
    result = asyncio.run(campaign.execute(args))
    assert result['design_counts']['succeeded'] == 64
    assert result['design_counts']['not_submitted'] == 1
    assert len(transport.submissions) == 1


def test_changed_source_preserves_accepted_result_but_fences_later_admission(tmp_path, monkeypatch):
    args = prepared(tmp_path, 65)
    transport = Transport(monkeypatch)
    first = campaign.read_plan(args.output)['children'][0]
    transport.pending.add(first['idempotency_key'])
    asyncio.run(campaign.execute(args))
    transport.pending.clear()
    args.source.write_text('Changed scientific input')
    with pytest.raises(ValueError, match='source changed'):
        asyncio.run(campaign.execute(args))
    receipt = batch.load_receipt(args.output / first['id'] / 'receipt.json')
    assert receipt['state'] == 'verified' and len(transport.submissions) == 1


def test_worked_existing_study_uses_current_schema_and_nonoverlapping_seeds(tmp_path):
    from jsonschema import Draft202012Validator
    schema_spec = importlib.util.spec_from_file_location('study_schema', ROOT / 'scientific_study_schema.py')
    schema = importlib.util.module_from_spec(schema_spec)
    schema_spec.loader.exec_module(schema)
    guide = (ROOT.parents[1] / 'skills/scientific-ai/binder-design-campaigns/references/rfdiffusion-study.md').read_text()
    code = guide.split('```python\n', 1)[1].split('```', 1)[0]
    code = code.replace("Path('/workspace/rfdiffusion-campaign')", f'Path({str(tmp_path)!r})')
    scope = {}
    exec(compile(code, 'worked-existing-study', 'exec'), scope)
    plan = scope['plan']
    Draft202012Validator(schema.STUDY_SCHEMA).validate(plan)
    parameters = [json.loads(Path(step['parameters']).read_text()) for step in plan['steps']]
    assert [p['num_designs'] for p in parameters] == [64, 1]
    assert [p['seed'] for p in parameters] == [8100, 8164]
    assert len({step['idempotency_key'] for step in plan['steps']}) == 2
    assert len({step['source_artifact'] for step in plan['steps']}) == 1


def test_binder_campaign_requires_actual_finalized_target_id_and_reuses_it(tmp_path, monkeypatch):
    args = prepared(tmp_path, 3, chunk_size=2)
    args.output = tmp_path / 'binder-campaign'
    args.operation, args.media_type = 'scaffold-motif', 'chemical/x-pdb'
    args.entry_name, args.semantic_type = 'target_structure', 'protein-structure-pdb/v1'
    reference = {'artifact_id': 'actual-uploaded-target', 'sha256': batch.FileSource(args.source).sha256,
                 'size_bytes': args.source.stat().st_size, 'media_type': args.media_type,
                 'compression': 'none'}
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'inputs').mkdir()
    artifact_path = tmp_path / 'runs/binder-target-001/artifact.json'
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(json.dumps(reference))
    guide = (ROOT.parents[1] / 'skills/scientific-ai/scientific-gateway/references/portable-campaign.md').read_text()
    code = guide.split('```python\n', 1)[1].split('```', 1)[0]
    exec(compile(code, 'worked-binder-campaign', 'exec'), {})
    parameters = json.loads((tmp_path / 'inputs/binder-parameters.json').read_text())
    assert parameters['input_pdb_artifact_id'] == reference['artifact_id']
    args.parameters.write_text(json.dumps(parameters))
    with pytest.raises(ValueError, match='Finalize the target first'):
        campaign.plan_campaign(args)
    args.source_artifact = tmp_path / 'uploaded-target.json'
    args.source_artifact.write_text(json.dumps({**reference, 'sha256': '0' * 64}))
    with pytest.raises(ValueError, match='exact source bytes'):
        campaign.plan_campaign(args)
    args.source_artifact.write_text(json.dumps(reference))
    args.parameters.write_text(json.dumps({**parameters, 'input_pdb_artifact_id': 'target_structure'}))
    with pytest.raises(ValueError, match='same actual uploaded PDB'):
        campaign.plan_campaign(args)
    args.parameters.write_text(json.dumps(parameters))
    campaign.plan_campaign(args)
    transport = Transport(monkeypatch, entry={'name': args.entry_name, 'semantic_type': args.semantic_type,
        'media_type': args.media_type, 'compression': args.compression})
    saved = args.output / 'source-artifact.json'
    original_reference_bytes = saved.read_bytes()
    saved.write_text(json.dumps({**reference, 'artifact_id': 'drifted-target'}))
    with pytest.raises(ValueError, match='Finalized target reference differs'):
        asyncio.run(campaign.execute(args))
    assert not transport.uploads and not transport.submissions
    saved.write_bytes(original_reference_bytes)
    result = asyncio.run(campaign.execute(args))
    assert result['state'] == 'verified'
    assert [request['parameters']['input_pdb_artifact_id'] for request in transport.submissions] == [
        reference['artifact_id'], reference['artifact_id']]
    assert len(transport.uploads) == 2  # Child manifests only, never upload the target again.


def test_failed_science_keeps_independent_typed_slot_evidence(tmp_path, monkeypatch):
    args = prepared(tmp_path, 65)
    transport = Transport(monkeypatch)
    plan = campaign.read_plan(args.output)
    first = plan['children'][0]
    transport.failed.add(first['idempotency_key'])
    with pytest.raises(batch.ScientificOperationFailed):
        asyncio.run(campaign.execute(args))
    owner = batch.load_receipt(args.output / 'receipt.json')['identity']
    local = campaign.child_args(args, plan, first)
    receipt = batch.load_receipt(local.output / 'receipt.json')
    operation_id = receipt['operation_id']
    status = {'operation_id': operation_id, 'model_id': 'rfdiffusion', 'status': 'FAILED',
              'operation': {'operation_id': operation_id, 'status': 'failed', 'result_available': False},
              'graph': {'action_required': True},
              'error': {'code': 'MODEL_EXECUTION_FAILED', 'admission_slot_held': True}}
    batch.save(local.output / 'status.json', status)
    summary = campaign.project(args, plan, owner)
    assert summary['design_counts']['failed'] == 64 and summary['design_counts']['held'] == 0
    assert summary['children'][0]['admission_slot_held'] is True
    assert summary['children'][1]['admission_slot_held'] is None
    assert 'status.json' in summary['children'][0]['request_runtime_result_references']
    del status['error']['admission_slot_held']
    batch.save(local.output / 'status.json', status)
    assert campaign.project(args, plan, owner)['children'][0]['admission_slot_held'] is True
    status['graph']['action_required'] = False
    batch.save(local.output / 'status.json', status)
    assert campaign.project(args, plan, owner)['children'][0]['admission_slot_held'] is None
    status['error']['admission_slot_held'] = False
    batch.save(local.output / 'status.json', status)
    assert campaign.project(args, plan, owner)['children'][0]['admission_slot_held'] is False
    status['operation_id'] = 'op-another-child'
    batch.save(local.output / 'status.json', status)
    assert campaign.project(args, plan, owner)['children'][0]['admission_slot_held'] is None
    assert len(transport.submissions) == 1  # Projection never releases or repeats science.
