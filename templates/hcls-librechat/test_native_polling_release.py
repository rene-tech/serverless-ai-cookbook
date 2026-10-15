"""Offline default-pointer/evidence consistency; no registry or live calls."""
import html
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).parent
MANIFEST = 'sha256:bd339b8357a381e3c453d5a5132fdc89fb514ff4b9e4cd67dc3ac2c4f1f5ca4d'
CONFIG = 'sha256:abf7424b90518ebe038c4c8553bd94f9fcc00f84826d478c8063f925b694abc2'


def evidence():
    return json.loads((ROOT/'docs/evidence/native-polling-release-20261015.json').read_text())


def test_pointer_and_console_link_select_exact_published_bytes():
    receipt = evidence()
    values = dict(re.findall(r"^(SCIENTIFIC_AI_[A-Z_]+)='([^']+)'$",
                             (ROOT/'scripts/release-image.sh').read_text(), re.M))
    assert values == {'SCIENTIFIC_AI_RELEASE_IMAGE':receipt['image'],
                      'SCIENTIFIC_AI_RELEASE_DIGEST':MANIFEST,
                      'SCIENTIFIC_AI_SKILLS_VERSION':'2026.10.15.1'}
    assert receipt['manifest'] == MANIFEST and receipt['config'] == CONFIG
    readme = (ROOT/'README.md').read_text()
    link = html.unescape(re.search(r'<a href="(https://console.nebius.com/serverless/endpoint/create\?[^"]+)"',readme)[1])
    selected = parse_qs(urlsplit(link).query)['image']
    assert selected == [receipt['image'].rsplit(':',1)[0]+'@'+MANIFEST]
    assert len(values['SCIENTIFIC_AI_RELEASE_IMAGE']) < 128


def test_receipt_preserves_real_scope_and_unknown_provider_usage():
    receipt = evidence()
    assert receipt['source'] == '65b88e24ca1ed20d73b6a6c7eef0ef8366e6d21e'
    assert receipt['independent_installed']['configured_uid'] == 0
    assert receipt['independent_installed']['sdk_tests_passed'] == 20
    assert receipt['independent_installed']['sdk_tests_skipped'] == 0
    assert receipt['browser']['new_scientific_operations'] == 0
    assert receipt['browser']['installed_qa_image_unchanged'] is True
    assert receipt['browser']['original_agent_restored'] is True
    assert receipt['browser']['autonomous_skill_loading_qualified'] is False
    assert receipt['browser']['provider_requests_actual'] is None
    assert receipt['browser']['provider_cost_actual_usd'] is None
    assert receipt['customer_ready'] is receipt['all_workflows_qualified'] is False
    assert receipt['isolated_state_restore']['upload_fixtures'] == 0
    assert receipt['isolated_state_restore']['local_containers_stopped'] is True
    assert receipt['rollback_manifest'] != MANIFEST


def test_default_chat_model_and_explicit_runtime_override_are_unchanged():
    deploy = (ROOT/'scripts/deploy.sh').read_text()
    assert 'IMAGE="${IMAGE:-$SCIENTIFIC_AI_RELEASE_IMAGE}"' in deploy
    assert 'SCIENTIFIC_CHAT_MODEL:-moonshotai/Kimi-K3' in deploy
    assert 'SCIENTIFIC_CHAT_MAX_OUTPUT_TOKENS:-16384' in deploy
