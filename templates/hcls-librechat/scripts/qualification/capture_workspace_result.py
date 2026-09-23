"""Read this GROMACS acceptance study back through the real authenticated UI API.

Retain private receipts rather than printing signed artifact links or chat data.
No submission, inference, login attempt, bucket mutation or credential disclosure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from uuid import UUID

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--session-state', type=Path, required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--list-only', action='store_true')
    parser.add_argument('--conversation-id', type=UUID,
                        help='Retain this acceptance conversation privately for provenance')
    args = parser.parse_args()
    prefix = PurePosixPath(args.prefix)
    if not args.url.startswith('https://') or not args.prefix.startswith('my-studies/gromacs-'):
        raise ValueError('Use the exact TLS workbench and task-owned GROMACS study')
    if '..' in prefix.parts or prefix.is_absolute():
        raise ValueError('Invalid workspace prefix')
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    state = json.loads(args.session_state.read_text())
    with httpx.Client(base_url=args.url, timeout=180, trust_env=False) as client:
        for cookie in state['cookies']:
            client.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])
        response = client.post('/api/auth/refresh')
        response.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + response.json()['token']
        # Refresh rotation stays in the existing private session file.
        state['cookies'] = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path,
                             'expires': c.expires or -1, 'secure': c.secure,
                             'httpOnly': c.has_nonstandard_attr('HttpOnly'), 'sameSite': 'Lax'}
                            for c in client.cookies.jar]
        args.session_state.write_text(json.dumps(state))
        if args.conversation_id:
            response = client.get('/api/messages/' + str(args.conversation_id))
            response.raise_for_status()
            (args.output / 'conversation-private.json').write_text(json.dumps(response.json(), indent=2))
        pending, files, total = [args.prefix], [], 0
        while pending:
            current = pending.pop()
            response = client.get('/api/scientific-demos/workspace', params={'path': current})
            response.raise_for_status()
            entries = response.json()['data']
            for item in entries:
                source = PurePosixPath(item['path'])
                relative = source.relative_to(prefix)
                if '..' in relative.parts or len(relative.parts) > 5:
                    raise ValueError('Unexpected returned path')
                if item['kind'] == 'directory':
                    pending.append(str(source))
                    continue
                size = item['size_bytes']
                total += size
                if size > 256 * 1024**2 or total > 512 * 1024**2 or len(files) >= 250:
                    raise ValueError('Acceptance capture budget exceeded')
                record = {'path': str(relative), 'bytes': size}
                if not args.list_only:
                    response = client.get('/api/scientific-demos/workspace/file', params={'path': str(source)})
                    response.raise_for_status()
                    if len(response.content) != size:
                        raise ValueError('Workspace file changed during capture')
                    destination = args.output / 'files' / str(relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(response.content)
                    record['sha256'] = hashlib.sha256(response.content).hexdigest()
                files.append(record)
        receipt = {'files': files, 'file_count': len(files), 'bytes': total,
                   'workspace_prefix': args.prefix, 'downloaded': not args.list_only}
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
        print(json.dumps({k: v for k, v in receipt.items() if k != 'files'}))


if __name__ == '__main__':
    main()
