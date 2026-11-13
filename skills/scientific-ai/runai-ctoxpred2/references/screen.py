"""Portable CToxPred2 client; requires an already uploaded owner input archive."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def save(path, value, *, create=False):
    raw = (json.dumps(value, indent=2) + '\n').encode()
    if create:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    else:
        temporary = path.with_name(path.name + '.tmp')
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True, help='Private durable intent; reuse this file after interruption')
    parser.add_argument('--idempotency-key', required=True, help='One stable key for this exact request')
    parser.add_argument('--key', required=True, help='Existing owner-bucket key of uploaded input.tar.gz')
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--version', required=True, help='Qualified scientific version from discovery')
    parser.add_argument('--region', required=True, help='Authorized processing region from discovery')
    parser.add_argument('--wait-seconds', type=int, default=3600)
    args = parser.parse_args()
    base = os.environ['SCIENTIFIC_AI_URL'].rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('Use the configured HTTPS service origin')
    api_client, download_client = build_opener(NoRedirect), build_opener(NoRedirect)

    def call(method, path, payload=None, *, idempotency_key=None):
        headers = {'Authorization': 'Bearer ' + os.environ['SCIENTIFIC_AI_TOKEN']}
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        request = Request(base + path, data=None if payload is None else json.dumps(payload).encode(),
                          method=method, headers=headers)
        try:
            with api_client.open(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError('Scientific API rejected request: ' + error.read().decode(errors='replace')) from None

    raw = args.archive.read_bytes()
    request = {'model': 'ctoxpred2', 'workflow': 'screen-molecules', 'version': args.version,
        'region': args.region, 'gpu': 'cpu', 'parameters': {}, 'inputs': [{'name': 'input.tar.gz',
        'key': args.key, 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}]}
    intent = {'origin': base, 'idempotency_key': args.idempotency_key, 'request': request}
    if args.state.exists():
        state = json.loads(args.state.read_text())
        if any(state.get(key) != value for key, value in intent.items()):
            raise ValueError('Saved intent differs; keep the original request and key for reconciliation')
    else:
        state = intent
        save(args.state, state, create=True)  # Durable BEFORE the first POST; contains no credentials.
    if 'run_id' not in state:
        discovery = call('GET', '/v1/models/ctoxpred2?workflow=screen-molecules')
        if 'screen-molecules' not in discovery['workflows']:
            raise ValueError('Selected workflow is unavailable')
        # An ambiguous response leaves the same intent/key for an explicit idempotent retry.
        run = call('POST', '/v1/runs', request, idempotency_key=state['idempotency_key'])
        state['run_id'] = run['run_id']; save(args.state, state)
    run_id = state['run_id']
    deadline = time.monotonic() + args.wait_seconds
    while True:
        run = call('GET', '/v1/runs/' + run_id)
        if run['phase'] in {'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMED_OUT', 'PAUSED', 'INTERRUPTED'}:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Client wait ended; poll/cancel the saved run ID or reuse this state file')
        time.sleep(3)
    state['phase'] = run['phase']; save(args.state, state)
    print(json.dumps({'run_id': run_id, 'phase': run['phase']}))
    if run['phase'] != 'SUCCEEDED':
        raise RuntimeError('Inspect the structured run error before changing inputs or resubmitting')
    manifest = call('GET', '/v1/runs/' + run_id + '/artifacts')  # Fresh signed links for this retrieval.
    output = args.state.parent / 'ctox-results' / run_id
    output.mkdir(parents=True, exist_ok=True)
    for item in manifest['files']:
        name = PurePosixPath(item['path'])
        if str(name) not in {'data/outputs/screen/predictions.json',
                'data/outputs/screen/predictions.csv', 'data/outputs/screen/science.json'}:
            continue
        with download_client.open(item['download_url'], timeout=120) as response:
            raw = response.read(item['size_bytes'] + 1)  # Separate opener carries no API bearer header.
        if len(raw) != item['size_bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Downloaded result failed size/hash verification')
        (output / name.name).write_bytes(raw)
        print(name.name, len(raw), item['sha256'])


if __name__ == '__main__':
    main()
