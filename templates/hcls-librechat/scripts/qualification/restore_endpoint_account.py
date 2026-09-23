"""Restore archived chats through LibreChat's supported import API.

Existing same-ID conversations are retained; imported conversations get new IDs.
The original private export stays authoritative for attachments, tool provenance
and resumable execution state, which conversation import does not migrate.
Never print login material or conversation text.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import httpx


def credentials(backup, profile):
    spec = json.loads((backup / 'endpoint-private.json').read_text())['spec']
    variables = {item['name']: item for item in spec['environment_variables']}
    def resolve(name):
        item = variables[name]
        if 'value' in item:
            return item['value']
        secret = item['mysterybox_secret']
        command = ['nebius', '--profile', profile, 'mysterybox', 'payload', 'get',
                   '--secret-id', secret['secret_id'], '--format', 'json']
        if secret.get('version_id'):
            command += ['--version-id', secret['version_id']]
        payload = json.loads(subprocess.check_output(command))
        return next(entry['string_value'] for entry in payload['data'] if entry['key'] == name)
    return {'email': resolve('SEED_DEFAULT_USER_EMAIL'), 'password': resolve('SEED_DEFAULT_USER_PASSWORD')}


def listing(client):
    rows = {}
    cursor = None
    for _ in range(1000):
        response = client.get('/api/convos', params={'limit': 100, **({'cursor': cursor} if cursor else {})})
        response.raise_for_status()
        page = response.json()
        rows.update({row['conversationId']: row for row in page['conversations']})
        cursor = page.get('nextCursor')
        if not cursor:
            return rows
    raise RuntimeError('Pagination did not finish')


def restore_assets(client, assets, output):
    """Re-upload chat images through the native API; keep byte-exact originals."""
    records = json.loads((assets / 'receipt-private.json').read_text())['files']
    mapping = {}
    for record in records:
        content = (assets / record['local']).read_bytes()
        if hashlib.sha256(content).hexdigest() != record['sha256']:
            raise ValueError('Archived image hash differs')
        response = client.post('/api/files/images',
            data={'endpoint': 'agents', 'file_id': str(uuid4())},
            files={'file': (record['original']['filename'], content, record['media_type'])})
        response.raise_for_status()
        uploaded = response.json()
        if 'file' in uploaded:
            uploaded = uploaded['file']
        if not uploaded.get('file_id') or not uploaded.get('filepath', '').startswith('/images/'):
            raise RuntimeError('Image upload returned no native image reference')
        verified = client.get(uploaded['filepath'])
        verified.raise_for_status()
        if not verified.headers.get('content-type', '').startswith('image/'):
            raise RuntimeError('Restored image is not readable')
        mapping[record['file_id']] = uploaded
        (output / 'image-mapping-private.json').write_text(json.dumps(mapping, indent=2))
    return mapping


def migrate_files(messages, mapping):
    # Preserve text and tool results. Only native attachment coordinates change.
    messages = json.loads(json.dumps(messages))
    for message in messages:
        for index, item in enumerate(message.get('files', [])):
            replacement = mapping.get(item['file_id'])
            if replacement is not None:
                message['files'][index] = {**item, **replacement}
    return messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--profile', default='sandbox2')
    args = parser.parse_args()
    if not args.url.startswith('https://'):
        raise ValueError('Use the real TLS endpoint')
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    login_input = credentials(args.backup, args.profile)
    (args.output / 'login-private.json').write_text(json.dumps(login_input))
    with httpx.Client(base_url=args.url, timeout=120, trust_env=False) as client:
        login = client.post('/api/auth/login', json=login_input)
        login.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + login.json()['token']
        cookies = [{'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain,
                    'path': cookie.path, 'expires': cookie.expires or -1,
                    'httpOnly': cookie.has_nonstandard_attr('HttpOnly'), 'secure': cookie.secure,
                    'sameSite': 'Lax'} for cookie in client.cookies.jar]
        (args.output / 'browser-state-private.json').write_text(json.dumps({'cookies': cookies, 'origins': []}))
        image_mapping = restore_assets(client, args.assets, args.output) if args.assets else {}
        records = []
        original = {}
        for path in sorted(args.backup.glob('conversations-*.json')):
            original.update({row['conversationId']: row for row in json.loads(path.read_text())['conversations']})
        before = listing(client)
        for old_id, row in original.items():
            messages = json.loads((args.backup / (old_id + '-messages.json')).read_text())
            messages = migrate_files(messages, image_mapping)
            if old_id in before:
                new_id = old_id
                imported = False
            else:
                payload = {'conversationId': old_id, 'title': row['title'], 'endpoint': row['endpoint'],
                           'messages': messages, 'options': {key: row[key] for key in ('agent_id', 'model', 'endpoint') if key in row}}
                response = client.post('/api/convos/import', files={'file': ('conversation.json', json.dumps(payload).encode(), 'application/json')})
                if response.status_code != 201:
                    raise RuntimeError(f'Chat import failed: HTTP {response.status_code}; predecessor must be retained')
                current = listing(client)
                created = set(current) - set(before)
                if len(created) != 1:
                    raise RuntimeError('Import did not create exactly one conversation')
                new_id = created.pop()
                before = current
                imported = True
            response = client.get('/api/messages/' + new_id)
            response.raise_for_status()
            restored = response.json()
            # Native import may strip transient fields, but no visible message
            # text/content may be silently lost during endpoint replacement.
            signature = lambda message: json.dumps({key: message.get(key) for key in ('text', 'content', 'isCreatedByUser')}, sort_keys=True)
            if sorted(map(signature, messages)) != sorted(map(signature, restored)):
                raise RuntimeError('Restored message content differs; retain predecessor and private archive')
            records.append({'old_id': old_id, 'new_id': new_id, 'messages': len(messages), 'imported': imported})
            (args.output / 'progress.json').write_text(json.dumps(records, indent=2))
        receipt = {'url': args.url, 'conversations_verified': len(records),
                   'messages_verified': sum(row['messages'] for row in records),
                   'imported': sum(row['imported'] for row in records), 'mapping': records,
                   'execution_state_migrated': False, 'original_archive_retained': True}
        receipt['images_restored'] = len(image_mapping)
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
        print(json.dumps({key: value for key, value in receipt.items() if key != 'mapping'}))


if __name__ == '__main__':
    main()
