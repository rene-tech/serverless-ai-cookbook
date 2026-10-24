"""Optional OAuth preserves the standard client and uses owner-scoped consent."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).parent


def render(tmp_path, **extra):
    output = tmp_path / 'config.json'
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('SCIENTIFIC_', 'NEBIUS_', 'DROPBOX_'))}
    env.update(SCIENTIFIC_DISCOVER_CHAT_MODELS='false',
               SCIENTIFIC_CORE_INSTRUCTIONS_PATH=str(ROOT / 'agent-instructions.md'))
    env.update(extra)
    result = subprocess.run(['node', str(ROOT / 'render-config.mjs'), str(output)],
                            env=env, capture_output=True, text=True)
    return result, json.loads(output.read_text()) if output.exists() else None


def test_dropbox_is_optional_and_preserves_every_standard_server(tmp_path):
    off, standard = render(tmp_path)
    assert off.returncode == 0
    assert 'dropbox' not in standard['mcpServers']
    on, research = render(tmp_path, SCIENTIFIC_DROPBOX_ENABLED='true',
                          DROPBOX_APP_KEY='fixture-client', DROPBOX_APP_SECRET='fixture-secret')
    assert on.returncode == 0
    dropbox = research['mcpServers'].pop('dropbox')
    for spec in research['modelSpecs']['list']:
        assert 'dropbox' in spec['mcpServers']
        spec['mcpServers'].remove('dropbox')
    assert research == standard
    assert dropbox['url'] == 'https://mcp.dropbox.com/mcp'
    assert dropbox['requiresOAuth'] and not dropbox['startup']
    assert 'fixture-secret' not in json.dumps(dropbox)
    assert 'token_access_type=offline' in dropbox['oauth']['authorization_url']
    assert 'files.content.write' not in dropbox['oauth']['scope']
    assert dropbox['oauth']['code_challenge_methods_supported'] == ['S256']


def test_partial_dropbox_credentials_fail_clearly(tmp_path):
    result, _ = render(tmp_path, SCIENTIFIC_DROPBOX_ENABLED='true', DROPBOX_APP_KEY='fixture')
    assert result.returncode != 0
    assert 'Dropbox requires DROPBOX_APP_SECRET' in result.stderr
