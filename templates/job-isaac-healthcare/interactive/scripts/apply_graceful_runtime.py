"""Apply the interactive-only Arena shutdown patch with exact source provenance."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

SOURCE = "arena/i4h_arena/runner.py"
BEFORE = "d3b87fac3efd8b8bf9273ed84d3105981727be5275995bfea8c6a46e8ea5d382"
AFTER = "ca11fedeef0d880561f0a622842d6f219ed9d1890c1c6b83dcc7b0fbb4ae53a0"
PATCH = "63550c0c41fbdc24900c63dc2253edd23c8080b4cb507c1553ebab189eca56e6"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(root, package):
    root, package = Path(root), Path(package)
    source = root / SOURCE
    patch = package / "patches/arena-graceful-interrupt.patch"
    manifest = package / "graceful-shutdown-provenance.json"
    if sha(patch) != PATCH:
        raise ValueError("Interactive shutdown patch bytes differ")
    record = {
        "schema": "isaac-interactive-graceful-shutdown/v1",
        "source": str(source),
        "before_sha256": BEFORE,
        "sha256": AFTER,
        "patch": str(patch),
        "patch_sha256": PATCH,
        "scope": "interactive image only; unchanged grace and scientific parameters",
    }
    if manifest.exists():
        if json.loads(manifest.read_bytes()) != record or sha(source) != AFTER:
            raise ValueError("Inherited interactive shutdown provenance differs")
        return record
    if sha(source) != BEFORE:
        raise ValueError("Arena runner is not the reviewed unmodified source")
    for check in (True, False):
        argv = ["git", "-c", f"safe.directory={root}", "-C", str(root), "apply"]
        if check:
            argv.append("--check")
        subprocess.run([*argv, str(patch)], check=True)
    if sha(source) != AFTER:
        raise ValueError("Installed interactive shutdown source differs")
    with manifest.open("x") as stream:
        stream.write(json.dumps(record, sort_keys=True, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/opt/i4h"))
    parser.add_argument("--package", type=Path, default=Path("/opt/interactive"))
    args = parser.parse_args()
    print(json.dumps(apply(args.root, args.package), sort_keys=True))
