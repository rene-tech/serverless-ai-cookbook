"""CPU-only source/import gate; does not claim GPU execution."""

import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path

from i4h_engine.loader import available_workflows, load_workflow_module
from i4h_engine.registry import default_registry

import isaac_healthcare_runtime
from isaac_healthcare_runtime.contract import SOURCE, parameters

root = Path("/opt/i4h")
observed = subprocess.check_output(
    ["git", "-c", "safe.directory=/opt/i4h", "-C", str(root), "rev-parse", "HEAD"],
    text=True,
).strip()
assert observed == SOURCE, "i4h source revision mismatch"
assert importlib.metadata.version("isaacsim") == "6.0.1.0", "Isaac Sim version mismatch"
catalog = [{"name": name, "scene": load_workflow_module(name).scene,
            "modes": list(load_workflow_module(name).modes)} for name in available_workflows()]
assert catalog, "Installed SDK contains no workflow modules"
assert not default_registry().errors, "Installed registry contains invalid manifests"
assert parameters({})["episode_steps"] is None
patches = json.loads(Path("/opt/isaac-healthcare/upstream-patches.json").read_bytes())
for patch in patches["patches"]:
    patch_file = Path("/opt/isaac-healthcare/patches") / patch["patch"]
    assert hashlib.sha256(patch_file.read_bytes()).hexdigest() == patch["patch_sha256"]
    for changed in patch["files"]:
        assert hashlib.sha256((root / changed["path"]).read_bytes()).hexdigest() == changed["sha256"]
asset_root = Path("/opt/i4h-assets/v0.9.0-7cf86a1")
assets = json.loads((asset_root / "manifest.json").read_bytes())
assert assets["asset_generation"] == "v0.9.0/7cf86a1"
sources = json.loads(Path("/opt/isaac-healthcare/asset-sources.json").read_bytes())
assert len(assets["files"]) == len(sources["files"])
for record in assets["files"]:
    path = asset_root / record["path"]
    assert path.stat().st_size == record["size_bytes"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
composed = json.loads((asset_root / "composed-assets.json").read_bytes())
assert composed["schema"] == "isaac-healthcare-composed-assets/v1"
assert composed["status"] == "passed" and not composed["errors"]
assert composed["source_manifest_sha256"] == hashlib.sha256(
    Path("/opt/isaac-healthcare/asset-sources.json").read_bytes()
).hexdigest()
assert composed["localized_manifest_sha256"] == hashlib.sha256(
    (asset_root / "manifest.json").read_bytes()
).hexdigest()
assert composed["verifier_sha256"] == hashlib.sha256(
    Path("/opt/isaac-healthcare/scripts/verify_composed_assets.py").read_bytes()
).hexdigest()
for material in composed["installed_builtin_materials"].values():
    assert hashlib.sha256(Path(material["path"]).read_bytes()).hexdigest() == material["sha256"]
mdl = json.loads((asset_root / "mdl-dependencies.json").read_bytes())
assert mdl["schema"] == "isaac-mdl-offline-layout/v1"
assert mdl["source_manifest_canonical_sha256"] == hashlib.sha256(
    json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
assert mdl["verifier_sha256"] == hashlib.sha256(
    Path("/opt/isaac-healthcare/scripts/fetch_assets.py").read_bytes()
).hexdigest()
assert mdl["parser_sha256"] == hashlib.sha256(
    Path("/opt/isaac-healthcare/scripts/mdl_dependencies.py").read_bytes()
).hexdigest()
assert {row["path"] for row in mdl["modules"]} == {
    row["path"] for row in sources["files"] if Path(row["path"]).suffix.lower() == ".mdl"
}
for module in mdl["modules"]:
    assert hashlib.sha256((asset_root / module["path"]).read_bytes()).hexdigest() == module["source_sha256"]
    for dependency in module["required"]:
        assert dependency["files"] and all(Path(path).is_file() for path in dependency["files"]), \
            "A required MDL resource disappeared after build"
    for builtin in module["builtin_modules"]:
        identity = builtin["provenance"]
        assert hashlib.sha256(Path(identity["path"]).read_bytes()).hexdigest() == identity["sha256"]
kit = root / "third_party/IsaacLab-ffff603/apps/isaaclab.python.kit"
localization = json.loads((asset_root / "kit-localization.json").read_bytes())
assert hashlib.sha256(kit.read_bytes()).hexdigest() == localization["sha256"]
assert (
    Path(localization["local_asset_root"])
    / "Isaac/Environments/Grid/default_environment.usd"
).is_file()
installed = Path(isaac_healthcare_runtime.__file__).parent
for source in Path("/opt/isaac-healthcare/src/isaac_healthcare_runtime").iterdir():
    if source.suffix in {".py", ".json"}:
        assert source.read_bytes() == (installed / source.name).read_bytes()
print(
    json.dumps(
        {
            "source_revision": observed,
            "isaac_sim": "6.0.1",
            "workflows": catalog,
            "portable_module": str(installed),
            "localized_assets": len(assets["files"]),
            "composed_asset_proof": composed["summary"],
            "pinned_material_modules": len(mdl["modules"]),
            "cpu_import_and_graph_validation": "passed",
            "gpu_execution": "not-performed",
        }
    )
)
