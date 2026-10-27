#!/usr/bin/env python3
"""Finite capability-file transfer shim; contains no cloud keys or private App imports."""
import argparse
import hashlib
import json
import os
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


def execute(config_path, command_path):
    config = json.loads(config_path.read_text())
    command_raw = command_path.read_bytes()
    if hashlib.sha256(command_raw).hexdigest() != config['command_sha256']:
        raise TransferError('Injected command checksum differs from the approved command')
    command = json.loads(command_raw)
    if not isinstance(command, list) or not command or any(not isinstance(v, str) or '\0' in v for v in command):
        raise TransferError('Command must be an exec-form string array')
    expected = config['input']
    if type(expected['size_bytes']) is not int or expected['size_bytes'] < 1:
        raise TransferError('Input size must be a positive integer')
    if len(expected['sha256']) != 64 or any(c not in '0123456789abcdef' for c in expected['sha256']):
        raise TransferError('Input SHA-256 must be a lowercase digest')
    root = Path(tempfile.mkdtemp(prefix='monai-provider-'))
    incoming, outgoing = root / 'in', root / 'out'
    incoming.mkdir(); outgoing.mkdir()
    input_path = incoming / 'input.tar'
    checksum, received = hashlib.sha256(), 0
    with open_object(Request(checked_url(expected['url']), method='GET')) as response, input_path.open('xb') as target:
        while block := response.read(4 * 1024**2):
            received += len(block)
            if received > expected['size_bytes']:
                raise TransferError('Downloaded input exceeds the declared byte length')
            checksum.update(block); target.write(block)
    if received != expected['size_bytes'] or checksum.hexdigest() != expected['sha256']:
        raise TransferError('Downloaded input bytes fail the declared size or SHA-256 integrity check')
    env = dict(os.environ, MONAI_PROVIDER_INPUT=str(incoming), MONAI_PROVIDER_OUTPUT=str(outgoing))
    with (outgoing / 'execution.log').open('xb') as log:
        completed = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    files = {}
    for item in sorted(outgoing.rglob('*')):
        if item.is_symlink() or (not item.is_dir() and not item.is_file()):
            raise TransferError('Output contains a nonregular file; export only closed scientific files')
        if item.is_file():
            files[str(item.relative_to(outgoing))] = {'sha256': digest(item), 'size_bytes': item.stat().st_size}
    (outgoing / 'transfer-result.json').write_text(json.dumps({
        'schema': 'monai-portable-transfer/v1', 'execution_exit_code': completed.returncode,
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
    print(json.dumps({'execution_exit_code': completed.returncode, 'input_sha256': checksum.hexdigest(),
                      'output_sha256': sha, 'output_size_bytes': size, 'uploaded': True}), flush=True)
    return completed.returncode if 0 <= completed.returncode <= 255 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--command', type=Path, required=True)
    args = parser.parse_args()
    try:
        return execute(args.config, args.command)
    except TransferError as error:
        print(json.dumps({'status': 'failed', 'phase': 'object-transfer', 'message': str(error)}), flush=True)
        return 74
    except (OSError, ValueError, KeyError):
        print(json.dumps({'status': 'failed', 'phase': 'transfer-configuration',
                          'message': 'Transfer configuration or local storage is invalid; inspect the injected field types and writable scratch'}), flush=True)
        return 2


if __name__ == '__main__':
    sys.exit(main())
