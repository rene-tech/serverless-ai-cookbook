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
        'demos/mcp.cjs': '/opt/hcls-librechat/demos/mcp.cjs',
        'demos/service.cjs': '/opt/hcls-librechat/demos/service.cjs',
        'demos/router.cjs': '/app/api/server/routes/scientific-demos.js',
    }
    script = 'import hashlib,json; print(json.dumps({p:hashlib.sha256(open(p,"rb").read()).hexdigest() for p in ' + repr(list(sources.values())) + '}))'
    actual = json.loads(subprocess.check_output([
        'docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', args.image, '-c', script]))
    for relative, installed in sources.items():
        assert actual[installed] == hashlib.sha256((root / relative).read_bytes()).hexdigest(), relative
    # A label or source-only test cannot detect a missing compiled browser shell.
    browser = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const assets = '/app/client/dist/assets';
const bundles = fs.readdirSync(assets).filter(p => p.endsWith('.js'))
  .map(p => fs.readFileSync(assets + '/' + p, 'utf8')).join('\n');
for (const marker of ['nebius-workspace-brand', 'Getting started & example prompts',
  'Workspace files', 'Upload file to workspace', 'Scientific execution details']) {
  assert.ok(bundles.includes(marker), 'Built browser assets omit ' + marker);
}
assert.ok(fs.readFileSync('/app/client/src/routes/index.tsx', 'utf8').includes("path: 'demos'"));
const query = fs.readFileSync('/app/client/src/data-provider/Subagents/queries.ts', 'utf8').split('const isTerminal =')[0];
assert.ok(query.indexOf('enabled: config?.enabled !== false') > query.indexOf('...config,'), 'Caller can enable new-chat polling');
console.log(JSON.stringify({scientific_shell: true, compiled_branding: true, synthetic_chat_guard: true}));
"""
    browser_result = json.loads(subprocess.check_output([
        'docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'node', args.image, '-e', browser]))
    print(json.dumps({'image_id': inspect['Id'], 'persistent_entrypoint': True,
                      'source_hashes_match': True, 'files': len(sources), **browser_result}))


if __name__ == '__main__':
    main()
