#!/usr/bin/env python3
"""Check pinned upstream files before installing the isolated environments."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    root = Path(sys.argv[1])
    manifest = json.loads((Path(__file__).parent / "upstream-locks.json").read_text())
    for name, expected in manifest["files"].items():
        path = root / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Pinned upstream source/lock differs: {name}")
    print(json.dumps({"status": "PASS", "upstream_revision": manifest["revision"], "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
