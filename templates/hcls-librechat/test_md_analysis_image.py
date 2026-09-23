"""The MD analysis layer must not replace the existing hosted API environment."""
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def test_exact_additive_base_and_separate_environment():
    dockerfile = (ROOT / "Dockerfile.md-analysis").read_text()
    assert "@sha256:aac7719ca7efd9fcb8e8e5b3e367271b80ff76c61d65fe3a1ede44faf6774eb1" in dockerfile
    assert "python3 -m venv /opt/md-analysis" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "--no-build-isolation" in dockerfile
    assert "/opt/scientific-client" not in dockerfile
    assert "ENV PATH" not in dockerfile
    assert "apt-get" not in dockerfile
    assert "COPY skills/scientific-ai/ /app/skill/" not in dockerfile
    assert "node /tmp/test-skills-installed.cjs" in dockerfile


def test_reference_and_requirements_agree_with_import_inventory():
    spec = importlib.util.spec_from_file_location("md_inventory", ROOT / "scripts/md-analysis-inventory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    requirements = (ROOT / "md-analysis-requirements.in").read_text()
    reference = (REPO / "skills/scientific-ai/scientific-batch/references/native-md.md").read_text()
    for distribution, (_, version) in module.EXPECTED.items():
        assert f"{distribution}=={version}" in requirements
        assert f"{distribution} {version}".casefold() in reference.casefold()
    assert "/opt/md-analysis/bin/python" in reference
    assert "not a scientific-validation" in reference
