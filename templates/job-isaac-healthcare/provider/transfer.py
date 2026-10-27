#!/usr/bin/env python3
"""Finite capability-file transfer shim; contains no cloud keys or private App imports."""
import argparse
import hashlib
import json
import os
import signal
import time
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class TransferError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise TransferError('Object transfer redirected; obtain a direct scoped object URL')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def checked_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise TransferError('A direct HTTPS scoped object URL is required')
    return value


def open_object(request):
    try:
        return build_opener(NoRedirect).open(request, timeout=120)
    except HTTPError as error:
        raise TransferError(f'Object transfer returned HTTP {error.code}; verify the scoped URL and expiry') from None
    except (URLError, TimeoutError):
        raise TransferError('Object transfer failed; verify connectivity, TLS and the scoped URL expiry') from None


def execute(config_path, command_path, *, endpoint_idle=False):
    config = json.loads(config_path.read_text())
    command_raw = command_path.read_bytes()
    if hashlib.sha256(command_raw).hexdigest() != config['command_sha256']:
        raise TransferError('Injected command checksum differs from the approved command')
    command = json.loads(command_raw)
    if not isinstance(command, list) or not command or any(not isinstance(v, str) or '\0' in v for v in command):
        raise TransferError('Command must be an exec-form string array')
    timeout_s = config.get('execution_timeout_s')
    if type(timeout_s) is not int or timeout_s <= 0:
        raise TransferError('execution_timeout_s must be a positive integer')
    if endpoint_idle and 'claim' not in config:
        raise TransferError('Endpoint execution requires a conditional start-marker capability')
    if 'claim' in config:
        claim = config['claim']
        headers = dict(claim.get('headers', {}))
        if headers.get('If-None-Match') != '*':
            raise TransferError('Start-marker PUT must require If-None-Match: *')
        payload = json.dumps({'command_sha256': config['command_sha256'],
                              'input_sha256': config['input']['sha256']}, sort_keys=True).encode()
        headers['Content-Type'] = 'application/json'
        headers['Content-Length'] = str(len(payload))
        request = Request(checked_url(claim['url']), data=payload, headers=headers, method='PUT')
        try:
            with build_opener(NoRedirect).open(request, timeout=120):
                pass
        except HTTPError as error:
            if error.code == 412:
                print(json.dumps({'execution_skipped': True, 'reason': 'start marker already exists'}), flush=True)
                return 0
            raise TransferError(f'Start-marker PUT returned HTTP {error.code}; science was not started') from None
        except (URLError, TimeoutError):
            raise TransferError('Start-marker request failed or is uncertain; do not replay science') from None
    expected = config['input']
    if type(expected['size_bytes']) is not int or expected['size_bytes'] < 1:
        raise TransferError('Input size must be a positive integer')
    if len(expected['sha256']) != 64 or any(c not in '0123456789abcdef' for c in expected['sha256']):
        raise TransferError('Input SHA-256 must be a lowercase digest')
    root = Path(tempfile.mkdtemp(prefix='isaac-provider-'))
    incoming, outgoing = root / 'in', root / 'out'
    incoming.mkdir()
    outgoing.mkdir()
    input_path = incoming / 'input.tar'
    checksum, received = hashlib.sha256(), 0
    with open_object(Request(checked_url(expected['url']), method='GET')) as response, input_path.open('xb') as target:
        while block := response.read(4 * 1024**2):
            received += len(block)
            if received > expected['size_bytes']:
                raise TransferError('Downloaded input exceeds the declared byte length')
            checksum.update(block)
            target.write(block)
    if received != expected['size_bytes'] or checksum.hexdigest() != expected['sha256']:
        raise TransferError('Downloaded input bytes fail the declared size or SHA-256 integrity check')
    env = dict(os.environ, ISAAC_PROVIDER_INPUT=str(incoming), ISAAC_PROVIDER_OUTPUT=str(outgoing))
    with (outgoing / 'execution.log').open('xb') as log:
        child = subprocess.Popen(command, cwd=root, env=env, stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        def forward(signum, _frame):
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass
        handlers = {number: signal.signal(number, forward) for number in (signal.SIGTERM, signal.SIGINT)}
        try:
            exit_code = child.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            exit_code = 124
            log.write(b'\nExecution exceeded caller-declared timeout; process group terminated.\n')
        finally:
            for number, handler in handlers.items():
                signal.signal(number, handler)
    files = {}
    for item in sorted(outgoing.rglob('*')):
        if item.is_symlink() or (not item.is_dir() and not item.is_file()):
            raise TransferError('Output contains a nonregular file; export only closed scientific files')
        if item.is_file():
            files[str(item.relative_to(outgoing))] = {'sha256': digest(item), 'size_bytes': item.stat().st_size}
    (outgoing / 'transfer-result.json').write_text(json.dumps({
        'schema': 'isaac-portable-transfer/v1', 'execution_exit_code': exit_code,
        'input_sha256': checksum.hexdigest(), 'command_sha256': config['command_sha256'], 'files': files,
    }, indent=2) + '\n')
    output_path = root / 'output.tar'
    with tarfile.open(output_path, 'w') as archive:
        for item in sorted(outgoing.rglob('*')):
            if item.is_file():
                archive.add(item, arcname=str(item.relative_to(outgoing)), recursive=False)
    size, sha = output_path.stat().st_size, digest(output_path)
    maximum = config['output'].get('max_bytes')
    if maximum is not None and (type(maximum) is not int or maximum < size):
        raise TransferError('Complete output exceeds the caller-declared export budget; no data was truncated')
    headers = dict(config['output'].get('headers', {}))
    headers['Content-Length'] = str(size)
    headers.setdefault('Content-Type', 'application/x-tar')
    with output_path.open('rb') as body:
        request = Request(checked_url(config['output']['url']), data=body, headers=headers, method='PUT')
        with open_object(request) as response:
            if not 200 <= response.status < 300:
                raise TransferError('Output upload did not succeed; retrieve completed files before retrying science')
    print(json.dumps({'execution_exit_code': exit_code, 'input_sha256': checksum.hexdigest(),
                      'output_sha256': sha, 'output_size_bytes': size, 'uploaded': True}), flush=True)
    return exit_code if 0 <= exit_code <= 255 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--command', type=Path, required=True)
    parser.add_argument('--endpoint-idle', action='store_true', help='Claim once, then idle until the owner stops the Endpoint')
    args = parser.parse_args()
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    try:
        result = execute(args.config, args.command, endpoint_idle=args.endpoint_idle)
    except TransferError as error:
        print(json.dumps({'status': 'failed', 'phase': 'object-transfer', 'message': str(error)}), flush=True)
        result = 74
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'status': 'failed', 'phase': 'transfer-configuration',
                          'message': 'Transfer configuration or local storage is invalid; inspect the injected field types and writable scratch'}), flush=True)
        result = 2
    if args.endpoint_idle:
        print(json.dumps({'phase': 'endpoint-idle', 'exit_code': result,
                          'science_replay': False, 'owner_stop_delete_required': True}), flush=True)
        while True:
            time.sleep(60)
    return result


if __name__ == '__main__':
    sys.exit(main())
