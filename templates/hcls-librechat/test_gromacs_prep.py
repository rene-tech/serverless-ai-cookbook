"""Installer regression tests; real native-command acceptance lives in verify.py."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gromacs_prep_install", ROOT / "scripts/gromacs-prep/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def paths(tmp_path):
    source = tmp_path / "prefix"
    (source / "bin").mkdir(parents=True)
    (source / "SOURCE-SHA256").write_text(installer.SOURCE_SHA256 + "\n")
    command = source / "bin/gmx"
    # Only installer mechanics are mocked. verify.py executes real compiled tools.
    command.write_text("#!/bin/sh\nprintf 'GROMACS version: 2026.4\\nGPU support: disabled\\n'\n")
    command.chmod(0o755)
    root = tmp_path / "client"
    (root / "usr/local/bin").mkdir(parents=True)
    return source, root, root / "usr/local/bin/gmx"


@pytest.mark.parametrize("previous", ["absent", "file", "symlink"])
def test_install_is_idempotent_and_rollback_preserves_previous_command(paths, previous):
    source, root, command = paths
    if previous == "file":
        command.write_text("previous executable\n")
        command.chmod(0o751)
    elif previous == "symlink":
        command.symlink_to("/previous/gmx")
    result = installer.install(source, root)
    assert result["changed"] is True
    assert command.is_symlink()
    assert command.resolve() == root / "opt/gromacs-prep/2026.4/bin/gmx"
    assert installer.install(source, root)["changed"] is False
    receipt = Path(result["receipt"])
    assert json.loads(receipt.read_text())["previous"]["kind"] == previous
    assert installer.rollback(receipt)["prefix_retained"] is True
    assert (root / "opt/gromacs-prep/2026.4/bin/gmx").is_file()
    if previous == "file":
        assert command.read_text() == "previous executable\n"
        assert command.stat().st_mode & 0o777 == 0o751
    elif previous == "symlink":
        assert os.readlink(command) == "/previous/gmx"
    else:
        assert not command.exists()


def test_install_rejects_changed_immutable_prefix(paths):
    source, root, _ = paths
    installer.install(source, root)
    (source / "extra").write_text("unexpected modification")
    with pytest.raises(ValueError, match="immutable version differs"):
        installer.install(source, root)


def test_rollback_does_not_clobber_a_later_change(paths):
    source, root, command = paths
    result = installer.install(source, root)
    command.unlink()
    command.write_text("new operator command")
    with pytest.raises(ValueError, match="Command changed"):
        installer.rollback(Path(result["receipt"]))
    assert command.read_text() == "new operator command"


def test_prefix_cannot_reference_external_files(paths):
    source, root, _ = paths
    (source / "outside").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="escapes installation"):
        installer.install(source, root)


def test_skill_distinguishes_duration_and_structural_repairs():
    skill = (ROOT.parents[1] / "skills/scientific-ai/gromacs/SKILL.md").read_text()
    for command in ("gmx dump", "check", "convert-tpr", "editconf", "grompp"):
        assert command in skill
    assert "does **not** require `.gro/.top/.mdp`" in skill
    assert "not automatically validated originals" in skill.replace("\n", " ")
    assert "do not ask for the same consent twice" in skill.replace("\n", " ")
    assert "original input SHA-256" in skill
    assert "never suppress warnings with `-maxwarn`" in skill
    assert "not proof of an inevitable" in skill


def test_final_image_installs_and_executes_native_report_helper(tmp_path):
    dockerfile = (ROOT / "Dockerfile.gromacs-prep").read_text()
    includes = (ROOT / "Dockerfile.gromacs-prep.dockerignore").read_text().splitlines()
    files = {
        "scientific_verified_results.py": "scientific_verified_results.py",
        "native_md_report.py": "native_md_report.py",
        "report-native-md.py": "native_md_report.py",
    }
    for target, source in files.items():
        assert f"COPY templates/hcls-librechat/{source} /opt/bionemo/{target}" in dockerfile
        assert f"!templates/hcls-librechat/{source}" in includes
        shutil.copyfile(ROOT / source, tmp_path / target)
    for name in ("report-native-md.py", "native_md_report.py"):
        assert f"/opt/scientific-client/bin/python /opt/bionemo/{name} --help" in dockerfile
        completed = subprocess.run([sys.executable, str(tmp_path / name), "--help"],
                                   cwd=tmp_path, text=True, capture_output=True, timeout=10)
        assert completed.returncode == 0, completed.stderr
        assert "--receipt-dir" in completed.stdout
        assert "--expected-repeats" in completed.stdout
