#!/usr/bin/env python3
"""Prepare isolated local baseline/candidate instances without customer state.

Reuse provider credentials privately; never reuse the source customer's platform
key or bucket. Supply a system QA API-key handover separately for App tests.
Explicitly authorized input fixtures can be hash-verified and mounted read-only;
their bytes are not copied into a bucket, repository or evidence workspace.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import time
import urllib.request

import httpx
from replay_agent_instructions import UA


def private_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)


def installed_agent(container):
    script = """
const {MongoClient}=require('mongodb');
(async()=>{const c=new MongoClient(process.env.MONGO_URI);await c.connect();
const a=await c.db().collection('agents').findOne({id:'agent_nebius_scientific_ai'},
{projection:{id:1,instructions:1,model:1,model_parameters:1,tools:1,mcpServerNames:1,skills_enabled:1,artifacts:1,provider:1,_id:0}});
console.log(JSON.stringify(a));await c.close();})().catch(()=>process.exit(1));
"""
    return json.loads(subprocess.check_output(['docker', 'exec', '-w', '/app', container, 'node', '-e', script]))


def input_bindings(manifest):
    """Resolve only the explicit original files in the private dispatch plan."""
    if manifest is None:
        return []
    plan = json.loads(manifest.read_text())
    records, targets = [], set()
    for name in ('private_input_bindings', 'public_input_bindings'):
        for row in plan.get(name, []):
            source, target = Path(row['source']).resolve(strict=True), PurePosixPath(row['target'])
            if (not source.is_file() or row.get('read_only') is not True
                    or not target.is_relative_to('/workspace') or len(target.parts) < 3
                    or '..' in target.parts or str(target) in targets
                    or ',' in str(source) or ',' in str(target)):
                raise ValueError('QA inputs must be distinct read-only files under /workspace.')
            with source.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != row['sha256']:
                raise ValueError('QA input bytes differ from the explicit dispatch-plan hash.')
            records.append({'source': str(source), 'target': str(target), 'sha256': digest,
                            'read_only': True, 'private': name == 'private_input_bindings'})
            targets.add(str(target))
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--source-env', type=Path, required=True)
    p.add_argument('--platform-key', type=Path)
    p.add_argument('--image', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--context-audit', action='store_true',
                   help='Retain only provider counts/finish reasons in this isolated QA workspace')
    p.add_argument('--input-bindings', type=Path,
                   help='Private dispatch plan with explicitly authorized SHA-256-pinned read-only fixture files.')
    a = p.parse_args()
    os.umask(0o077)
    bindings = input_bindings(a.input_bindings)
    root = a.root / a.label
    root.mkdir(parents=True, exist_ok=False)
    workspace = root / 'workspace'
    # Current client images require a separate POSIX state mount. Keep this
    # across qualification restarts just like a managed Serverless instance;
    # never disable persistence checks merely to make a local probe start.
    state = root / 'state'
    state.mkdir(mode=0o700)
    inputs = workspace / 'inputs'
    inputs.mkdir(parents=True)
    if '/workspace/inputs/1UBQ.cif' not in {row['target'] for row in bindings}:
        with urllib.request.urlopen('https://files.rcsb.org/download/1UBQ.cif', timeout=45) as r:
            (inputs / '1UBQ.cif').write_bytes(r.read())
    for row in bindings:
        (workspace / PurePosixPath(row['target']).relative_to('/workspace')).parent.mkdir(parents=True, exist_ok=True)
    if bindings:
        private_json(root / 'input-bindings.json', bindings)
    (inputs / 'sequences.fasta').write_text('>seqA\nACGTACGTNN\n>seqB\nGGCCATTA\n>seqC\nNNNN\n')
    (inputs / 'assay.csv').write_text('condition,response\ncontrol,1\ncontrol,2\ncontrol,3\ntreated,3\ntreated,5\ntreated,7\ntreated,\n')
    allowed = {'NEBIUS_API_KEY', 'TAVILY_API_KEY'}
    env = dict(line.split('=', 1) for line in a.source_env.read_text().splitlines()
               if '=' in line and line.split('=', 1)[0] in allowed)
    if not env.get('NEBIUS_API_KEY'):
        raise ValueError('No provider credential in the explicitly supplied source')
    email = f'qa-{a.label}@scientific-ai.invalid'
    password = secrets.token_urlsafe(24)
    env.update({'SEED_DEFAULT_USER_EMAIL': email, 'SEED_DEFAULT_USER_PASSWORD': password,
                'ALLOW_REGISTRATION': 'false', 'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance',
                'SCIENTIFIC_STUDY_OWNER': email, 'SCIENTIFIC_DISCOVER_CHAT_MODELS': 'false'})
    if a.platform_key:
        handover = json.loads(a.platform_key.read_text())
        env['SCIENTIFIC_MODELS_API_KEY'] = handover.get('secret') or handover.get('token') or handover['api_key']
    if a.context_audit:
        env['SCIENTIFIC_CONTEXT_AUDIT_PATH'] = '/workspace/qualification-provider-counts.json'
    (root / 'runtime.env').write_text(''.join(f'{k}={v}\n' for k, v in env.items()))
    private_json(root / 'login.json', {'email': email, 'password': password})
    name = 'fs2-default-release-' + a.label
    mounts = [arg for row in bindings for arg in (
        '--mount', f'type=bind,source={row["source"]},target={row["target"]},readonly')]
    subprocess.run(['docker', 'run', '-d', '--name', name, '--cpus', '4', '--memory', '12g',
                    '-p', f'127.0.0.1:{a.port}:3080', '--env-file', str(root / 'runtime.env'),
                    '--mount', f'type=bind,source={workspace},target=/workspace',
                    '--mount', f'type=bind,source={state},target=/data', *mounts, a.image],
                   check=True, stdout=subprocess.DEVNULL)
    base = f'http://127.0.0.1:{a.port}'
    headers = {'User-Agent': UA, 'Origin': base}
    with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
        deadline = time.monotonic() + 180
        while True:
            try:
                if client.get('/health').status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError('Local release did not become healthy; preserve container for diagnosis')
            time.sleep(2)
        r = client.post('/api/auth/login', json={'email': email, 'password': password})
        r.raise_for_status()
        session = r.json()
        private_json(root / 'session.json', session)
        client.headers['Authorization'] = 'Bearer ' + session['token']
        agent = installed_agent(name)
        private_json(root / 'agent.json', agent)
        (root / 'instructions.md').write_text(agent['instructions'])
    print(json.dumps({'container': name, 'url': base, 'image': a.image,
                      'model': agent['model'], 'instruction_characters': len(agent['instructions']),
                      'reasoning_effort': agent.get('model_parameters', {}).get('reasoning_effort')}))


if __name__ == '__main__':
    main()
