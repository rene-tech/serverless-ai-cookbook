"""CPU-only inventory of this immutable portable installation; no cloud access."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[^@\s]+@sha256:[0-9a-f]{64}', args.image):
        raise ValueError('Supply your complete immutable image reference')
    result = subprocess.run([sys.executable, '-I', '/opt/isaac-healthcare/scripts/verify_runtime.py'],
                            stdout=subprocess.PIPE, stderr=sys.stderr, check=True)
    # Keep ordinary source-check diagnostics on stderr; stdout is the inventory.
    sys.stderr.buffer.write(result.stdout)
    contract = json.loads(Path(__file__).with_name('source-paths.json').read_bytes())
    if contract['schema'] != 'isaac-healthcare-owned-source-paths/v1':
        raise ValueError('Source ownership contract is missing')
    files = {}
    for name, owner in contract['files'].items():
        path = Path(name)
        if not path.is_absolute() or not owner:
            raise ValueError('Execution source needs an absolute path and declared owner')
        files[name] = {'owner': owner, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    distributions = {d.metadata['Name'].lower().replace('_', '-'): {'version': d.version}
                     for d in importlib.metadata.distributions()}
    print(json.dumps({'schema': 'isaac-healthcare-customer-installation/v1',
        'runtime_sources': {'schema': 'isaac-healthcare-runtime-source-contract/v1',
                            'portable_image': args.image, 'files': files},
        'distributions': {'distributions': distributions}}, sort_keys=True))


if __name__ == '__main__':
    main()
