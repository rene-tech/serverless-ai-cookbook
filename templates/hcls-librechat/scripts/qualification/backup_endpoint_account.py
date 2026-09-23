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
from urllib.parse import quote

import httpx


def private(path, value):
    with path.open('x') as handle:
        path.chmod(0o600)
        json.dump(value, handle, indent=2)
        handle.write('\n')


def required_json(response):
    """HTTP 200 alone is not an export: LibreChat may stream an API error."""
    response.raise_for_status()
    if 'json' not in response.headers.get('content-type', '').lower():
        raise RuntimeError('Account export returned non-JSON; retain the predecessor')
    value = response.json()
    if isinstance(value, dict) and value.get('error'):
        raise RuntimeError('Account export returned an error; retain the predecessor')
    return value


def capture_run_history(client, output):
    """Keep every discoverable operation, not just the first history page."""
    rows, cursors, cursor = {}, set(), None
    for page_number in range(1000):
        params = {'limit': 200, **({'cursor': cursor} if cursor else {})}
        page = required_json(client.get('/api/scientific-demos/runs', params=params))
        if not isinstance(page.get('data'), list) or page.get('history_available') is not True:
            raise RuntimeError('Full operation history is unavailable; retain the predecessor')
        private(output / f'runs-{page_number:04d}.json', page)
        for row in page['data']:
            rows[row['id']] = row
        cursor = page.get('next_cursor')
        if not cursor:
            return {'data': list(rows.values()), 'next_cursor': None,
                    'history_available': True, 'archived_pages': page_number + 1}
        if cursor in cursors:
            raise RuntimeError('Operation history cursor repeated; export is incomplete')
        cursors.add(cursor)
    raise RuntimeError('Operation history pagination bound reached')


def capture_agent_details(client, listing, output):
    """Capture editable details, or explicitly mark server-owned view-only seeds."""
    if not isinstance(listing.get('data'), list) or listing.get('has_more'):
        raise RuntimeError('Agent listing is incomplete; retain the predecessor')
    ids = []
    for row in listing['data']:
        agent_id = row.get('id')
        if not isinstance(agent_id, str) or not agent_id or '/' in agent_id or '..' in agent_id:
            raise RuntimeError('Unexpected agent identity; retain the predecessor')
        path = '/api/agents/' + quote(agent_id, safe='')
        response = client.get(path + '/expanded')
        access = 'editable'
        if response.status_code == 403:
            access = 'view-only'
            response = client.get(path)
        detail = required_json(response)
        if not isinstance(detail, dict) or detail.get('id') != agent_id:
            raise RuntimeError('Expanded agent identity differs; retain the predecessor')
        private(output / ('agent-' + agent_id + '-details.json'), {'access': access, 'body': detail})
        ids.append(agent_id)
    return ids


def capture(endpoint, output, *, profile, browser_user_agent):
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
    with httpx.Client(base_url=url, timeout=90, trust_env=False,
                      headers={'User-Agent': browser_user_agent, 'Accept': 'application/json'}) as client:
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
            listing = required_json(response)
            private(output / f'conversations-{page:04d}.json', listing)
            rows = listing.get('conversations', [])
            fresh = [row for row in rows if row['conversationId'] not in seen]
            for row in fresh:
                conversation_id = row['conversationId']
                if '/' in conversation_id or '..' in conversation_id:
                    raise ValueError('Unexpected conversation ID in account response')
                messages = client.get('/api/messages/' + conversation_id)
                private(output / (conversation_id + '-messages.json'), required_json(messages))
                seen.add(conversation_id)
                conversations.append(conversation_id)
            cursor = listing.get('nextCursor')
            if not fresh or not cursor and len(rows) < 25:
                break
        else:
            raise RuntimeError('Account export pagination bound reached; do not retire the endpoint')
        history = capture_run_history(client, output)
        private(output / 'runs.json', {'http_status': 200, 'body': history})
        agent_ids = []
        for name, path in {'workspace': '/api/scientific-demos/workspace',
                           'studies': '/api/scientific-demos/studies',
                           'clinical': '/api/scientific-demos/clinical',
                           'agents': '/api/agents', 'files': '/api/files',
                           'projects': '/api/projects', 'account-user': '/api/user',
                           'presets': '/api/presets',
                           'favorites': '/api/user/settings/favorites',
                           'tool-favorites': '/api/user/settings/favorites/tools',
                           'active-skills': '/api/user/settings/skills/active'}.items():
            response = client.get(path)
            body = required_json(response)
            private(output / (name + '.json'), {'http_status': response.status_code, 'body': body})
            if name == 'agents' and body.get('has_more') or name == 'projects' and body.get('nextCursor'):
                raise RuntimeError(f'{name} export requires additional pages; retain the predecessor')
            if name == 'agents':
                agent_ids = capture_agent_details(client, body, output)
    receipt = {'endpoint': endpoint, 'url': url, 'image': value['spec']['image'],
               'conversations': len(conversations), 'operation_history_count': len(history['data']),
               'archived_agent_details': len(agent_ids),
               'at': datetime.now(timezone.utc).isoformat(),
               'read_only': True, 'bucket_modified': False, 'endpoint_deleted': False}
    private(output / 'receipt.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', default='sandbox2')
    parser.add_argument('--browser-user-agent', required=True,
                        help='Browser-compatible User-Agent required by native authenticated APIs')
    args = parser.parse_args()
    os.umask(0o077)
    capture(args.endpoint, args.output, profile=args.profile, browser_user_agent=args.browser_user_agent)
