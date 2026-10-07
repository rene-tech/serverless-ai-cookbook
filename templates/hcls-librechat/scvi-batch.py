#!/opt/scientific-client/bin/python
"""Large scVI/scANVI jobs via canonical REST/MCP clients; exit 75 means pending."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from scientific_receipts import load, receipt_lock, save

HERE = Path(__file__).resolve().parent
CLIENT = HERE / 'scvi-client'


def origin():
    value = os.environ.get('SCIENTIFIC_MODELS_API_BASE_URL') or os.environ.get('SCIENTIFIC_MODELS_MCP_URL')
    if not value:
        raise ValueError('Configure the Scientific AI API or MCP URL.')
    return value.rstrip('/').removesuffix('/v1').removesuffix('/mcp')


def verify_client():
    source = json.loads((CLIENT / 'SOURCE.json').read_text())
    for name, digest in source['files'].items():
        if hashlib.sha256((CLIENT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Canonical single-cell client differs from its pinned source.')


def call(module, arguments, log, runner):
    # Reuse transport unchanged; publish receipts through the existing
    # workbench JSON journal on object-storage mounts.
    code = ("import sys;sys.path[:0]=sys.argv[1:3];sys.argv=sys.argv[3:];"
            f"import {module} as client;from scientific_receipts import save;client.save=save;"
            "client.main(require_qa=False)")
    return runner([sys.executable, '-c', code, str(CLIENT), str(HERE), module, *arguments],
                  stdout=log, stderr=subprocess.STDOUT).returncode


def run(args, runner=subprocess.run):
    verify_client()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    receipt = load(output / 'workbench.json')
    api = origin()
    if not os.environ.get('SCIENTIFIC_MODELS_API_KEY'):
        raise ValueError('Scientific AI key is not configured.')
    owner = hashlib.sha256(os.environ['SCIENTIFIC_MODELS_API_KEY'].encode()).hexdigest()
    if receipt and (receipt['origin'], receipt['caller_fingerprint']) != (api, owner):
        raise ValueError('Existing operation belongs to a different endpoint/key; preserve it.')
    admission = load(output / 'run/admission.json')
    operation_id = admission['operation']['id'] if admission else None
    if not receipt:
        if args.recover_only or not args.input or not args.parameters or not args.idempotency_key:
            raise ValueError('New runs require --input, --parameters and --idempotency-key.')
        parameters = json.loads(args.parameters.read_text())
        if parameters.get('schema') != 'fs2-serve.nebius.ai/scvi-workflow-request/v1':
            raise ValueError('Supply only the model parameter object, using the live batch schema.')
        receipt = {'origin': api, 'caller_fingerprint': owner, 'state': 'prepared',
                   'input': str(args.input.resolve()), 'parameters': parameters,
                   'reference': str(args.reference.resolve()) if args.reference else None,
                   'idempotency_key': args.idempotency_key, 'protocol': args.protocol or 'mcp'}
        save(output / 'parameters.json', parameters)
        save(output / 'workbench.json', receipt)
    else:
        changed = (
            (args.parameters and json.loads(args.parameters.read_text()) != receipt['parameters'])
            or (args.input and str(args.input.resolve()) != receipt['input'])
            or (args.reference and str(args.reference.resolve()) != receipt['reference'])
            or (args.idempotency_key and args.idempotency_key != receipt['idempotency_key'])
            or (args.protocol and args.protocol != receipt['protocol'])
        )
        if changed:
            raise ValueError('Do not change a retained run; use a new run directory.')
    if args.recover_only and not operation_id:
        raise ValueError('No recorded operation to recover; inspect admission receipts before submitting.')
    # Object-storage mounts reject O_APPEND on an existing object. Keep each
    # observation attempt's log separately; never append, truncate old evidence
    # or move the study to scratch to recover an existing operation.
    log_path = output / 'logs' / f'{time.time_ns()}-{uuid4().hex}.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    receipt['log'] = str(log_path)
    save(output / 'workbench.json', receipt)
    with log_path.open('w') as log:
        if not operation_id:
            arguments = ['--origin', api, '--input', receipt['input'], '--parameters', str(output / 'parameters.json'),
                         '--output', str(output / 'upload'), '--prepare-only',
                         '--idempotency-key', receipt['idempotency_key']]
            if receipt['reference']:
                arguments += ['--reference', receipt['reference']]
            if call('qualify_api', arguments, log, runner):
                return {'state': 'upload_error', 'log': str(log_path)}, 1
        arguments = ['--origin', api, '--output', str(output / 'run'), '--protocol', receipt['protocol'],
                     '--timeout', str(args.wait_seconds)]
        if operation_id:
            arguments += ['--operation-id', operation_id]
        else:
            arguments += ['--request', str(output / 'upload/request.json'), '--idempotency-key', receipt['idempotency_key']]
        code = call('qualify_hosted', arguments, log, runner)
    admission = load(output / 'run/admission.json')
    operation_id = admission['operation']['id'] if admission else operation_id
    status = load(output / 'run/status.json') or {}
    state = status.get('batch', {}).get('status', status.get('status'))
    if code:
        published = status.get('batch', {}).get('result_published', status.get('result_available', False))
        pending = bool(operation_id) and (
            state in ('accepted', 'queued', 'running')
            or (state in ('succeeded', 'failed', 'cancelled') and not published)
        )
        receipt.update(operation_id=operation_id, state='pending' if pending else 'error')
        save(output / 'workbench.json', receipt)
        return {'state': receipt['state'], 'operation_id': operation_id, 'output': str(output),
                'log': str(log_path), 'next': 'Recover this directory; do not submit a replacement.'}, 75 if pending else 1
    sys.path.insert(0, str(CLIENT))
    from qualify_outputs import validate
    validation = validate(output / 'run/worker-result.json', output / 'run/data')
    save(output / 'output-validation.json', validation)
    receipt.update(operation_id=operation_id, state='succeeded')
    save(output / 'workbench.json', receipt)
    return {'state': 'succeeded', 'operation_id': operation_id, 'output': str(output),
            'data': str(output / 'run/data'), 'log': str(log_path), 'validation': validation}, 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path)
    p.add_argument('--parameters', type=Path)
    p.add_argument('--reference', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--idempotency-key')
    p.add_argument('--protocol', choices=('rest', 'mcp'))
    p.add_argument('--wait-seconds', type=int, default=60)
    p.add_argument('--recover-only', action='store_true')
    args = p.parse_args()
    if not 1 <= args.wait_seconds <= 10800:
        p.error('Observation must be 1–10800 seconds; this is not the server job timeout.')
    os.umask(0o077)
    with receipt_lock(args.output):
        value, code = run(args)
    print(json.dumps(value))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
