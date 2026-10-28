#!/usr/bin/env python3
"""Build and stage the pinned browser as a new, hash-bound portable artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path, *, offline: bool = False) -> dict:
    root = Path(__file__).resolve().parent
    output = output.absolute()
    if output.exists():
        raise FileExistsError(output)
    sources = [
        root / n
        for n in ("package.json", "package-lock.json", "index.html", "tsconfig.json")
    ]
    sources += sorted(p for p in (root / "src").rglob("*") if p.is_file())
    before = {str(p.relative_to(root)): digest(p) for p in sources}
    subprocess.run(
        ["npm", "ci", *(["--offline"] if offline else [])], cwd=root, check=True
    )
    subprocess.run(["npm", "run", "check"], cwd=root, check=True)
    subprocess.run(["npm", "run", "build"], cwd=root, check=True)
    if before != {str(p.relative_to(root)): digest(p) for p in sources}:
        raise RuntimeError("Browser source changed during the build")
    dist = root / "dist"
    if not (dist / "index.html").is_file() or not (dist / "assets").is_dir():
        raise RuntimeError(
            "The browser build did not produce its expected entrypoint/assets"
        )
    for p in dist.rglob("*"):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            raise ValueError("Viewer artifacts must contain ordinary files/directories")
    files = {
        str(p.relative_to(dist)): {"sha256": digest(p), "size_bytes": p.stat().st_size}
        for p in sorted(dist.rglob("*"))
        if p.is_file()
    }
    manifest = {
        "schema": 1,
        "builder_sha256": digest(Path(__file__).resolve()),
        "source_sha256": before,
        "files": files,
        "commands": [
            "npm ci" + (" --offline" if offline else ""),
            "npm run check",
            "npm run build",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".isaac-viewer-", dir=output.parent
    ) as temp:
        staged = Path(temp) / "artifact"
        shutil.copytree(dist, staged / "dist")
        (staged / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        for p in staged.rglob("*"):
            p.chmod(0o555 if p.is_dir() else 0o444)
        if output.exists():
            raise FileExistsError(output)
        os.rename(staged, output)
        output.chmod(0o555)
    return {
        "artifact": str(output),
        "viewer_dist": str(output / "dist"),
        "manifest_sha256": digest(output / "manifest.json"),
        "files": len(files),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the existing npm cache without network access",
    )
    args = parser.parse_args()
    print(json.dumps(build(args.output, offline=args.offline), sort_keys=True))


if __name__ == "__main__":
    main()
