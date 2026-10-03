"""Exercise the local qualification launcher without containers or remote calls."""

import io
import hashlib
import json
import os
import sys

import httpx
import pytest

import prepare_default_release as launcher


@pytest.mark.parametrize('with_bindings', [False, True])
def test_separate_state_and_workspace_mounts_preserve_restart_boundary(tmp_path, monkeypatch, with_bindings):
    source = tmp_path / 'source.env'
    source.write_text('NEBIUS_API_KEY=provider-fixture\nSCIENTIFIC_MODELS_API_KEY=customer-not-allowed\n')
    key = tmp_path / 'qa.json'
    key.write_text(json.dumps({'secret': 'system-qa-fixture'}))
    root = tmp_path / 'evidence'
    arguments = ['prepare', '--root', str(root), '--source-env', str(source),
        '--platform-key', str(key), '--image', 'registry.invalid/client@sha256:' + 'a' * 64,
        '--label', 'candidate', '--port', '13205']
    if with_bindings:
        fixture = tmp_path / 'original.cif'
        fixture.write_bytes(b'original fixture')
        plan = tmp_path / 'plan.json'
        plan.write_text(json.dumps({'private_input_bindings': [{
            'source': str(fixture), 'target': '/workspace/inputs/1UBQ.cif',
            'sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(), 'read_only': True}]}))
        arguments += ['--input-bindings', str(plan)]
    monkeypatch.setattr(sys, 'argv', arguments)
    downloads = []

    def download(*args, **kwargs):
        downloads.append(args)
        return io.BytesIO(b'fixture')

    monkeypatch.setattr(launcher.urllib.request, 'urlopen', download)
    commands = []
    monkeypatch.setattr(launcher.subprocess, 'run', lambda command, **kwargs: commands.append(command))
    monkeypatch.setattr(launcher, 'installed_agent', lambda container: {
        'instructions': 'seeded fixture', 'model': 'moonshotai/Kimi-K3',
        'model_parameters': {'reasoning_effort': 'high'}})
    requests = []

    def handle(request):
        requests.append((request.method, request.url.path))
        return httpx.Response(200, json={'token': 'login-fixture'})

    client = httpx.Client
    monkeypatch.setattr(launcher.httpx, 'Client',
                        lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(handle)))
    original_umask = os.umask(0o077)
    try:
        launcher.main()
        with pytest.raises(FileExistsError):
            launcher.main()
    finally:
        os.umask(original_umask)
    assert len(commands) == 1
    command = commands[0]
    assert 'type=bind,source=' + str(root / 'candidate/workspace') + ',target=/workspace' in command
    assert 'type=bind,source=' + str(root / 'candidate/state') + ',target=/data' in command
    assert (root / 'candidate/state').stat().st_mode & 0o777 == 0o700
    assert requests == [('GET', '/health'), ('POST', '/api/auth/login')]
    environment = (root / 'candidate/runtime.env').read_text()
    assert 'SCIENTIFIC_MODELS_API_KEY=system-qa-fixture\n' in environment
    assert 'customer-not-allowed' not in environment
    assert 'PERSISTENCE' not in environment
    assert json.loads((root / 'candidate/agent.json').read_text())['model_parameters']['reasoning_effort'] == 'high'
    if with_bindings:
        assert f'type=bind,source={fixture},target=/workspace/inputs/1UBQ.cif,readonly' in command
        assert fixture.read_bytes() == b'original fixture'
        assert not (root / 'candidate/workspace/inputs/1UBQ.cif').exists()
        assert (root / 'candidate/input-bindings.json').stat().st_mode & 0o777 == 0o600
        assert downloads == []
    else:
        assert len(downloads) == 1


@pytest.mark.parametrize('change', ['hash', 'writable', 'escape', 'duplicate'])
def test_input_binding_rejects_wrong_bytes_or_mutable_ambiguous_mount(tmp_path, change):
    fixture = tmp_path / 'original.cif'
    fixture.write_bytes(b'original fixture')
    row = {'source': str(fixture), 'target': '/workspace/private/original.cif',
           'sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(), 'read_only': True}
    if change == 'hash':
        row['sha256'] = '0' * 64
    if change == 'writable':
        row['read_only'] = False
    if change == 'escape':
        row['target'] = '/workspace/../data/private.cif'
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'private_input_bindings': [row, row] if change == 'duplicate' else [row]}))
    with pytest.raises(ValueError, match='QA input'):
        launcher.input_bindings(plan)
    assert fixture.read_bytes() == b'original fixture'
