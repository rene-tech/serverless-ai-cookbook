"""Missing installed defaults must fail before GPU execution."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "default_marker_assets", Path(__file__).parents[1] / "scripts/default_marker_assets.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path, value):
    path.write_text(json.dumps(value))


def prepared(tmp_path, filename="ordinary-marker.usd"):
    markers = tmp_path / "markers"
    markers.mkdir()
    (markers / "defaults.py").write_text(
        'from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR\n'
        'DEFAULT = VisualizationMarkersCfg(markers={"marker": UsdFileCfg('
        f'usd_path=f"{{ISAAC_NUCLEUS_DIR}}/Props/{filename}")}})\n'
    )
    asset_root = tmp_path / "assets"
    local_root = asset_root / "external/Isaac/current"
    remote = "https://assets.example/Isaac/current"
    original = "[settings]\n" + "".join(
        f'persistent.isaac.asset_root.{name} = "{remote}"\n'
        for name in ("default", "cloud", "nvidia")
    )
    kit = tmp_path / "example.kit"
    kit.write_text(original.replace(remote, str(local_root)))
    receipt = tmp_path / "localization.json"
    write(receipt, {"source_asset_root": remote, "local_asset_root": str(local_root),
                    "sha256": MODULE.sha(kit),
                    "source_sha256": hashlib.sha256(original.encode()).hexdigest()})
    observed = MODULE.inspect(markers, kit, receipt)
    path = local_root / "Isaac/Props" / filename
    path.parent.mkdir(parents=True)
    path.write_text('#usda 1.0\ndef Xform "ordinary" {}\n')
    url = observed["seed_urls"][0]
    row = {"path": path.relative_to(asset_root).as_posix(), "url": url,
           "sha256": MODULE.sha(path), "size_bytes": path.stat().st_size}
    source = tmp_path / "source.json"
    fields = ("schema", "source_asset_root", "marker_source_files", "references", "seed_urls")
    write(source, {"files": [row], "seed_urls": [url],
                   "default_marker_assets": {key: observed[key] for key in fields}})
    write(asset_root / "manifest.json", {"files": [{**row, "source_url": url, "source_sha256": row["sha256"]}]})
    composed = tmp_path / "composed.json"
    write(composed, {"status": "passed", "errors": [],
                     "source_manifest_sha256": MODULE.sha(source),
                     "localized_manifest_sha256": MODULE.sha(asset_root / "manifest.json"),
                     "roots": [{"source_url": url, "kind": "composed_usd_root", "composition_errors": []}]})
    return (markers, kit, receipt, source, asset_root, composed), path


def test_unseen_source_filename_is_derived_without_marker_name_allowlist(tmp_path):
    args, path = prepared(tmp_path, "renamed-calibration-frame.usd")
    result = MODULE.verify_installed(*args)
    assert result["status"] == "passed"
    assert result["roots"][0]["path"].endswith(path.name)


def test_missing_file_cannot_reuse_a_previously_valid_composition_receipt(tmp_path):
    args, path = prepared(tmp_path)
    assert MODULE.verify_installed(*args)["status"] == "passed"
    path.unlink()
    with pytest.raises(ValueError, match="file is absent"):
        MODULE.verify_installed(*args)


def test_unrecorded_default_source_dependency_fails_closed(tmp_path):
    args, _ = prepared(tmp_path)
    source = args[0] / "defaults.py"
    source.write_text(source.read_text().replace("ordinary-marker.usd", "another-marker.usd"))
    with pytest.raises(ValueError, match="source declarations differ"):
        MODULE.verify_installed(*args)
