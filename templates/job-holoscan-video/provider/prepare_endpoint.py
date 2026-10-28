"""Prepare an exact typed-API shape offline; never contacts the provider."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re


def prepare(args):
    if not re.fullmatch(r'.+@sha256:[a-f0-9]{64}', args.image):
        raise ValueError('Use the immutable digest of your portable image')
    if args.disk_gib <= 0 or args.shm_gib < 0:
        raise ValueError('Disk must be positive and shared memory nonnegative')
    source = Path(__file__).resolve().parent
    command = ['/opt/holoscan-video/launch.sh', 'python3', '-I', '/run/holoscan_bundle.py']
    command_bytes = (json.dumps(command, indent=2) + '\n').encode()
    transfer = json.loads(args.transfer_config.read_text())
    if transfer.get('claim', {}).get('headers', {}).get('If-None-Match') != '*':
        raise ValueError('Endpoint fallback requires a conditional start-marker PUT capability')
    transfer['command_sha256'] = hashlib.sha256(command_bytes).hexdigest()
    inject = {
        '/run/holoscan_transfer.py': (source / 'transfer.py').read_bytes(),
        '/run/holoscan_bundle.py': (source / 'run_bundle.py').read_bytes(),
        '/run/command.json': command_bytes,
        '/run/transfer.json': (json.dumps(transfer, indent=2) + '\n').encode(),
    }
    request = {
        'metadata': {'parent_id': args.project, 'name': args.name},
        'spec': {
            'image': args.image,
            'container_command': '/opt/holoscan-video/launch.sh',
            'args': 'python3 -I /run/holoscan_transfer.py --config /run/transfer.json --command /run/command.json --endpoint-idle',
            'platform': args.platform, 'preset': args.preset,
            'disk': {'type': 'NETWORK_SSD', 'size_bytes': str(args.disk_gib * 1024**3)},
            'shm_size_bytes': str(args.shm_gib * 1024**3),
            'pricing_model': {'on_demand': {}}, 'public_ip': False, 'ports': [],
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
    prepare(p.parse_args())
