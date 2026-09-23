"""Publish only the frozen <=100 MB public preview after stop-first replacement.

Default is a read-only plan. --publish uses the existing exclusive-create
workspace API, never S3 overwrite/delete, quota changes, or endpoint mutations.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import subprocess

import httpx

from restore_endpoint_account import credentials

PREFIX = 'demo-assets/four-engine-alanine-20260923'
MAX_BYTES = 100_000_000


def measured(path):
    with path.open('rb') as source:
        before = os.fstat(source.fileno())
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
        after = os.fstat(source.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Preview source changed while hashing')
    return {'size_bytes': before.st_size, 'sha256': digest}


def inventory(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Use the explicit frozen preview directory, not a link')
    rows, total = [], 0
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Preview links are not followed')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('Preview contains a non-regular file')
        total += path.stat().st_size
        if total > MAX_BYTES:
            raise ValueError('Preview exceeds the requested 100 MB limit; no upload allowed')
        row = measured(path)
        if row['size_bytes'] != path.stat().st_size:
            raise ValueError('Preview changed during inventory')
        total = sum(item['size_bytes'] for item in rows) + row['size_bytes']
        if total > MAX_BYTES:
            raise ValueError('Preview exceeds the requested 100 MB limit; no upload allowed')
        rows.append({'relative': path.relative_to(root).as_posix(), **row})
    if not rows:
        raise ValueError('Preview is empty')
    return rows


def cli(profile, *arguments):
    try:
        return json.loads(subprocess.check_output(
            ['nebius', '--profile', profile, *arguments, '--format', 'json'], stderr=subprocess.PIPE))
    except subprocess.CalledProcessError:
        raise RuntimeError('Provider read failed; no endpoint, bucket or quota was changed') from None


def resolve_variable(variable, profile):
    if 'value' in variable:
        return variable['value']
    secret = variable['mysterybox_secret']
    args = ['mysterybox', 'payload', 'get', '--secret-id', secret['secret_id']]
    if secret.get('version_id'):
        args += ['--version-id', secret['version_id']]
    payload = cli(profile, *args)
    return next(row['string_value'] for row in payload['data'] if row['key'] == variable['name'])


def binding(live, backup, storage, image):
    if live['metadata']['id'] == backup['metadata']['id']:
        raise ValueError('Preview publication waits for the replacement; predecessor is untouched')
    if live['status']['state'] != 'RUNNING' or live['spec']['image'] != image:
        raise ValueError('Replacement is not running the exact qualified image')
    old, new = backup['spec'], live['spec']
    if old['volumes'] != new['volumes'] or storage.get('state') != 'ready':
        raise ValueError('Workspace binding changed or customer storage is not ready')
    old_vars = {item['name']: item for item in old['environment_variables']}
    new_vars = {item['name']: item for item in new['environment_variables']}
    for name in ('SCIENTIFIC_MODELS_API_KEY', 'SCIENTIFIC_MODELS_API_BASE_URL',
                 'SEED_DEFAULT_USER_EMAIL', 'SEED_DEFAULT_USER_PASSWORD'):
        if old_vars[name] != new_vars[name]:
            raise ValueError('Customer account/key binding changed')
    mounts = [item for item in new['volumes'] if item['container_path'] == '/workspace']
    if (len(mounts) != 1 or mounts[0]['source'] != 's3://' + storage['bucket_name']
            or mounts[0]['mode'] != 'READ_WRITE'):
        raise ValueError('Mounted workspace does not match the caller-owned bucket')


def headroom(storage, provider):
    status = provider['status']
    if status['state'] != 'ACTIVE' or status['suspension_state'] != 'NOT_SUSPENDED':
        raise ValueError('Provider bucket is not active and writable')
    quota = int(provider['spec']['max_size_bytes'])
    if quota <= 0 or quota != int(storage['quota_bytes']):
        raise ValueError('Provider and caller storage quotas differ; no quota is changed')
    if not status.get('counters'):
        raise ValueError('Provider usage counters are unavailable; do not guess free space')
    used = 0
    for group in status['counters']:
        for name in ('counters', 'non_current_counters'):
            counter = group.get(name, {})
            values = [int(counter.get(key, 0)) for key in
                      ('simple_objects_size', 'multipart_objects_size', 'inflight_parts_size')]
            if any(value < 0 for value in values):
                raise ValueError('Invalid provider usage counter')
            used += sum(values)
    return {'allocated_bytes': quota, 'used_bytes': used, 'headroom_bytes': quota - used,
            'usage_basis': 'fresh provider counters, including noncurrent versions and inflight parts'}


def existing(client, relative, expected):
    with client.stream('GET', '/api/scientific-demos/workspace/file', params={'path': relative}) as response:
        if response.status_code == 404:
            return False
        response.raise_for_status()
        size, digest = 0, hashlib.sha256()
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > expected['size_bytes']:
                raise ValueError('Existing preview differs; no overwrite allowed')
            digest.update(chunk)
    if size != expected['size_bytes'] or digest.hexdigest() != expected['sha256']:
        raise ValueError('Existing preview differs; no overwrite allowed')
    return True


def publish_files(client, source, rows, *, publish, capacity, progress):
    # Check every destination before writing any file. An interrupted attempt
    # can be rerun: identical completed files are verified and reused.
    missing = [row for row in rows if not existing(client, PREFIX + '/' + row['relative'], row)]
    needed = sum(row['size_bytes'] for row in missing)
    usage = capacity()  # Fresh quota/usage after all pre-existing content checks.
    if needed > usage['headroom_bytes']:
        raise ValueError('Insufficient current workspace headroom; nothing is uploaded or deleted')
    progress.update(usage=usage, new_bytes=needed, total_preview_bytes=sum(row['size_bytes'] for row in rows),
                    files=rows, verified_uploaded=[], reused_files=len(rows) - len(missing))
    if not publish:
        return
    for row in missing:
        path, relative = source / row['relative'], PREFIX + '/' + row['relative']
        if measured(path) != {key: row[key] for key in ('size_bytes', 'sha256')}:
            raise ValueError('Frozen preview changed; no further files uploaded')
        with path.open('rb') as content:
            response = client.post('/api/scientific-demos/workspace', data={'path': relative},
                files={'file': (path.name, content, mimetypes.guess_type(path.name)[0] or 'application/octet-stream')})
        if response.status_code != 409:
            response.raise_for_status()
        # A raced exclusive-create is acceptable only for identical full bytes.
        if not existing(client, relative, row):
            raise RuntimeError('Uploaded preview is not readable; preserve the partial attempt')
        progress['verified_uploaded'].append(row['relative'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', required=True, type=Path, help='Original predecessor account export')
    parser.add_argument('--endpoint', required=True, help='Exact replacement endpoint ID, not the predecessor')
    parser.add_argument('--image', required=True)
    parser.add_argument('--preview', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True, help='SHA256 of canonical sorted local inventory')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--profile', default='sandbox2')
    parser.add_argument('--browser-user-agent', required=True)
    parser.add_argument('--session-state', type=Path, help='Reuse restored-account browser cookies')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if args.output.exists() or '@sha256:' not in args.image:
        raise ValueError('Use a new private receipt path and exact qualified image')
    rows = inventory(args.preview)
    manifest_sha256 = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if manifest_sha256 != args.manifest_sha256:
        raise ValueError('Frozen preview inventory changed; no cloud request or upload was made')
    backup = json.loads((args.backup / 'endpoint-private.json').read_text())
    live = cli(args.profile, 'ai', 'endpoint', 'get', '--id', args.endpoint)
    variables = {item['name']: item for item in live['spec']['environment_variables']}
    key = resolve_variable(variables['SCIENTIFIC_MODELS_API_KEY'], args.profile)
    base = variables['SCIENTIFIC_MODELS_API_BASE_URL']['value'].rstrip('/').removesuffix('/v1')
    with httpx.Client(timeout=90, trust_env=False) as platform:
        response = platform.get(base + '/v1/storage', headers={'Authorization': 'Bearer ' + key})
        response.raise_for_status()
        storage = response.json()
    binding(live, backup, storage, args.image)
    url = next(item for item in live['status']['public_endpoints'] if item.startswith('https://'))
    receipt = {'endpoint': args.endpoint, 'image': args.image, 'workspace_prefix': '/workspace/' + PREFIX,
               'local_inventory_sha256': manifest_sha256,
               'recorded_at': datetime.now(timezone.utc).isoformat(), 'dry_run': not args.publish,
               'endpoint_changed': False, 'quota_changed': False, 'existing_data_deleted': False,
               'customer_ready': False, 'status': 'in_progress'}
    try:
        with httpx.Client(base_url=url, timeout=180, trust_env=False,
                          headers={'User-Agent': args.browser_user_agent}) as client:
            if args.session_state:
                for cookie in json.loads(args.session_state.read_text())['cookies']:
                    client.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])
                login = client.post('/api/auth/refresh')
            else:
                login = client.post('/api/auth/login', json=credentials(args.backup, args.profile))
            login.raise_for_status()
            client.headers['Authorization'] = 'Bearer ' + login.json()['token']
            mounted = client.get('/api/scientific-demos/workspace')
            mounted.raise_for_status()
            info = mounted.json()['info']
            if (not info.get('mounted') or info.get('mount_path') != '/workspace'
                    or info.get('team_bucket_name') != storage['bucket_name']):
                raise ValueError('Actual workbench mount differs from the authorized bucket')
            capacity = lambda: headroom(storage, cli(args.profile, 'storage', 'bucket', 'get-by-name',
                '--parent-id', live['metadata']['parent_id'], '--name', storage['bucket_name']))
            publish_files(client, args.preview, rows, publish=args.publish, capacity=capacity, progress=receipt)
            receipt['status'] = 'published_verified' if args.publish else 'dry_run_ready'
    except Exception as error:
        receipt.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as output:
            json.dump(receipt, output, indent=2)
            output.write('\n')
    print(json.dumps({name: receipt[name] for name in
                     ('status', 'workspace_prefix', 'dry_run', 'new_bytes', 'total_preview_bytes', 'usage')}))


if __name__ == '__main__':
    main()
