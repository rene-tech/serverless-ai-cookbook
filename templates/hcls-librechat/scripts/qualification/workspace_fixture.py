"""Publish a public qualification fixture through the real workbench workspace API.

Idempotent by content, refuses to replace different existing bytes. This tests
the same mounted customer bucket used by the browser and agent.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx
from restore_endpoint_account import credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.prefix.startswith('demo-assets/gromacs-') or '..' in args.prefix.split('/'):
        raise ValueError('Only this task\'s public demo fixture directory is allowed')
    os.umask(0o077)
    if args.output.exists():
        raise ValueError('Retain the existing verification receipt')
    verified = []
    with httpx.Client(base_url=args.url, timeout=180, trust_env=False) as client:
        login = client.post('/api/auth/login', json=credentials(args.backup, 'sandbox2'))
        login.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + login.json()['token']
        for name in ('input.tar.gz', 'request.json', 'fixture.json'):
            source = args.fixture / name
            digest = hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()
            relative = args.prefix.rstrip('/') + '/' + name
            existing = client.get('/api/scientific-demos/workspace/file', params={'path': relative})
            if existing.status_code == 404:
                with source.open('rb') as stream:
                    response = client.post('/api/scientific-demos/workspace', data={'path': relative},
                        files={'file': (name, stream, 'application/octet-stream')})
                response.raise_for_status()
                existing = client.get('/api/scientific-demos/workspace/file', params={'path': relative})
            existing.raise_for_status()
            if hashlib.sha256(existing.content).hexdigest() != digest:
                raise ValueError('Workspace has different bytes; no overwrite is allowed')
            verified.append({'path': '/workspace/' + relative, 'bytes': source.stat().st_size, 'sha256': digest})
    args.output.write_text(json.dumps({'files': verified, 'round_trip': True}, indent=2))
    print(json.dumps({'files': len(verified), 'round_trip': True, 'workspace_prefix': '/workspace/' + args.prefix}))


if __name__ == '__main__':
    main()
