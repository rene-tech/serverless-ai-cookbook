#!/usr/bin/env python3
"""Plan and iterate RFdiffusion campaigns with the existing batch receipt owner.

Planning is offline. Run/observe use the same endpoint/key environment as
invoke-scientific-batch.py. No scheduler, concurrency override or native retry
policy is introduced. Each child remains an ordinary request of at most 64
designs. A stopped campaign admits no more children; stopping never cancels
accepted science. Use the existing cancel_operation tool for explicit control.
"""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile


_helper = Path(__file__).with_name('invoke-scientific-batch.py')
if not _helper.is_file():
    _helper = Path(__file__).with_name('scientific-batch-acceptance.py')
_spec = importlib.util.spec_from_file_location('campaign_batch_client', _helper)
batch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(batch)


def freeze(path, document):
    """Reuse the exclusive artifact publisher: identical bytes resume, conflicts stop."""
    raw = batch.canonical(document)
    reference = {'sha256': batch.digest(raw), 'size_bytes': len(raw)}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='scientific-campaign-plan-') as folder:
        staged = Path(folder) / 'document.json'
        staged.write_bytes(raw)
        with staged.open('rb') as stream:
            os.fsync(stream.fileno())
        batch.publish_artifact(staged, path, reference)
    batch.verify_artifact_file(path, reference)


def children(identity):
    count, seed = identity['designs'], identity['parameters'].get('seed')
    chunk_size = identity['chunk_size']
    if type(count) is not int or count < 1:
        raise ValueError('Campaign designs must be a positive integer.')
    if type(chunk_size) is not int or not 1 <= chunk_size <= 64:
        raise ValueError('Chunk size must respect the existing 1..64 request bound.')
    # These are the existing RFdiffusion request/seed bounds, not campaign caps.
    if type(seed) is not int or not 0 <= seed <= 1000000 or seed + count - 1 > 1000000:
        raise ValueError('Campaign seed range exceeds the existing 0..1000000 bound.')
    campaign_id = batch.digest(batch.canonical(identity))
    return [{'id': f'chunk-{index:06d}',
             'idempotency_key': f'campaign-{campaign_id[:24]}-{index:06d}',
             'parameters': {**identity['parameters'], 'seed': seed + offset,
                            'num_designs': min(chunk_size, count - offset)}}
            for index, offset in enumerate(range(0, count, chunk_size))]


def plan_campaign(args):
    source = batch.FileSource(args.source)
    parameters = json.loads(args.parameters.read_text())
    if not isinstance(parameters, dict) or parameters.get('operation') != args.operation:
        raise ValueError('Use the RFdiffusion parameter object for the selected operation.')
    reference = batch.source_reference(args.source_artifact, source, args) if args.source_artifact else None
    if args.operation == 'scaffold-motif' and (
            reference is None or parameters.get('input_pdb_artifact_id') != reference['artifact_id']):
        raise ValueError('Finalize the target first: --source-artifact and input_pdb_artifact_id '
                         'must identify the same actual uploaded PDB. No pointer is substituted.')
    identity = {'model': 'rfdiffusion', 'tool': 'submit_rfdiffusion',
                'operation': args.operation, 'parameters': parameters,
                'designs': args.designs, 'chunk_size': args.chunk_size,
                'campaign_key': args.idempotency_key,
                'display_name': args.display_name, 'service_class': args.service_class,
                'media_type': args.media_type, 'compression': args.compression,
                'entry_name': args.entry_name, 'semantic_type': args.semantic_type,
                'source': {'sha256': source.sha256, 'size_bytes': len(source)}}
    chunks = children(identity)
    plan = {'schema': 'scientific-campaign/v1', 'identity': identity,
            'campaign_sha256': batch.digest(batch.canonical(identity)),
            'source_path': str(args.source.resolve()), 'children': chunks}
    existing = batch.load_receipt(args.output / 'campaign.json')
    if existing is not None and existing != plan:
        raise ValueError('Output directory already contains a different immutable campaign.')
    # Freeze every child before publishing the plan; no network or credentials.
    for child in chunks:
        freeze(args.output / child['id'] / 'parameters.json', child['parameters'])
    if reference:
        freeze(args.output / 'source-artifact.json', reference)
    freeze(args.output / 'campaign.json', plan)
    return {'state': 'planned', 'campaign_sha256': plan['campaign_sha256'],
            'designs': args.designs, 'children': len(chunks), 'output': str(args.output)}


def read_plan(output):
    plan = batch.load_receipt(output / 'campaign.json')
    if (not plan or plan.get('schema') != 'scientific-campaign/v1'
            or plan['identity']['model'] != 'rfdiffusion'
            or plan['identity']['tool'] != 'submit_rfdiffusion'
            or plan['campaign_sha256'] != batch.digest(batch.canonical(plan['identity']))
            or plan['children'] != children(plan['identity'])):
        raise ValueError('Campaign plan identity differs; preserve it, do not infer missing chunks.')
    return plan


def child_args(args, plan, child):
    identity = plan['identity']
    reference = args.output / 'source-artifact.json'
    return argparse.Namespace(**{key: identity[key] for key in
        ('model', 'tool', 'operation', 'media_type', 'compression', 'entry_name',
         'semantic_type', 'service_class')}, source=Path(plan['source_path']),
        parameters=args.output / child['id'] / 'parameters.json',
        output=args.output / child['id'], idempotency_key=child['idempotency_key'],
        display_name=f"{identity['display_name']} / {child['id']}",
        source_artifact=reference if reference.is_file() else None,
        wait_seconds=args.wait_seconds, poll_seconds=args.poll_seconds)


def read_children(args, plan, owner):
    result = []
    for child in plan['children']:
        local = child_args(args, plan, child)
        receipt = batch.load_receipt(local.output / 'receipt.json')
        if receipt:
            expected = {'model_id': plan['identity']['model'],
                        'source_sha256': plan['identity']['source']['sha256'],
                        'parameters_sha256': batch.digest(batch.canonical(child['parameters'])),
                        'endpoint': owner['endpoint'], 'caller_fingerprint': owner['caller_fingerprint'],
                        'idempotency_key': child['idempotency_key']}
            if receipt.get('identity') != expected:
                raise ValueError('Child receipt belongs to a different immutable request or caller.')
            if receipt.get('operation_id'):
                batch.admission_binding(local, receipt)
        result.append((child, local, receipt))
    return result


def retain_source(args, plan, records):
    """Recover the first finalized source from existing receipts, never re-upload it."""
    expected = {**plan['identity']['source'], **{key: plan['identity'][key]
                                              for key in ('media_type', 'compression')}}
    references = [receipt['source_artifact'] for _, _, receipt in records
                  if receipt and 'source_artifact' in receipt]
    saved = batch.load_receipt(args.output / 'source-artifact.json')
    if saved:
        references.append(saved)
    target_id = plan['identity']['parameters'].get('input_pdb_artifact_id')
    if plan['identity']['operation'] == 'scaffold-motif' and (
            not references or any(reference.get('artifact_id') != target_id for reference in references)):
        raise ValueError('Finalized target reference differs from input_pdb_artifact_id or is missing; '
                         'restore the original reference, never upload a replacement.')
    for reference in references:
        if (any(reference.get(key) != value for key, value in expected.items())
                or not isinstance(reference.get('artifact_id'), str) or not reference['artifact_id']
                or reference != references[0]):
            raise ValueError('Campaign source reference differs; no new chunk may be admitted.')
    if references:
        freeze(args.output / 'source-artifact.json', references[0])


def category(local, receipt):
    if not receipt:
        return 'not_submitted'
    state = receipt.get('state')
    if state == 'verified':
        return 'succeeded'
    if state == 'cancelled':
        return 'cancelled'
    if state in batch.TERMINAL:
        return 'failed'
    if state == 'rejected':
        return 'rejected'
    if state in {'submitting', 'admission_unknown'} and not receipt.get('operation_id'):
        return 'unknown'
    status = batch.load_receipt(local.output / 'status.json') or {}
    if status.get('graph', {}).get('action_required') is True:
        return 'held'
    return 'pending' if receipt.get('operation_id') else 'not_submitted'


def admission_slot_held(local, receipt):
    status = batch.load_receipt(local.output / 'status.json')
    if not status or not receipt.get('operation_id'):
        return None
    try:
        batch.batch_operation(status, operation_id=receipt['operation_id'],
                              model_id=receipt['identity']['model_id'])
    except ValueError:
        return None  # A retained mismatched response is not this child's slot evidence.
    error, graph = status.get('error'), status.get('graph')
    flag = error.get('admission_slot_held') if isinstance(error, dict) else None
    signals = [flag] if type(flag) is bool else []
    if isinstance(graph, dict) and graph.get('action_required') is True:
        signals.append(True)
    return signals[0] if signals and all(value == signals[0] for value in signals) else None


def project(args, plan, owner):
    counts = {name: 0 for name in ('requested', 'submitted', 'succeeded', 'failed',
              'cancelled', 'unknown', 'held', 'pending', 'rejected', 'not_submitted')}
    rows = []
    for child, local, receipt in read_children(args, plan, owner):
        receipt = receipt or {}
        count, seed = child['parameters']['num_designs'], child['parameters']['seed']
        state = category(local, receipt)
        counts['requested'] += count
        counts['submitted'] += count if receipt.get('operation_id') else 0
        counts[state] += count
        references = {}
        for name in ('request.json', 'model-contract.json', 'result.json', 'status.json'):
            path = local.output / name
            if path.is_file():
                references[name] = {'path': str(path), 'sha256': batch.FileSource(path).sha256}
        rows.append({'id': child['id'], 'idempotency_key': child['idempotency_key'],
                     'designs': count, 'seed_first': seed, 'seed_last': seed + count - 1,
                     'state': state, 'operation_id': receipt.get('operation_id'),
                     'admission_slot_held': admission_slot_held(local, receipt),
                     'source_artifact': receipt.get('source_artifact'),
                     'output_manifest': receipt.get('output_manifest'),
                     'request_runtime_result_references': references})
    summary = {'schema': 'scientific-campaign-summary/v1',
               'campaign_sha256': plan['campaign_sha256'], 'design_counts': counts,
               'children': rows, 'cost': None,
               'state': 'verified' if counts['succeeded'] == counts['requested'] else 'incomplete',
               'count_scope': 'Requested designs grouped by retained child operation; not accepted binders.'}
    batch.save(args.output / 'summary.json', summary)
    return summary


async def execute(args):
    plan = read_plan(args.output)
    owner = {'endpoint': os.environ['SCIENTIFIC_MODELS_MCP_URL'],
             'caller_fingerprint': batch.digest(os.environ['SCIENTIFIC_MODELS_API_KEY'].encode()),
             'plan_sha256': batch.digest(batch.canonical(plan))}
    ledger = batch.load_receipt(args.output / 'receipt.json') or {'identity': owner, 'state': 'prepared'}
    if ledger['identity'] != owner:
        raise ValueError('Campaign belongs to a different plan, endpoint or caller.')
    if args.action == 'stop':
        ledger['admission_stopped'] = True
    batch.save(args.output / 'receipt.json', ledger)
    records = read_children(args, plan, owner)
    retain_source(args, plan, records)
    errors = []
    # Always visit all accepted siblings before considering any new admission.
    if args.action != 'stop':
        for _, local, receipt in records:
            if receipt and receipt.get('operation_id') and category(local, receipt) not in {
                    'succeeded', 'failed', 'cancelled'}:
                try:
                    with batch.receipt_lock(local.output):
                        await batch.observe_saved(local)
                except Exception as error:
                    errors.append(error)
    records = read_children(args, plan, owner)
    fenced = (errors or ledger.get('admission_stopped') or any(
        category(local, receipt) in {'failed', 'cancelled', 'rejected', 'held', 'pending'}
        for _, local, receipt in records))
    remaining = [record for record in records if category(record[1], record[2]) != 'succeeded']
    if args.action == 'run' and not fenced and remaining:
        source = batch.FileSource(Path(plan['source_path']))
        if {'sha256': source.sha256, 'size_bytes': len(source)} != plan['identity']['source']:
            raise ValueError('Campaign source changed; no new chunk was submitted.')
        unknown = [record for record in remaining if category(record[1], record[2]) == 'unknown']
        # Resolve every unknown first. Even successful reconciliation does not
        # unlock new chunks in this invocation; the next explicit run may do so.
        for child, local, receipt in unknown or remaining:
            # Unknown admission is reconciled by the existing exact request/key
            # owner. Its bounded retry journal fences every later chunk on error.
            freeze(local.parameters, child['parameters'])
            local = child_args(args, plan, child)
            try:
                with batch.receipt_lock(local.output):
                    await batch.run(local)
            except Exception as error:
                errors.append(error)
            finally:
                refreshed = read_children(args, plan, owner)
                retain_source(args, plan, refreshed)
            current = batch.load_receipt(local.output / 'receipt.json')
            if errors or category(local, current) != 'succeeded':
                break
    summary = project(args, plan, owner)
    ledger.update(state=summary['state'])
    batch.save(args.output / 'receipt.json', ledger)
    if errors:
        raise errors[0]  # Existing errors stay diagnosable, never a success/retry claim.
    return {**summary, 'admission_stopped': bool(ledger.get('admission_stopped'))}


def command_line():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    plan = commands.add_parser('plan', help='Freeze all chunks offline; no upload or model call.')
    plan.add_argument('--designs', type=int, required=True)
    plan.add_argument('--chunk-size', type=int, default=64,
                      help='Designs per native request, 1..64. Use smaller chunks for a bounded pilot.')
    plan.add_argument('--operation', required=True)
    plan.add_argument('--source', type=Path, required=True)
    plan.add_argument('--source-artifact', type=Path)
    plan.add_argument('--parameters', type=Path, required=True)
    plan.add_argument('--media-type', required=True)
    plan.add_argument('--compression', choices=('none', 'gzip', 'zstd'), default='none')
    plan.add_argument('--entry-name', required=True)
    plan.add_argument('--semantic-type', required=True)
    plan.add_argument('--idempotency-key', required=True)
    plan.add_argument('--display-name', required=True)
    plan.add_argument('--service-class', choices=('customer-batch', 'bulk-backfill'), default='customer-batch')
    plan.add_argument('--output', type=Path, required=True)
    for action in ('run', 'observe', 'stop'):
        command = commands.add_parser(action)
        command.add_argument('--output', type=Path, required=True)
        command.add_argument('--wait-seconds', type=float, default=180)
        command.add_argument('--poll-seconds', type=float, default=10)
    args = parser.parse_args()
    with batch.receipt_lock(args.output):
        result = plan_campaign(args) if args.action == 'plan' else asyncio.run(execute(args))
    print(json.dumps(result), flush=True)
    return 0 if args.action in {'plan', 'stop'} or result['state'] == 'verified' else 75


if __name__ == '__main__':
    sys.exit(command_line())
