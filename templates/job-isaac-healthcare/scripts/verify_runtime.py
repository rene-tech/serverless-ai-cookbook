"""CPU-only source/import gate; does not claim GPU execution."""

import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path

from i4h_engine.loader import resolve_workflow
from pxr import UsdUtils

import isaac_healthcare_runtime
from isaac_healthcare_runtime.contract import SOURCE, parameters

root = Path("/opt/i4h")
observed = subprocess.check_output(
    ["git", "-c", "safe.directory=/opt/i4h", "-C", str(root), "rev-parse", "HEAD"],
    text=True,
).strip()
assert observed == SOURCE, "i4h source revision mismatch"
assert importlib.metadata.version("isaacsim") == "6.0.1.0", "Isaac Sim version mismatch"
workflow = resolve_workflow("scissor_pick_and_place", "rule-based")
assert workflow.scene == "soarm_scissors"
assert len(workflow.graph.nodes) >= 10
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
    if path.suffix in {".usd", ".usda", ".usdc"}:
        for references in UsdUtils.ExtractExternalReferences(str(path)):
            for reference in references:
                assert (
                    reference in sources["builtin_materials"]
                    or Path(reference).is_file()
                )
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
            "workflow": workflow.name,
            "portable_module": str(installed),
            "localized_assets": len(assets["files"]),
            "cpu_import_and_graph_validation": "passed",
            "gpu_execution": "not-performed",
        }
    )
)
