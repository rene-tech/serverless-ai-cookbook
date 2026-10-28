"""Offline localization must preserve tiled textures and reject unpinned bytes."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from pxr import UsdUtils

module = Path(__file__).parents[1] / "scripts/fetch_assets.py"
spec = importlib.util.spec_from_file_location("fetch_assets", module)
fetch_assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_assets)


def scene(tmp_path):
    source = tmp_path / "raw"
    source.mkdir()
    (source / "textures").mkdir()
    (source / "scene.usda").write_text('''#usda 1.0
def Shader "Texture" {
    asset inputs:file = @textures/body layer.<UDIM>.png@
}
''')
    for tile in (1001, 1002):
        (source / f"textures/body layer.{tile}.png").write_bytes(f"retained-tile-{tile}".encode())
    root = "https://public.example.test/assets/"
    rows = []
    for path in sorted(source.rglob("*")):
        if path.is_file():
            name = path.relative_to(source).as_posix()
            rows.append({"path": name, "url": root + name.replace(" ", "%20"),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "size_bytes": path.stat().st_size})
    manifest = {"asset_generation": "test", "files": rows, "builtin_materials": [],
                "udim_patterns": {root + "textures/body layer.<UDIM>.png": {
                    "path": "textures/body layer.<UDIM>.png",
                    "tiles": [row["url"] for row in rows if row["path"].endswith(".png")],
                }}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return source, path, manifest


def test_udim_pattern_keeps_all_pinned_tiles_and_encoded_space_paths(tmp_path):
    source, manifest, _ = scene(tmp_path)
    target = tmp_path / "localized"
    fetch_assets.fetch(manifest, target, source)
    references = UsdUtils.ExtractExternalReferences(str(target / "scene.usda"))
    assert str(target / "textures/body layer.<UDIM>.png") in references[1]
    assert len(list((target / "textures").glob("*.png"))) == 2
    assert len(json.loads((target / "manifest.json").read_text())["files"]) == 3


def test_unpinned_texture_dependency_is_rejected(tmp_path):
    source, path, manifest = scene(tmp_path)
    manifest["udim_patterns"] = {}
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="not localized"):
        fetch_assets.fetch(path, tmp_path / "localized", source)


def test_cached_bytes_are_still_sha_verified(tmp_path):
    source, path, _ = scene(tmp_path)
    (source / "textures/body layer.1001.png").write_bytes(b"changed-source")
    with pytest.raises(ValueError, match="immutable manifest"):
        fetch_assets.fetch(path, tmp_path / "localized", source)


def material_scene(tmp_path):
    source = tmp_path / "raw-materials"
    (source / "materials/textures").mkdir(parents=True)
    files = {
        "scene.usda": b'#usda 1.0\ndef Shader "Material" {\n asset info:mdl:sourceAsset = @materials/main.mdl@\n}\n',
        "materials/main.mdl": b'mdl 1.7; import .::helper::*; export material main(texture_2d t = texture_2d("textures/surface.png")) = helper(t);\n',
        "materials/helper.mdl": b'mdl 1.7; export material helper(texture_2d t) = material();\n',
        "materials/textures/surface.png": b"pinned-texture-byte-fixture",
    }
    root = "https://public.example.test/materials/"
    rows, evidence = [], {}
    spec = importlib.util.spec_from_file_location("mdl_dependencies", module.with_name("mdl_dependencies.py"))
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    for name, data in files.items():
        (source / name).write_bytes(data)
        rows.append({"path": name, "url": root + name,
                     "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)})
        if name.endswith(".mdl"):
            evidence[root + name] = parser.extract_dependencies(
                data.decode(), source_url=root + name, builtin_material_provenance={},
            )
    manifest = {"asset_generation": "test", "source_root": root, "files": rows,
                "builtin_materials": [], "mdl_dependencies": evidence}
    path = tmp_path / "material-manifest.json"
    path.write_text(json.dumps(manifest))
    return source, path, manifest


def test_transitive_mdl_resources_preserve_shader_bytes_and_relative_layout(tmp_path):
    source, path, _ = material_scene(tmp_path)
    target = tmp_path / "localized"
    fetch_assets.fetch(path, target, source)
    for shader in ("main.mdl", "helper.mdl"):
        assert (target / "materials" / shader).read_bytes() == (source / "materials" / shader).read_bytes()
    proof = json.loads((target / "mdl-dependencies.json").read_bytes())
    assert len(proof["modules"]) == 2
    assert len(proof["modules"][0]["required"]) == 2


def test_missing_mdl_texture_cannot_hide_behind_successful_usd_composition(tmp_path):
    source, path, manifest = material_scene(tmp_path)
    manifest["files"] = [row for row in manifest["files"] if not row["path"].endswith(".png")]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="absent from its pinned relative layout"):
        fetch_assets.fetch(path, tmp_path / "localized", source)


def test_mdl_declared_dependency_evidence_is_checked_against_actual_source(tmp_path):
    source, path, manifest = material_scene(tmp_path)
    first = next(iter(manifest["mdl_dependencies"].values()))
    first["required"] = []
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="evidence differs"):
        fetch_assets.fetch(path, tmp_path / "localized", source)
