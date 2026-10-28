"""Prepare a finite provider Job offline; never uploads or contacts the provider."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


def prepare(args):
    if not re.fullmatch(r'[^\s]+@sha256:[a-f0-9]{64}', args.image):
        raise ValueError('Use the full immutable digest of your portable image')
    if args.disk_gib <= 0 or args.shm_gib < 0 or args.timeout_seconds <= 0:
        raise ValueError('Disk/timeout must be positive and shared memory nonnegative')
    source = Path(__file__).resolve().parent
    transfer = json.loads(args.transfer_config.read_text())
    if 'claim' in transfer:
        raise ValueError('Finite Job mode needs only input GET and output PUT; omit the Endpoint claim')
    for name in ('input', 'output'):
        parsed = urlsplit(transfer[name]['url'])
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('Use direct scoped HTTPS object URLs')
    if not re.fullmatch(r'[a-f0-9]{64}', transfer['input']['sha256']):
        raise ValueError('Input integrity needs a complete SHA-256')
    for value in (transfer['input']['size_bytes'], transfer['output']['max_bytes'], transfer['execution_timeout_s']):
        if type(value) is not int or value <= 0:
            raise ValueError('Transfer byte budgets and execution timeout must be positive integers')
    if transfer['execution_timeout_s'] >= args.timeout_seconds:
        raise ValueError('Job timeout must leave time beyond science for transfer and shutdown')
    if transfer['output'].get('headers', {}).get('Content-Type') != 'application/x-tar':
        raise ValueError('The output PUT must sign Content-Type: application/x-tar')
    command = ['/opt/holoscan-video/launch.sh', 'python3', '-I', '/run/holoscan_bundle.py']
    command_bytes = (json.dumps(command, indent=2) + '\n').encode()
    transfer['command_sha256'] = hashlib.sha256(command_bytes).hexdigest()
    inject = {
        '/run/holoscan_transfer.py': (source / 'transfer.py').read_bytes(),
        '/run/holoscan_bundle.py': (source / 'run_bundle.py').read_bytes(),
        '/run/command.json': command_bytes,
        '/run/transfer.json': (json.dumps(transfer, indent=2) + '\n').encode(),
    }
    public_keys = []
    if args.ssh_public_key:
        public = args.ssh_public_key.read_text().strip()
        if '\n' in public or not public.startswith(('ssh-', 'ecdsa-')) or len(public.split()) < 2:
            raise ValueError('Supply one existing OpenSSH public key, never a private key')
        public_keys.append(public)
    request = {
        'metadata': {'parent_id': args.project, 'name': args.name},
        'spec': {
            'image': args.image,
            'container_command': '/opt/holoscan-video/launch.sh',
            'args': 'python3 -I /run/holoscan_transfer.py --config /run/transfer.json --command /run/command.json',
            'platform': args.platform, 'preset': args.preset,
            'disk': {'type': 'NETWORK_SSD', 'size_bytes': str(args.disk_gib * 1024**3)},
            'shm_size_bytes': str(args.shm_gib * 1024**3),
            'timeout': str(args.timeout_seconds) + 's', 'restart_attempts': 0,
            'pricing_model': {'on_demand': {}},
            'public_ip': bool(public_keys), 'ssh_authorized_keys': public_keys,
            'ports': [], 'volumes': [],
            'injected_files': [{'container_path': name, 'content': base64.b64encode(data).decode()}
                               for name, data in inject.items()],
        },
        'dry_run': True,
    }
    os.umask(0o077)
    with args.output.open('x') as target:
        json.dump(request, target, indent=2)
        target.write('\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'project', 'name', 'platform', 'preset'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--transfer-config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--disk-gib', type=int, default=100)
    p.add_argument('--shm-gib', type=int, default=16)
    p.add_argument('--timeout-seconds', type=int, default=2400)
    p.add_argument('--ssh-public-key', type=Path)
    prepare(p.parse_args())
