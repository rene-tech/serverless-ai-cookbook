"""Future build and installed-byte gate regressions; no live deployment."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('observer_image_gate', ROOT / 'scripts/verify-observer-recovery.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


@pytest.mark.parametrize('recipe', ['Dockerfile', 'Dockerfile.default-release', 'Dockerfile.observer-recovery'])
def test_maintained_recipes_verify_the_installed_worker(recipe):
    text = (ROOT / recipe).read_text()
    assert '/opt/scientific-client/bin/python /tmp/client/scripts/verify-observer-recovery.py --source /tmp/client' in text
    assert 'scientific-study-worker.py' in text and 'scientific-workflow.py' in text
    if recipe != 'Dockerfile':
        context = (ROOT / (recipe + '.dockerignore')).read_text()
        for source in [*gate.FILES, 'scripts/verify-observer-recovery.py']:
            assert '!templates/hcls-librechat/' + source in context


@pytest.mark.parametrize('stale', list(gate.FILES.values()))
def test_gate_refuses_one_stale_or_missing_runtime_file_before_import(tmp_path, stale):
    source, installed = tmp_path / 'source', tmp_path / 'installed'
    installed.mkdir()
    for original, target in gate.FILES.items():
        path = source / original
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('current source')
        (installed / target).write_text('stale' if target == stale else 'current source')
    with pytest.raises(RuntimeError, match='Installed observer source differs: ' + stale):
        gate.verify(source, installed)
    (installed / stale).unlink()
    with pytest.raises(FileNotFoundError):
        gate.verify(source, installed)
