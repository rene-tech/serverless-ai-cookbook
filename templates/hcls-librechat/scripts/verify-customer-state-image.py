#!/usr/bin/env python3
"""Verify immutable managed-client packaging before promoting an image."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    inspect = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]
    expected = ['/usr/bin/tini', '-s', '--', 'python3',
                '/opt/hcls-librechat/state-supervisor.py', '--',
                '/usr/local/bin/hcls-librechat-entrypoint']
    assert inspect['Config']['Entrypoint'] == expected, 'Persistent-state supervisor missing from entrypoint'
    assert 'SCIENTIFIC_REQUIRE_PERSISTENT_STATE=true' in inspect['Config']['Env']
    sources = {
        'state-supervisor.py': '/opt/hcls-librechat/state-supervisor.py',
        'entrypoint.sh': '/usr/local/bin/hcls-librechat-entrypoint',
        'seed-workbench.js': '/app/seed-hcls-workbench.js',
        'seed-user.js': '/app/seed-user.js',
        'seed-merge.cjs': '/app/seed-merge.cjs',
    }
    script = 'import hashlib,json; print(json.dumps({p:hashlib.sha256(open(p,"rb").read()).hexdigest() for p in ' + repr(list(sources.values())) + '}))'
    actual = json.loads(subprocess.check_output([
        'docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', args.image, '-c', script]))
    for relative, installed in sources.items():
        assert actual[installed] == hashlib.sha256((root / relative).read_bytes()).hexdigest(), relative
    print(json.dumps({'image_id': inspect['Id'], 'persistent_entrypoint': True,
                      'source_hashes_match': True, 'files': len(sources)}))


if __name__ == '__main__':
    main()
