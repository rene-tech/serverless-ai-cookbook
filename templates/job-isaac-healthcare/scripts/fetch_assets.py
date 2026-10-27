"""Fetch exact public scene assets and localize their USD dependencies at image build time."""

import argparse
import hashlib
import itertools
import json
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from pxr import Sdf, UsdUtils


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(manifest_path, target):
    manifest = json.loads(manifest_path.read_bytes())
    target.mkdir(parents=True, exist_ok=True)
    for row in manifest["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Asset manifest path leaves the image asset directory")
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with (
            urllib.request.urlopen(row["url"], timeout=120) as source,
            path.open("wb") as destination,
        ):
            total = 0
            while block := source.read(4 * 1024**2):
                total += len(block)
                if total > row["size_bytes"]:
                    raise ValueError("Public asset exceeded its pinned size")
                destination.write(block)
        if path.stat().st_size != row["size_bytes"] or sha(path) != row["sha256"]:
            raise ValueError("Public asset content differs from its immutable manifest")
    mapping = {}
    for row in manifest["files"]:
        mapping[row["url"]] = str(target / row["path"])
        if "original_reference" in row:
            mapping[row["original_reference"]] = str(target / row["path"])
    materialized = []
    for row in manifest["files"]:
        path = target / row["path"]
        if path.suffix in {".usd", ".usda", ".usdc"}:
            layer = Sdf.Layer.FindOrOpen(str(path))
            UsdUtils.ModifyAssetPaths(
                layer,
                lambda reference, source_url=row["url"]: mapping.get(
                    urljoin(source_url, reference), mapping.get(reference, reference)
                ),
            )
            layer.Save()
            dependencies = UsdUtils.ExtractExternalReferences(str(path))
            for reference in itertools.chain.from_iterable(dependencies):
                if (
                    reference not in manifest["builtin_materials"]
                    and not Path(reference).is_file()
                ):
                    raise ValueError(f"USD dependency was not localized: {reference}")
        materialized.append(
            {
                "path": row["path"],
                "source_sha256": row["sha256"],
                "sha256": sha(path),
                "size_bytes": path.stat().st_size,
            }
        )
    (target / "manifest.json").write_text(
        json.dumps(
            {"asset_generation": manifest["asset_generation"], "files": materialized},
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    fetch(args.manifest, args.target)
