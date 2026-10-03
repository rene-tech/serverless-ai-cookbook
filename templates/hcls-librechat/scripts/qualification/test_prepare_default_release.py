"""Exercise the local qualification launcher without containers or remote calls."""

import io
import json
import os
import sys

import httpx
import pytest

import prepare_default_release as launcher


def test_separate_state_and_workspace_mounts_preserve_restart_boundary(tmp_path, monkeypatch):
    source = tmp_path / 'source.env'
    source.write_text('NEBIUS_API_KEY=provider-fixture\nSCIENTIFIC_MODELS_API_KEY=customer-not-allowed\n')
    key = tmp_path / 'qa.json'
    key.write_text(json.dumps({'secret': 'system-qa-fixture'}))
    root = tmp_path / 'evidence'
    monkeypatch.setattr(sys, 'argv', ['prepare', '--root', str(root), '--source-env', str(source),
        '--platform-key', str(key), '--image', 'registry.invalid/client@sha256:' + 'a' * 64,
        '--label', 'candidate', '--port', '13205'])
    monkeypatch.setattr(launcher.urllib.request, 'urlopen', lambda *args, **kwargs: io.BytesIO(b'fixture'))
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
