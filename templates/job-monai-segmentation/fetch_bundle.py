#!/usr/bin/env python3
"""Download the public Apache-2.0 checkpoint at an immutable revision, verify every file."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

REVISION = "8c4da75225ff7cb30292729dd704cceccae5413c"


def fetch(root):
    for name, expected in json.loads((root / "manifest.json").read_text()).items():
        path = root / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://huggingface.co/MONAI/spleen_ct_segmentation/resolve/{REVISION}/{name}"
            urllib.request.urlretrieve(url, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Bundle integrity check failed: {name}; remove that file and fetch again")
    print("Pinned MONAI bundle integrity verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "bundle")
    fetch(parser.parse_args().output)
