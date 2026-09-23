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
import re
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


def image_metadata(record):
    """Match LibreChat's native image-upload contract, including dimensions."""
    original = record['original']
    dimensions = {name: int(original[name]) for name in ('width', 'height')}
    if any(value <= 0 for value in dimensions.values()):
        raise ValueError('Archived image lacks valid dimensions')
    return {'endpoint': 'agents', 'file_id': str(uuid4()),
            **{name: str(value) for name, value in dimensions.items()}}


def restore_assets(client, assets, output):
    """Re-upload chat images through the native API; keep byte-exact originals."""
    records = json.loads((assets / 'receipt-private.json').read_text())['files']
    mapping_path = output / 'image-mapping-private.json'
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    for record in records:
        content = (assets / record['local']).read_bytes()
        if hashlib.sha256(content).hexdigest() != record['sha256']:
            raise ValueError('Archived image hash differs')
        if record['file_id'] in mapping:
            response = client.get(mapping[record['file_id']]['filepath'])
            response.raise_for_status()
            if not response.headers.get('content-type', '').startswith('image/'):
                raise RuntimeError('Previously restored image is no longer readable')
            continue
        response = client.post('/api/files/images',
            data=image_metadata(record),
            files={'file': (record['original']['filename'], content, record['media_type'])})
        if response.is_error:
            (output / 'image-upload-error-private.bin').write_bytes(response.content)
        response.raise_for_status()
        try:
            uploaded = response.json()
        except ValueError as exc:
            (output / 'image-upload-response-private.bin').write_bytes(response.content)
            diagnostic = {'status': response.status_code, 'bytes': len(response.content),
                          'content_type': response.headers.get('content-type'),
                          'content_encoding': response.headers.get('content-encoding')}
            (output / 'image-upload-diagnostic.json').write_text(json.dumps(diagnostic, indent=2))
            raise RuntimeError('Image upload returned non-JSON; private diagnostics retained') from exc
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


def message_signature(message):
    """Native import removes transient assistant inline-UI handles, not prose.

    Preserve all tool content and user text. Only the exact renderer token shape
    observed in LibreChat's import is normalized. The raw archive stays intact.
    """
    value = json.loads(json.dumps({key: message.get(key) for key in
                                ('text', 'content', 'isCreatedByUser')}))
    if not value['isCreatedByUser']:
        strip_handle = lambda text: re.sub(r'\\ui\{[0-9a-f]{10}\}', '', text)
        if isinstance(value['text'], str):
            value['text'] = strip_handle(value['text'])
        for block in value['content'] or []:
            if block.get('type') == 'text' and isinstance(block.get('text'), str):
                block['text'] = strip_handle(block['text'])
    return json.dumps(value, sort_keys=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--profile', default='sandbox2')
    parser.add_argument('--browser-user-agent', required=True,
                        help='Browser-compatible User-Agent for the authenticated native file API')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--session-state', type=Path,
                        help='Reuse an existing authenticated browser session instead of another password login')
    args = parser.parse_args()
    if not args.url.startswith('https://'):
        raise ValueError('Use the real TLS endpoint')
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=args.resume)
    with httpx.Client(base_url=args.url, timeout=120, trust_env=False,
                      headers={'User-Agent': args.browser_user_agent}) as client:
        if args.session_state:
            state = json.loads(args.session_state.read_text())
            for cookie in state['cookies']:
                client.cookies.set(cookie['name'], cookie['value'],
                                   domain=cookie['domain'], path=cookie['path'])
            login = client.post('/api/auth/refresh')
        else:
            login_input = credentials(args.backup, args.profile)
            (args.output / 'login-private.json').write_text(json.dumps(login_input))
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
        import_path = args.output / 'imports-private.json'
        imported_ids = json.loads(import_path.read_text()) if import_path.exists() else {}
        progress_path = args.output / 'progress.json'
        if progress_path.exists():
            imported_ids.update({item['old_id']: item['new_id'] for item in json.loads(progress_path.read_text())})
        original = {}
        for path in sorted(args.backup.glob('conversations-*.json')):
            original.update({row['conversationId']: row for row in json.loads(path.read_text())['conversations']})
        before = listing(client)
        for old_id, row in original.items():
            messages = json.loads((args.backup / (old_id + '-messages.json')).read_text())
            messages = migrate_files(messages, image_mapping)
            if old_id in imported_ids:
                new_id = imported_ids[old_id]
                if new_id not in before:
                    raise RuntimeError('Previously imported conversation is missing; do not duplicate it')
                imported = True
            elif old_id in before:
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
                imported_ids[old_id] = new_id
                import_path.write_text(json.dumps(imported_ids, indent=2))
            response = client.get('/api/messages/' + new_id)
            response.raise_for_status()
            restored = response.json()
            # Native import may strip transient fields, but no visible message
            # text/content may be silently lost during endpoint replacement.
            if sorted(map(message_signature, messages)) != sorted(map(message_signature, restored)):
                (args.output / 'content-mismatch-private.json').write_text(json.dumps(
                    {'old_id': old_id, 'new_id': new_id, 'before': messages, 'after': restored}, indent=2))
                raise RuntimeError('Restored message content differs; retain predecessor and private archive')
            file_refs = lambda rows: sorted((file['file_id'], file.get('filepath'))
                                           for row in rows for file in row.get('files', []))
            if file_refs(messages) != file_refs(restored):
                raise RuntimeError('Restored attachment coordinates differ')
            records.append({'old_id': old_id, 'new_id': new_id, 'messages': len(messages), 'imported': imported})
            (args.output / 'progress.json').write_text(json.dumps(records, indent=2))
        receipt = {'url': args.url, 'conversations_verified': len(records),
                   'messages_verified': sum(row['messages'] for row in records),
                   'imported': sum(row['imported'] for row in records), 'mapping': records,
                   'execution_state_migrated': False, 'original_archive_retained': True}
        receipt['images_restored'] = len(image_mapping)
        receipt['transient_inline_ui_handles_migrated'] = False
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
        print(json.dumps({key: value for key, value in receipt.items() if key != 'mapping'}))


if __name__ == '__main__':
    main()
