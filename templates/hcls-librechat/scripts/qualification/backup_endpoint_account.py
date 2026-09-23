"""Read-only endpoint/configuration and account export before replacement.

No mutation, deletion, endpoint creation or token output. The output directory
contains private account data and is created with owner-only permissions.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

import httpx


def private(path, value):
    with path.open('x') as handle:
        path.chmod(0o600)
        json.dump(value, handle, indent=2)
        handle.write('\n')


def capture(endpoint, output, *, profile):
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    cli = ['nebius', '--profile', profile]
    value = json.loads(subprocess.check_output(cli + ['ai', 'endpoint', 'get', '--id', endpoint, '--format', 'json']))
    private(output / 'endpoint-private.json', value)
    variables = {item['name']: item for item in value['spec']['environment_variables']}

    def resolve(name):
        item = variables[name]
        if 'value' in item:
            return item['value']
        secret = item['mysterybox_secret']
        command = cli + ['mysterybox', 'payload', 'get', '--secret-id', secret['secret_id'], '--format', 'json']
        if secret.get('version_id'):
            command += ['--version-id', secret['version_id']]
        payload = json.loads(subprocess.check_output(command))
        entries = payload.get('data', [])
        selected = next(entry for entry in entries if entry['key'] == name)
        return selected['string_value']

    url = next(item for item in value['status']['public_endpoints'] if item.startswith('https://'))
    with httpx.Client(base_url=url, timeout=90, trust_env=False) as client:
        login = client.post('/api/auth/login', json={
            'email': resolve('SEED_DEFAULT_USER_EMAIL'), 'password': resolve('SEED_DEFAULT_USER_PASSWORD')})
        if login.status_code != 200:
            raise RuntimeError(f'Account login failed: HTTP {login.status_code}; no deletion is allowed')
        client.headers['Authorization'] = 'Bearer ' + login.json()['token']
        conversations = []
        seen = set()
        cursor = None
        for page in range(1000):
            response = client.get('/api/convos', params={'pageNumber': page + 1, **({'cursor': cursor} if cursor else {})})
            response.raise_for_status()
            listing = response.json()
            private(output / f'conversations-{page:04d}.json', listing)
            rows = listing.get('conversations', [])
            fresh = [row for row in rows if row['conversationId'] not in seen]
            for row in fresh:
                conversation_id = row['conversationId']
                if '/' in conversation_id or '..' in conversation_id:
                    raise ValueError('Unexpected conversation ID in account response')
                messages = client.get('/api/messages/' + conversation_id)
                messages.raise_for_status()
                private(output / (conversation_id + '-messages.json'), messages.json())
                seen.add(conversation_id)
                conversations.append(conversation_id)
            cursor = listing.get('nextCursor')
            if not fresh or not cursor and len(rows) < 25:
                break
        else:
            raise RuntimeError('Account export pagination bound reached; do not retire the endpoint')
        for name, path in {'runs': '/api/scientific-demos/runs',
                           'workspace': '/api/scientific-demos/workspace',
                           'agents': '/api/agents'}.items():
            response = client.get(path)
            private(output / (name + '.json'), {'http_status': response.status_code,
                    'body': response.json() if 'json' in response.headers.get('content-type', '') else None})
    receipt = {'endpoint': endpoint, 'url': url, 'image': value['spec']['image'],
               'conversations': len(conversations), 'at': datetime.now(timezone.utc).isoformat(),
               'read_only': True, 'bucket_modified': False, 'endpoint_deleted': False}
    private(output / 'receipt.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', default='sandbox2')
    args = parser.parse_args()
    os.umask(0o077)
    capture(args.endpoint, args.output, profile=args.profile)
