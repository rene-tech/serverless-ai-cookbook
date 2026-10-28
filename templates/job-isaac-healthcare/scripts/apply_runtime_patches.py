"""Apply and verify reviewed upstream runtime fixes on fresh or inherited images."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PATCHES = (
    {
        "id": "soarm-camera-disable-v1",
        "patch": "soarm-camera-disable.patch",
        "reason": "Honor explicit camera disable in the SOARM scene and its observation terms",
        "files": ("arena/i4h_arena/scenes/soarm_scissors.py", "arena/i4h_arena/embodiments/so_arm.py"),
    },
    {
        "id": "arena-camera-control-v1",
        "patch": "arena-camera-control.patch",
        "reason": "Normalize explicit camera control before scene construction and AppLauncher selection",
        "files": ("arena/i4h_arena/cli.py",),
    },
    {
        "id": "arena-launch-outcome-v1",
        "patch": "arena-launch-outcome.patch",
        "reason": "Preserve failed initialization status before simulator shutdown hooks run",
        "files": ("arena/i4h_arena/app.py",),
    },
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(root, package):
    """Verify inherited patch bytes before adding a new independent patch."""
    manifest = package / "upstream-patches.json"
    previous = json.loads(manifest.read_bytes()) if manifest.exists() else {
        "schema": "isaac-healthcare-upstream-patches/v1", "patches": []
    }
    if previous.get("schema") != "isaac-healthcare-upstream-patches/v1":
        raise ValueError("Unknown upstream patch manifest schema")
    existing = {row["id"]: row for row in previous["patches"]}
    if len(existing) != len(previous["patches"]) or set(existing) - {p["id"] for p in PATCHES}:
        raise ValueError("Unexpected inherited runtime patches")
    # Preflight every patch before mutating source; a changed recorded source
    # must never be mistaken for an already-applied trusted patch.
    for patch in PATCHES:
        path = package / "patches" / patch["patch"]
        if recorded := existing.get(patch["id"]):
            if recorded["patch"] != patch["patch"] or recorded["patch_sha256"] != sha(path):
                raise ValueError("Inherited patch bytes differ: " + patch["id"])
            if [r["path"] for r in recorded["files"]] != list(patch["files"]):
                raise ValueError("Inherited patch source paths differ: " + patch["id"])
            if any(sha(root / row["path"]) != row["sha256"] for row in recorded["files"]):
                raise ValueError("Inherited patched source differs: " + patch["id"])
        else:
            subprocess.run(["git", "-C", str(root), "apply", "--check", str(path)], check=True)
    records = []
    for patch in PATCHES:
        if patch["id"] in existing:
            records.append(existing[patch["id"]])
            continue
        path = package / "patches" / patch["patch"]
        before = {name: sha(root / name) for name in patch["files"]}
        subprocess.run(["git", "-C", str(root), "apply", str(path)], check=True)
        records.append({
            **patch, "patch_sha256": sha(path),
            "files": [{"path": name, "source_sha256": before[name], "sha256": sha(root / name)}
                      for name in patch["files"]],
        })
    manifest.write_text(json.dumps({"schema": previous["schema"], "patches": records}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/opt/i4h"))
    parser.add_argument("--package", type=Path, default=Path("/opt/isaac-healthcare"))
    args = parser.parse_args()
    apply(args.root, args.package)
