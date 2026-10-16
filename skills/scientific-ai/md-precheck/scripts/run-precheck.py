#!/usr/bin/env python3
"""Consented MD precheck through hosted MCP, with exact reuse and verified files.

Uses the workbench's existing upload and receipt helpers. No scientific code,
customer credentials, scheduler or alternative checker is embedded here.
Explicit --rerun requests a fresh check; resuming its receipt never duplicates it.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from urllib.parse import quote, urlsplit

sys.path.insert(0, '/opt/bionemo')
import httpx2
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from scientific_receipts import load, receipt_lock, save, staged_output

spec = importlib.util.spec_from_file_location('artifact_upload', '/opt/bionemo/upload-artifact.py')
upload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload)


def admitted_retry(value):
    error = value.get('error') or {}
    return error.get('retryable') is True and error.get('admission') == 'not-submitted'


def workspace_url(path):
    path = path.resolve().relative_to('/workspace')
    return '/demos?tab=workspace&path=' + quote(str(path.parent), safe='') + '&file=' + quote(str(path), safe='')


async def execute(args, client, object_http, endpoint, key):
    options = {'input_format': args.input_format, 'probes': args.probes, 'intent': args.intent,
               'nsteps': args.nsteps, 'threads': args.threads, 'define': args.define}
    options.update({field: getattr(args, field) for field in
                    ('coords', 'top', 'mdp', 'ndx', 'tpr', 'fasta', 'workflow', 'chain_names')
                    if getattr(args, field) is not None})
    identity = {**upload.file_identity(args.file), 'options': options, 'endpoint': endpoint,
                'caller': hashlib.sha256(key.encode()).hexdigest(), 'idempotency_key': args.idempotency_key}
    rerun = getattr(args, 'rerun', False)
    if rerun:
        identity['rerun'] = True
    receipt = args.output_dir / 'receipt.json'
    record = load(receipt) or {'identity': identity, 'state': 'prepared'}
    if record['identity'] != identity:
        raise ValueError('Input, options or caller changed; use a new output directory and key.')
    deadline = time.monotonic() + args.wait_seconds

    async def call(name, value, filename):
        raw = await client.call_tool(name, value)
        save(args.output_dir / filename, raw.model_dump(mode='json', by_alias=True))
        return upload.unpack(raw)

    schema = await call('get_model_schema', {'model_id': 'mdprecheck', 'protocol': 'native',
                                           'tool_name': 'run_mdprecheck'}, 'schema.json')
    contracts = schema.get('contracts', [])
    if len(contracts) != 1:
        raise ValueError('Exact native checker contract is unavailable; inspect schema.json.')
    media = {'tar.gz': 'application/gzip', 'tar': 'application/x-tar',
             'zip': 'application/zip', 'tpr': 'application/octet-stream'}[args.input_format]
    upload_args = SimpleNamespace(file=args.file, model='mdprecheck', media_type=media,
                                  compression='none', output_dir=args.output_dir / 'upload',
                                  idempotency_key=args.idempotency_key + '-upload')
    upload_args.output_dir.mkdir(parents=True, exist_ok=True)
    uploaded = await upload.transfer(client, object_http, upload_args, endpoint, key)
    payload = {'input': uploaded['artifact'], **options}
    Draft202012Validator(contracts[0]['input_schema']).validate(
        {**payload, 'idempotency_key': args.idempotency_key, 'wait_seconds': 0})
    lookup = await call('lookup_mdprecheck', payload, 'lookup.json')
    if 'error' in lookup:
        raise ValueError('Precheck lookup failed; inspect lookup.json. No replacement report is allowed.')
    fingerprint = lookup['workload_fingerprint']
    save(args.output_dir / 'input.json', payload)
    if not rerun and not record.get('operation_id') and lookup.get('found'):
        if lookup['operation']['status'] not in ('CANCELLED', 'FAILED', 'TIMED_OUT', 'EXPORT_FAILED'):
            record.update(operation_id=lookup['operation']['id'], reused=True)
    while not record.get('operation_id'):
        record['state'] = 'submitting'
        save(receipt, record)  # A lost reply must keep this same idempotency key.
        accepted = await call('run_mdprecheck', {**payload, 'idempotency_key': args.idempotency_key,
                                               'wait_seconds': 0}, 'submission.json')
        if admitted_retry(accepted):
            record['state'] = 'waiting-for-admission'
            save(receipt, record)
            if time.monotonic() >= deadline:
                raise TimeoutError('Not admitted yet; rerun this same command to continue. No old report substituted.')
            await asyncio.sleep(5)
            continue
        if 'error' in accepted:
            raise ValueError('Precheck submission failed; inspect submission.json and preserve this key.')
        record.update(operation_id=accepted['operation']['id'], reused=False)
        save(receipt, record)
    op = record['operation_id']
    print(json.dumps({'operation_id': op, 'reused': record.get('reused', False)}), flush=True)
    while True:
        state = await call('get_scientific_status', {'operation_id': op}, 'status.json')
        if state.get('operation', {}).get('id') != op:
            raise ValueError('Status identity mismatch; inspect status.json.')
        record['state'] = state['operation']['status']
        save(receipt, record)
        if record['state'] == 'SUCCEEDED':
            break
        if record['state'] in ('FAILED', 'CANCELLED', 'TIMED_OUT', 'PREEMPTED', 'EXPORT_FAILED'):
            raise ValueError('Precheck terminated without complete reports: ' + record['state'])
        if time.monotonic() >= deadline:
            raise TimeoutError('Check still pending; resume this command and operation, not a new job.')
        await asyncio.sleep(5)
    envelope = await call('get_scientific_result', {'operation_id': op}, 'result.json')
    result = envelope['result']
    if envelope['operation']['id'] != op or result['workload_fingerprint'] != fingerprint:
        raise ValueError('Report does not cover the exact requested inputs/options; refusing delivery.')
    files = []
    for kind in ('html', 'json'):
        pointer = result['artifacts'][kind]
        metadata = await call('get_scientific_artifact', {'artifact_id': pointer['artifact_id']}, kind + '-metadata.json')
        if any(metadata.get(k) != v for k, v in pointer.items()):
            raise ValueError('Report metadata differs from its immutable pointer.')
        handle = await call('download_scientific_artifact', {'artifact_id': pointer['artifact_id']}, kind + '-handle.json')
        handle = handle.get('handle', handle)
        if handle.get('method') != 'GET' or urlsplit(handle['url']).scheme != 'https':
            raise ValueError('Expected an authenticated platform-issued HTTPS download handle.')
        target = args.output_dir / ('report.' + kind)
        with staged_output(target) as staged:
            digest, size = hashlib.sha256(), 0
            async with object_http.stream('GET', handle['url'], headers=handle.get('headers', {})) as response:
                response.raise_for_status()
                with staged.path.open('wb') as stream:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > min(pointer['size_bytes'], 128 * 1024**2):
                            raise ValueError('Report exceeds its declared size.')
                        digest.update(chunk)
                        stream.write(chunk)
            if size != pointer['size_bytes'] or digest.hexdigest() != pointer['sha256']:
                raise ValueError('Report checksum mismatch; nothing delivered.')
        files.append({**staged.receipt, 'workspace_url': workspace_url(target)})
    delivered = {'operation_id': op, 'workload_fingerprint': fingerprint, 'status': result['status'],
                 'verdict': result.get('verdict'), 'findings': result['findings'], 'files': files,
                 'reused': record.get('reused', False), 'options': options}
    save(args.output_dir / 'delivery.json', delivered)
    record.update(state='delivered', workload_fingerprint=fingerprint)
    save(receipt, record)
    return delivered


async def run(args):
    endpoint, key = os.environ['SCIENTIFIC_MODELS_MCP_URL'], os.environ['SCIENTIFIC_MODELS_API_KEY']
    if urlsplit(endpoint).scheme != 'https':
        raise ValueError('The Scientific AI MCP endpoint must use HTTPS.')
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + key}, timeout=120, trust_env=False) as http:
        async with httpx2.AsyncClient(timeout=300, trust_env=False, follow_redirects=False) as objects:
            async with Client(streamable_http_client(endpoint, http_client=http)) as client:
                return await execute(args, client, objects, endpoint, key)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--rerun', action='store_true',
                        help='Explicitly request a fresh check instead of reusing an existing report. Use a new output directory and idempotency key, then resume that same command if interrupted.')
    parser.add_argument('--input-format', choices=('tar.gz', 'tar', 'zip', 'tpr'), required=True)
    for field in ('coords', 'top', 'mdp', 'ndx', 'tpr', 'fasta', 'workflow', 'chain_names'):
        parser.add_argument('--' + field.replace('_', '-'))
    parser.add_argument('--intent', action='append', default=[])
    parser.add_argument('--define', action='append', default=[])
    parser.add_argument('--probes', nargs='*', choices=('grompp', 'energy', 'minimize', 'stability'), default=[])
    parser.add_argument('--nsteps', type=int, default=5000)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--wait-seconds', type=int, default=2400)
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 190 or not 1 <= args.wait_seconds <= 7200:
        parser.error('Use an 8–190 character idempotency key and 1–7200 second observation bound.')
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with receipt_lock(args.output_dir):
        print(json.dumps(asyncio.run(run(args)), ensure_ascii=False), flush=True)
