"""Composed closure follows USD values, including variants, samples and packages."""

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest
from pxr import Sdf, Usd, UsdUtils


module = Path(__file__).parents[1] / "scripts/verify_composed_assets.py"
spec = importlib.util.spec_from_file_location("verify_composed_assets", module)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def prepare(tmp_path, files, missing=(), *, seed="root.usda", builtins=None):
    directory = tmp_path / "assets"
    directory.mkdir()
    source_root = "https://source.example.test/release/"
    source_rows = []
    for name, value in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode() if isinstance(value, str) else value)
        source_rows.append({"path": name, "url": source_root + name,
                            "sha256": verifier.sha(path), "size_bytes": path.stat().st_size})
    for name in files:
        if Path(name).suffix in {".usd", ".usda", ".usdc"}:
            path = directory / name
            layer = Sdf.Layer.FindOrOpen(str(path))
            UsdUtils.ModifyAssetPaths(layer, lambda reference, path=path:
                reference if reference in (builtins or {}) else str((path.parent / reference).resolve()))
            layer.Save()
    localized = []
    for source_row in source_rows:
        path = directory / source_row["path"]
        localized.append({"path": source_row["path"], "source_url": source_row["url"],
                          "source_sha256": source_row["sha256"], "sha256": verifier.sha(path),
                          "size_bytes": path.stat().st_size})
    source = {"source_root": source_root, "seed_urls": [source_root + seed], "files": source_rows,
              "builtin_materials": list(builtins or {}), "builtin_material_provenance": builtins or {},
              "missing_assets": {source_root + name: {"reason": "http_404"} for name in missing}}
    manifest = tmp_path / "source.json"
    manifest.write_text(json.dumps(source))
    (directory / "manifest.json").write_text(json.dumps({"files": localized}))
    return manifest, directory


WEAK = '''#usda 1.0
(defaultPrim = "Model")
def Xform "Model" {
    def Shader "Surface" {
        asset inputs:file = @missing-original.<UDIM>.png@
    }
}
'''
STRONG = '''#usda 1.0
def Xform "World" (references = @weak.usda@</Model>) {
    over "Surface" {
        asset inputs:file = @renamed-valid-texture.bin@
    }
}
'''


def test_strong_opinion_resolves_weak_missing_texture_without_rewriting_usd(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": STRONG, "weak.usda": WEAK,
        "renamed-valid-texture.bin": b"texture-bytes"}, ["missing-original.<UDIM>.png"])
    before = {path.name: verifier.sha(path) for path in directory.glob("*.usda")}
    report = verifier.verify(manifest, directory)
    assert report["status"] == "passed", report["errors"]
    assert len(report["missing_authored_assets"]) == 1
    missing = next(iter(report["missing_authored_assets"].values()))
    assert missing["classification"] == "overridden_in_all_composed_roots_and_variants"
    assert len(missing["observations"][0]["stack"]) == 2
    assert before == {path.name: verifier.sha(path) for path in directory.glob("*.usda")}


def test_selected_missing_texture_fails_even_when_declared_by_download_audit(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": WEAK}, ["missing-original.<UDIM>.png"])
    report = verifier.verify(manifest, directory)
    assert report["status"] == "failed"
    assert any(row["kind"] == "unresolved_composed_asset" for row in report["errors"])


def test_authored_variant_with_missing_texture_is_checked_even_if_not_default(tmp_path):
    scene = '''#usda 1.0
def Xform "World" (
    variants = { string look = "good" }
    prepend variantSets = "look"
) {
    variantSet "look" = {
        "good" {
            def Shader "Surface" {
                asset inputs:file = @valid.bin@
            }
        }
        "broken" {
            def Shader "Surface" {
                asset inputs:file = @missing.bin@
            }
        }
    }
}
'''
    manifest, directory = prepare(tmp_path, {"root.usda": scene, "valid.bin": b"texture"}, ["missing.bin"])
    report = verifier.verify(manifest, directory)
    assert report["status"] == "failed"
    assert report["summary"]["composed_configurations"] == 2
    assert any(row.get("variants", [{}])[0].get("selected") == "broken"
               for row in report["errors"] if row["kind"] == "unresolved_composed_asset")


def test_asset_time_sample_is_not_hidden_by_valid_default(tmp_path):
    scene = '''#usda 1.0
def Shader "Surface" {
    asset inputs:file = @valid.bin@
    asset inputs:file.timeSamples = { 0: @valid.bin@, 5: @missing.bin@ }
}
'''
    manifest, directory = prepare(tmp_path, {"root.usda": scene, "valid.bin": b"texture"}, ["missing.bin"])
    report = verifier.verify(manifest, directory)
    assert any(row["kind"] == "unresolved_composed_asset" and row["time"] == 5
               for row in report["errors"])


def test_instance_proxy_assets_are_checked(tmp_path):
    scene = '''#usda 1.0
def Xform "Instance" (instanceable = true; references = @weak.usda@</Model>) {}
'''.replace("true; references", "true\n    references")
    manifest, directory = prepare(tmp_path, {"root.usda": scene, "weak.usda": WEAK}, ["missing-original.<UDIM>.png"])
    report = verifier.verify(manifest, directory)
    assert any(row["kind"] == "unresolved_composed_asset" and row["attribute"].startswith("/Instance/")
               for row in report["errors"])


def test_missing_composition_reference_cannot_be_waived_as_weak_texture(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": '''#usda 1.0
def Xform "World" (references = @missing.usda@) {}
'''}, ["missing.usda"])
    report = verifier.verify(manifest, directory)
    assert report["status"] == "failed"
    assert any(row["kind"] == "composition_error" for row in report["errors"])


def test_pinned_non_usd_payload_is_a_format_limitation_not_missing_bytes(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": '''#usda 1.0
def Xform "World" (payload = @surface.obj@) {}
''', "surface.obj": "v 0 0 0\n"})
    report = verifier.verify(manifest, directory)
    assert report["status"] == "passed", report["errors"]
    assert report["format_limitations"][0]["kind"] == "pinned_payload_without_usd_format_plugin"
    assert report["renderer_execution"] == "not-performed"


def test_missing_non_usd_payload_still_fails(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": '''#usda 1.0
def Xform "World" (payload = @surface.obj@) {}
'''}, ["surface.obj"])
    report = verifier.verify(manifest, directory)
    assert report["status"] == "failed"
    assert not report["format_limitations"]


def test_builtin_material_requires_actual_pinned_installed_bytes(tmp_path):
    material = tmp_path / "Example.mdl"
    material.write_text("mdl 1.7;\n")
    manifest, directory = prepare(tmp_path, {"root.usda": '''#usda 1.0
def Shader "Surface" {
    asset info:mdl:sourceAsset = @Example.mdl@
}
'''}, builtins={"Example.mdl": {"path": str(material), "sha256": verifier.sha(material)}})
    assert verifier.verify(manifest, directory)["status"] == "passed"
    material.write_text("changed\n")
    with pytest.raises(ValueError, match="builtin material bytes differ"):
        verifier.verify(manifest, directory)


def test_unmatched_missing_declaration_is_uncertain_and_fails(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": '#usda 1.0\ndef Xform "World" {}\n'}, ["unobserved.bin"])
    report = verifier.verify(manifest, directory)
    assert report["status"] == "failed"
    assert any(row["kind"] == "missing_asset_without_complete_override_proof" for row in report["errors"])


def test_changed_localized_file_is_rejected_before_composition(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": '#usda 1.0\ndef Xform "World" {}\n'})
    (directory / "root.usda").write_text('#usda 1.0\ndef Xform "Different" {}\n')
    with pytest.raises(ValueError, match="Localized asset bytes changed"):
        verifier.verify(manifest, directory)


def test_package_member_resolves_within_exact_pinned_usdz(tmp_path):
    package = tmp_path / "bundle.usdz"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("scene.usda", '''#usda 1.0
(defaultPrim = "Model")
def Xform "Model" {
    def Shader "Surface" {
        asset inputs:file = @0/texture.bin@
    }
}
''')
        archive.writestr("0/texture.bin", b"pinned-inside-package")
    manifest, directory = prepare(tmp_path, {"root.usda": '''#usda 1.0
def Xform "World" (references = @bundle.usdz@) {}
''', "bundle.usdz": package.read_bytes()})
    report = verifier.verify(manifest, directory)
    assert report["status"] == "passed", report["errors"]
    member = next(row for row in report["package_members"].values() if row["member"] == "0/texture.bin")
    assert member["sha256"] == hashlib.sha256(b"pinned-inside-package").hexdigest()


def test_missing_package_archive_is_allowed_only_when_member_use_is_overridden(tmp_path):
    weak = WEAK.replace("missing-original.<UDIM>.png", "missing.usdz[0/texture.png]")
    manifest, directory = prepare(tmp_path, {"root.usda": STRONG, "weak.usda": weak,
        "renamed-valid-texture.bin": b"texture-bytes"}, ["missing.usdz"])
    source = json.loads(manifest.read_text())
    root = source["source_root"]
    source["package_members"] = {root + "missing.usdz[0/texture.png]": {
        "archive_url": root + "missing.usdz", "member": "0/texture.png"}}
    manifest.write_text(json.dumps(source))
    report = verifier.verify(manifest, directory)
    assert report["status"] == "passed", report["errors"]
    proof = next(iter(report["missing_authored_assets"].values()))
    assert proof["classification"] == "overridden_in_all_composed_roots_and_variants"
    assert proof["uses"][0]["authored"].endswith("missing.usdz[0/texture.png]")


def test_selected_array_member_missing_archive_is_rejected(tmp_path):
    scene = '''#usda 1.0
def Shader "Surface" {
    asset[] inputs:files = [@valid.bin@, @missing.usdz[0/texture.png]@]
}
'''
    manifest, directory = prepare(tmp_path, {"root.usda": scene, "valid.bin": b"texture"}, ["missing.usdz"])
    report = verifier.verify(manifest, directory)
    assert report["status"] == "failed"
    assert any(row["kind"] == "unresolved_composed_asset" and row.get("requested_member") == "0/texture.png"
               for row in report["errors"])


def test_non_usd_seed_assets_receive_full_integrity_proof_without_composition(tmp_path):
    manifest, directory = prepare(tmp_path, {"root.usda": '#usda 1.0\ndef Xform "World" {}\n',
                                            "asset.png": b"image-bytes", "NOTICE.txt": b"asset-license"})
    source = json.loads(manifest.read_text())
    source["seed_urls"].extend(source["source_root"] + name for name in ("asset.png", "NOTICE.txt"))
    manifest.write_text(json.dumps(source))
    report = verifier.verify(manifest, directory)
    assert report["status"] == "passed", report["errors"]
    assert report["summary"]["seed_roots"] == 3
    assert report["summary"]["composed_configurations"] == 1
    assert report["summary"]["pinned_non_layer_seeds"] == 2


def test_authored_inactive_ancestor_proves_missing_descendant_is_not_selected(tmp_path):
    inactive = WEAK.replace('def Xform "Model" {', 'def Xform "Model" (active = false) {')
    manifest, directory = prepare(tmp_path, {"root.usda": inactive}, ["missing-original.<UDIM>.png"])
    report = verifier.verify(manifest, directory)
    assert report["status"] == "passed", report["errors"]
    proof = next(iter(report["missing_authored_assets"].values()))
    assert proof["classification"] == "inactive_or_overridden_in_all_composed_roots_and_variants"
    assert proof["inactive_observations"][0]["prim_stack"][0]["active"] is False


def test_stronger_activation_in_another_seed_prevents_inactive_asset_waiver(tmp_path):
    inactive = WEAK.replace('def Xform "Model" {', 'def Xform "Model" (active = false) {')
    active = '''#usda 1.0
def Xform "World" (
    active = true
    references = @root.usda@</Model>
) {}
'''
    manifest, directory = prepare(tmp_path, {"root.usda": inactive, "reactivated.usda": active},
                                  ["missing-original.<UDIM>.png"])
    source = json.loads(manifest.read_text())
    source["seed_urls"].append(source["source_root"] + "reactivated.usda")
    manifest.write_text(json.dumps(source))
    report = verifier.verify(manifest, directory)
    assert report["status"] == "failed"
    assert any(row["kind"] == "unresolved_composed_asset" and row["root"].endswith("reactivated.usda")
               for row in report["errors"])


def test_variant_on_inactive_ancestor_can_reactivate_missing_asset(tmp_path):
    authored = tmp_path / "authored.usda"
    stage = Usd.Stage.CreateNew(str(authored))
    model = stage.DefinePrim("/Model", "Xform")
    shader = stage.DefinePrim("/Model/Shader", "Shader")
    shader.CreateAttribute("inputs:file", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath("missing.bin"))
    variants = model.GetVariantSets().AddVariantSet("enabled")
    for name, active in [("off", False), ("on", True)]:
        variants.AddVariant(name)
        variants.SetVariantSelection(name)
        with variants.GetVariantEditContext():
            model.SetActive(active)
    variants.SetVariantSelection("off")
    stage.GetRootLayer().Save()
    manifest, directory = prepare(tmp_path, {"root.usda": authored.read_text()}, ["missing.bin"])
    report = verifier.verify(manifest, directory)
    assert report["summary"]["composed_configurations"] == 2
    assert report["status"] == "failed"
    assert any(row["kind"] == "unresolved_composed_asset" for row in report["errors"])
