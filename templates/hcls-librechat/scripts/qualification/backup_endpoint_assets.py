"""Retain account-referenced image bytes before retiring a workbench instance."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx

from restore_endpoint_account import credentials
from backup_endpoint_account import required_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', default='sandbox2')
    parser.add_argument('--browser-user-agent', required=True,
                        help='Browser-compatible User-Agent required by native authenticated APIs')
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    receipt = json.loads((args.backup / 'receipt.json').read_text())
    references = {}
    for path in args.backup.glob('*-messages.json'):
        for message in json.loads(path.read_text()):
            for item in message.get('files', []):
                references[item['file_id']] = item
    with httpx.Client(base_url=receipt['url'], timeout=90, trust_env=False,
                      headers={'User-Agent': args.browser_user_agent}) as client:
        login = client.post('/api/auth/login', json=credentials(args.backup, args.profile))
        login.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + login.json()['token']
        diagnostics = []
        for route in ['/api/files']:
            response = client.get(route, headers={'Accept': 'application/json'})
            diagnostics.append({'route': route, 'status': response.status_code,
                                'content_type': response.headers.get('content-type'), 'bytes': len(response.content)})
            listing = required_json(response)
            if not isinstance(listing, list):
                raise RuntimeError('File listing has an unexpected shape; retain the predecessor')
            (args.output / 'files-private.json').write_text(json.dumps(listing, indent=2))
            references.update({item['file_id']: item for item in listing if item.get('file_id')})
        retained = []
        for index, (file_id, item) in enumerate(references.items()):
            path = item.get('filepath', '')
            if not path.startswith('/images/') or '..' in path or '?' in path:
                raise ValueError('Unexpected attachment storage path; retain predecessor for manual migration')
            response = client.get(path)
            response.raise_for_status()
            media_type = response.headers.get('content-type', '').split(';')[0]
            if not media_type.startswith('image/'):
                raise ValueError('Attachment response is not an image; do not retire predecessor')
            local = f'attachment-{index:04d}.bin'
            (args.output / local).write_bytes(response.content)
            retained.append({'file_id': file_id, 'original': item, 'local': local,
                             'bytes': len(response.content), 'media_type': media_type,
                             'sha256': hashlib.sha256(response.content).hexdigest()})
        result = {'endpoint': receipt['endpoint'], 'files': retained, 'api_diagnostics': diagnostics}
        (args.output / 'receipt-private.json').write_text(json.dumps(result, indent=2))
        print(json.dumps({'retained_images': len(retained), 'total_bytes': sum(row['bytes'] for row in retained),
                          'api_diagnostics': diagnostics}))


if __name__ == '__main__':
    main()
