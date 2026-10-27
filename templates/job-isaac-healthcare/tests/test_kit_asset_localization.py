"""Overlay builds preserve exact prior Kit source/localization provenance."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "localize_kit_assets", Path(__file__).parents[1] / "scripts/localize_kit_assets.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fresh_and_inherited_localization_preserve_exact_original(tmp_path):
    root, assets = tmp_path / "sdk", tmp_path / "assets"
    (root / "apps").mkdir(parents=True)
    assets.mkdir()
    kit = root / "apps/isaaclab.python.kit"
    source = "[settings]\nphysics.example = 12\n" + "".join(
        f'persistent.isaac.asset_root.{kind} = "{MODULE.REMOTE}"\n'
        for kind in ("default", "cloud", "nvidia")
    )
    kit.write_text(source)
    first = MODULE.localize(root, assets)
    localized = kit.read_bytes()
    second = MODULE.localize(root, assets)
    assert first["source_sha256"] == second["source_sha256"]
    assert not first["already_localized"] and second["already_localized"]
    assert kit.read_bytes() == localized
    assert "physics.example = 12" in localized.decode()
    proof = json.loads((assets / "kit-localization.json").read_text())
    proof["source_sha256"] = "a" * 64
    (assets / "kit-localization.json").write_text(json.dumps(proof))
    with pytest.raises(RuntimeError, match="exact source proof"):
        MODULE.localize(root, assets)


def test_partial_settings_do_not_pass_as_localized(tmp_path):
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps/isaaclab.python.kit").write_text(
        f'persistent.isaac.asset_root.default = "{MODULE.REMOTE}"\n'
    )
    with pytest.raises(RuntimeError, match="configuration changed"):
        MODULE.localize(tmp_path, tmp_path)
