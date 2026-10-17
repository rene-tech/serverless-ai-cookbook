#!/usr/bin/env python3
"""Consented MD precheck through hosted MCP, with exact reuse and verified files.

Uses the workbench's existing upload and receipt helpers. No scientific code,
customer credentials, scheduler or alternative checker is embedded here.
Explicit --rerun requests a fresh check. The result is returned in one call;
there is no asynchronous job, polling or automatic inference retry.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
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
    Draft202012Validator(contracts[0]['input_schema']).validate(payload)
    lookup = await call('lookup_mdprecheck', payload, 'lookup.json')
    if 'error' in lookup:
        raise ValueError('Precheck lookup failed; inspect lookup.json. No replacement report is allowed.')
    fingerprint = lookup['workload_fingerprint']
    save(args.output_dir / 'input.json', payload)
    envelope = load(args.output_dir / 'result.json')
    if envelope is None and not rerun and lookup.get('found'):
        envelope = lookup
        record['reused'] = True
    if envelope is None:
        if record['state'] == 'submitting':
            raise ValueError('Previous response was lost. Inspect the exact-input lookup before explicitly rerunning; no automatic retry.')
        record['state'] = 'submitting'
        save(receipt, record)
        envelope = await call('run_mdprecheck', payload, 'response.json')
        if 'error' in envelope:
            raise ValueError('Precheck submission failed; inspect response.json. Do not retry automatically.')
        record['reused'] = False
    op = envelope['operation']['id']
    result = envelope['result']
    if envelope['operation']['status'] != 'SUCCEEDED' or result['workload_fingerprint'] != fingerprint:
        raise ValueError('Report does not cover the exact requested inputs/options; refusing delivery.')
    save(args.output_dir / 'result.json', envelope)
    record.update(operation_id=op, state='completed')
    save(receipt, record)
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
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + key}, timeout=2400, trust_env=False) as http:
        async with httpx2.AsyncClient(timeout=300, trust_env=False, follow_redirects=False) as objects:
            async with Client(streamable_http_client(endpoint, http_client=http), read_timeout_seconds=2400) as client:
                return await execute(args, client, objects, endpoint, key)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--idempotency-key', required=True, help='Immutable upload identity only, not inference idempotency.')
    parser.add_argument('--rerun', action='store_true',
                        help='Explicitly request a fresh synchronous check instead of reusing a completed report; use a new output directory and upload identity.')
    parser.add_argument('--input-format', choices=('tar.gz', 'tar', 'zip', 'tpr'), required=True)
    for field in ('coords', 'top', 'mdp', 'ndx', 'tpr', 'fasta', 'workflow', 'chain_names'):
        parser.add_argument('--' + field.replace('_', '-'))
    parser.add_argument('--intent', action='append', default=[])
    parser.add_argument('--define', action='append', default=[])
    parser.add_argument('--probes', nargs='*', choices=('grompp', 'energy', 'minimize', 'stability'), default=[])
    parser.add_argument('--nsteps', type=int, default=5000)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 190:
        parser.error('Use an 8–190 character upload idempotency key.')
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with receipt_lock(args.output_dir):
        print(json.dumps(asyncio.run(run(args)), ensure_ascii=False), flush=True)
