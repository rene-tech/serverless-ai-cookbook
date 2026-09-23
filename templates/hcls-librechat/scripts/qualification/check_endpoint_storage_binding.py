"""Read-only check that the mounted workspace and customer's API share a bucket."""
import argparse
import json
from pathlib import Path
import subprocess

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--profile', default='sandbox2')
    args = parser.parse_args()
    spec = json.loads((args.backup / 'endpoint-private.json').read_text())['spec']
    variables = {item['name']: item for item in spec['environment_variables']}
    item = variables['SCIENTIFIC_MODELS_API_KEY']
    if 'value' in item:
        key = item['value']
    else:
        secret = item['mysterybox_secret']
        command = ['nebius', '--profile', args.profile, 'mysterybox', 'payload', 'get',
                   '--secret-id', secret['secret_id'], '--format', 'json']
        if secret.get('version_id'):
            command += ['--version-id', secret['version_id']]
        payload = json.loads(subprocess.check_output(command))
        key = next(entry['string_value'] for entry in payload['data'] if entry['key'] == item['name'])
    base = variables['SCIENTIFIC_MODELS_API_BASE_URL']['value'].rstrip('/').removesuffix('/v1')
    with httpx.Client(timeout=90, trust_env=False) as client:
        response = client.get(base.rstrip('/') + '/v1/storage', headers={'Authorization': 'Bearer ' + key})
        response.raise_for_status()
        storage = response.json()
    mounted = [volume['source'].removeprefix('s3://') for volume in spec['volumes'] if volume['source'].startswith('s3://')]
    expected = storage['bucket_name']
    if mounted != [expected]:
        raise ValueError('Mounted bucket differs from the authorized customer bucket; do not replace blindly')
    print(json.dumps({'workspace_matches_api_bucket': True, 'mounts': len(mounted)}))


if __name__ == '__main__':
    main()
