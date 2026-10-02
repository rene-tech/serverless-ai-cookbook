#!/usr/bin/env python3
"""Create an explicitly requested parallel preview using existing bindings.

No tenant, key, bucket, or secret is created. The predecessor is never changed.
A distinct stable study namespace prevents two supervisors adopting the same
work. Keep the output directory private: provider receipts contain secret refs.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess


def save(path, value):
    with open(path, 'w', opener=lambda name, flags: os.open(name, flags, 0o600)) as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def preview(source, name, image, owner, public_key):
    spec = copy.deepcopy(source['spec'])
    env = {v['name']: v for v in spec['environment_variables']}
    prior_owner = env.get('SCIENTIFIC_STUDY_OWNER', env.get('SEED_DEFAULT_USER_EMAIL', {})).get('value')
    if not owner or owner == prior_owner:
        raise ValueError('A parallel preview needs its own stable study owner namespace')
    for required in ('SCIENTIFIC_MODELS_API_KEY', 'NEBIUS_API_KEY', 'TAVILY_API_KEY',
                     'SEED_DEFAULT_USER_PASSWORD'):
        if 'mysterybox_secret' not in env.get(required, {}):
            raise ValueError('Expected an existing secret reference for ' + required)
    for key, value in {'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance',
                       'SCIENTIFIC_STUDY_OWNER': owner,
                       'SCIENTIFIC_CHAT_MODEL': 'moonshotai/Kimi-K3',
                       'SCIENTIFIC_CHAT_REASONING_EFFORT': 'high',
                       'SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS': '131072',
                       'SCIENTIFIC_CHAT_MAX_OUTPUT_TOKENS': '16384',
                       'SCIENTIFIC_AGENT_MODEL_DEADLINE_MS': '90000',
                       'SCIENTIFIC_AGENT_MODEL_TIME_MS': '300000',
                       'SCIENTIFIC_AGENT_REPEAT_ROUNDS': '2',
                       'SCIENTIFIC_CONTEXT_AUDIT_PATH': '',
                       'ALLOW_REGISTRATION': 'false'}.items():
        env[key] = {'name': key, 'value': value}
    spec['environment_variables'] = list(env.values())
    spec['image'] = image
    spec['ssh_authorized_keys'] = list(dict.fromkeys(spec.get('ssh_authorized_keys', []) + [public_key]))
    return {'metadata': {'parent_id': source['metadata']['parent_id'], 'name': name}, 'spec': spec}


def create_args(request, s3_profile):
    spec = request['spec']
    supported = {'image', 'platform', 'preset', 'disk', 'subnet_id', 'ports', 'public_ip',
                 'ssh_authorized_keys', 'environment_variables', 'volumes'}
    if set(spec) - supported:
        raise ValueError('Source contains settings requiring explicit handling: ' + ','.join(set(spec) - supported))
    args = ['ai', 'endpoint', 'create', '--parent-id', request['metadata']['parent_id'],
            '--name', request['metadata']['name'], '--image', spec['image'],
            '--platform', spec['platform'], '--preset', spec['preset'],
            '--disk-size', str(int(spec['disk']['size_bytes']) // (1024**3)) + 'Gi',
            '--subnet-id', spec['subnet_id'], '--public=' + str(spec.get('public_ip', False)).lower()]
    for port in spec['ports']:
        if port['container_port'] != port['host_port']:
            raise ValueError('Remapped source ports are not supported by this helper')
        args += ['--container-port', str(port['container_port']) + '/' + port['protocol'].lower()]
    for key in spec['ssh_authorized_keys']:
        args += ['--ssh-key', key]
    for mount in spec['volumes']:
        mode = {'READ_WRITE': 'rw', 'READ_ONLY': 'ro'}[mount['mode']]
        if mount['source'].startswith('computefilesystem-'):
            args += ['--volume', f"{mount['source']}:{mount['container_path']}:{mode}"]
        else:
            ref = mount['s3_config']['mysterybox_secret']
            args += ['--volume', f"{mount['source']}:{mount['container_path']}:{mode}:{s3_profile}@{ref['secret_id']}@{ref['version_id']}"]
    for var in spec['environment_variables']:
        if 'mysterybox_secret' in var:
            ref = var['mysterybox_secret']
            args += ['--env-secret', f"{var['name']}={ref['secret_id']}@{ref['version_id']}"]
        else:
            args += ['--env', var['name'] + '=' + var.get('value', '')]
    return args


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source-endpoint', 'project', 'name', 'image', 'study-owner', 's3-profile'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--cli', default='nebius')
    p.add_argument('--profile', default='sandbox2')
    p.add_argument('--ssh-public-key', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--state-filesystem', help='Dedicated empty QA state filesystem; never share the source state')
    a = p.parse_args()
    os.umask(0o077)
    a.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if a.output.stat().st_mode & 0o077:
        raise ValueError('The receipt directory must be private')
    cli = [a.cli, '--profile', a.profile, '--no-browser', '--no-check-update', '--format', 'json']

    def cloud(args, label, json_output=True):
        result = subprocess.run(cli + args, text=True, capture_output=True, timeout=120)
        save(a.output / (label + '-private.json'), {'exit_code': result.returncode,
             'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode:
            raise RuntimeError(label + ' failed; inspect the retained private receipt before retry')
        return json.loads(result.stdout) if json_output else None

    source = cloud(['ai', 'endpoint', 'get', '--id', a.source_endpoint], 'source')
    if source['metadata']['parent_id'] != a.project:
        raise ValueError('Source endpoint belongs to a different project')
    request = preview(source, a.name, a.image, a.study_owner, a.ssh_public_key.read_text().strip())
    if a.state_filesystem:
        if not a.state_filesystem.startswith('computefilesystem-'):
            raise ValueError('State must use a Nebius filesystem')
        if any(m['source'] == a.state_filesystem or m['container_path'] == '/data' for m in request['spec']['volumes']):
            raise ValueError('A parallel preview must never mount the predecessor state filesystem')
        request['spec']['volumes'].append({'source': a.state_filesystem, 'container_path': '/data', 'mode': 'READ_WRITE'})
        request['spec']['environment_variables'].append({'name': 'SCIENTIFIC_REQUIRE_PERSISTENT_STATE', 'value': 'true'})
    save(a.output / 'request-private.json', request)
    listing = cloud(['ai', 'endpoint', 'list', '--parent-id', a.project], 'inventory')
    if listing.get('next_page_token'):
        raise RuntimeError('Paginated inventory must be reconciled before creation')
    matches = [v for v in listing['items'] if v['metadata']['name'] == a.name]
    if matches:
        existing = cloud(['ai', 'endpoint', 'get', '--id', matches[0]['metadata']['id']], 'existing')
        if existing['spec'] != request['spec']:
            raise RuntimeError('Existing preview differs from this request; never create a duplicate')
        print(json.dumps({'endpoint': existing['metadata']['id'], 'state': existing['status']['state'], 'reused': True}))
        return
    if (a.output / 'creation-attempt.json').exists():
        raise RuntimeError('An earlier creation is unresolved; reconcile it before any retry')
    command = create_args(request, a.s3_profile)
    cloud(command + ['--dry-run'], 'dry-run', json_output=False)
    if a.apply:
        save(a.output / 'creation-attempt.json', {'name': a.name, 'source_endpoint': a.source_endpoint})
        cloud(command + ['--async'], 'create', json_output=False)
    print(json.dumps({'name': a.name, 'image': a.image, 'dry_run': 'passed',
                      'creation_requested': a.apply, 'source_endpoint_changed': False}))


if __name__ == '__main__':
    main()
