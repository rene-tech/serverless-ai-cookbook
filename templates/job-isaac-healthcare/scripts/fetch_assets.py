"""Fetch exact public scene assets and localize their USD dependencies at image build time."""

import argparse
import hashlib
import importlib.util
import itertools
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from pxr import Ar, Sdf, UsdUtils


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_path(target, name):
    relative = Path(name)
    if not name or relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError("Asset manifest path leaves the image asset directory")
    return target / relative


def source_identity(value):
    if Ar.IsPackageRelativePath(unquote(value)):
        outer, member = Ar.SplitPackageRelativePathOuter(unquote(value))
        return Ar.JoinPackageRelativePath(source_identity(outer), member)
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"}:
        return urlunsplit(("https", parsed.netloc, quote(unquote(parsed.path), safe="/<>"), "", ""))
    return value


def verify_mdl_assets(manifest, target, mapping, patterns):
    """Prove the exact pinned MDL resources resolve in the preserved layout.

    Keep shader source unchanged. An HTTP module URL alone is not an offline
    dependency proof, and optional material-editor thumbnails are not textures.
    """
    spec = importlib.util.spec_from_file_location(
        "isaac_pinned_mdl_dependencies", Path(__file__).with_name("mdl_dependencies.py")
    )
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    reports = []
    for row in manifest["files"]:
        if Path(row["path"]).suffix.lower() != ".mdl":
            continue
        path = local_path(target, row["path"])
        observed = parser.extract_dependencies(
            path.read_bytes().decode("utf-8"), source_url=row["url"],
            builtin_material_provenance=manifest.get("builtin_material_provenance", {}),
        )
        if observed != manifest.get("mdl_dependencies", {}).get(row["url"]):
            raise ValueError("MDL source dependency evidence differs from its immutable manifest")
        required = []
        for item in observed["required"]:
            name = item.get("reference")
            if item["kind"] == "module":
                name = item["module"].replace("::", "/") + ".mdl"
            if item["resolution"] not in {
                "declared-relative-resource", "declared-relative-module", "versioned-relative-module",
            } or not name or Path(name).is_absolute():
                raise ValueError("MDL search-root/URL dependency needs an explicit offline localization plan")
            mapped = mapping.get(source_identity(item["url"]))
            actual = (path.parent / name).resolve()
            if mapped is None or actual != Path(mapped).resolve() or not actual.is_relative_to(target.resolve()):
                raise ValueError("Required MDL dependency is absent from its pinned relative layout")
            if item.get("pattern"):
                if mapped not in patterns or not all(Path(tile).is_file() for tile in patterns[mapped]):
                    raise ValueError("MDL tiled resource lacks its complete immutable inventory")
            elif not actual.is_file():
                raise ValueError("Required MDL dependency is not a pinned regular file")
            required.append({"kind": item["kind"], "url": item["url"], "path": mapped,
                             "files": patterns[mapped] if item.get("pattern") else [mapped]})
        for item in observed["builtins"]:
            provenance = item["provenance"]
            source = Path(provenance["path"])
            if not source.is_file() or sha(source) != provenance["sha256"]:
                raise ValueError("Builtin MDL module differs from its installed path/SHA256 proof")
        reports.append({
            "path": row["path"], "source_sha256": row["sha256"], "required": required,
            "builtin_modules": observed["builtins"], "optional_editor_thumbnails": observed["optional"],
        })
    (target / "mdl-dependencies.json").write_text(json.dumps({
        "schema": "isaac-mdl-offline-layout/v1", "modules": reports,
        "source_manifest_canonical_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "verifier_sha256": sha(Path(__file__)),
        "parser_sha256": sha(Path(__file__).with_name("mdl_dependencies.py")),
        "scope": "Exact source/resources/builtin modules and relative layout; not GPU shader compilation.",
    }, indent=2) + "\n")


def fetch(manifest_path, target, source_directory=None, composed_report=None):
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("missing_assets") and composed_report is None:
        raise ValueError("Authored missing references require exact composed-root qualification")
    target.mkdir(parents=True, exist_ok=True)
    for row in manifest["files"]:
        path = local_path(target, row["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if source_directory is not None:
            source_path = local_path(source_directory, row["path"])
            if not source_path.is_file() or source_path.is_symlink():
                raise ValueError("Pinned asset cache member is not a regular file")
            shutil.copyfile(source_path, path)
        else:
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
        mapping[source_identity(row["url"])] = str(target / row["path"])
        if "original_reference" in row:
            mapping[row["original_reference"]] = str(target / row["path"])
    patterns = {}
    for url in manifest.get("missing_assets", {}):
        parsed = urlsplit(url)
        root = manifest["source_root"]
        name = unquote(url[len(root):]) if url.startswith(root) else "external/" + parsed.netloc + unquote(parsed.path)
        mapping[source_identity(url)] = str(local_path(target, name))
    for url, item in manifest.get("udim_patterns", {}).items():
        pattern = str(local_path(target, item["path"]))
        tiles = item["tiles"]
        if "<UDIM>" not in pattern or not tiles or any(source_identity(tile) not in mapping for tile in tiles):
            raise ValueError("UDIM pattern lacks its complete pinned tile inventory")
        patterns[pattern] = [mapping[source_identity(tile)] for tile in tiles]
        mapping[source_identity(url)] = pattern
        mapping[url.replace("https://", "http://", 1)] = pattern
    for url, item in manifest.get("package_members", {}).items():
        outer = mapping.get(source_identity(item["archive_url"]))
        if outer is None:
            raise ValueError("Package member lacks its pinned outer archive")
        mapping[source_identity(url)] = Ar.JoinPackageRelativePath(outer, item["member"])
    verify_mdl_assets(manifest, target, mapping, patterns)
    materialized = []
    for row in manifest["files"]:
        path = target / row["path"]
        if path.suffix in {".usd", ".usda", ".usdc"}:
            layer = Sdf.Layer.FindOrOpen(str(path))
            if layer is None:
                raise ValueError(f"Pinned USD asset is unreadable: {row['path']}")
            # Missing material-editor thumbnails do not become remote lookups.
            # Remove only the exact standard UI metadata uses classified by the
            # pinned source audit; never remove a rendering/composition input.
            omitted_icons = []
            for missing, evidence in manifest.get("missing_optional_ui_assets", {}).items():
                for use in evidence["uses"]:
                    if source_identity(use["source"]) != source_identity(row["url"]):
                        continue
                    for location in use["attributes"]:
                        attribute = layer.GetAttributeAtPath(location)
                        if (
                            not attribute or attribute.name != "ui:nodegraph:node:icon"
                            or not isinstance(attribute.default, Sdf.AssetPath)
                            or source_identity(urljoin(row["url"], attribute.default.path)) != source_identity(missing)
                        ):
                            raise ValueError("Optional UI metadata differs from its pinned classification")
                        omitted_icons.append(location)
                        attribute.owner.RemoveProperty(attribute)
            UsdUtils.ModifyAssetPaths(
                layer,
                lambda reference, source_url=row["url"]: mapping.get(
                    source_identity(urljoin(source_url, reference)), mapping.get(reference, reference)
                ),
            )
            layer.Save()
            dependencies = UsdUtils.ExtractExternalReferences(str(path))
            for reference in itertools.chain.from_iterable(dependencies):
                if (
                    reference not in manifest["builtin_materials"]
                    and not Path(reference).is_file()
                    and not (Ar.IsPackageRelativePath(reference) and Ar.GetResolver().Resolve(reference))
                    and not (
                        reference in patterns
                        and all(Path(tile).is_file() for tile in patterns[reference])
                    )
                    and reference not in {
                        mapping[source_identity(url)] for url in manifest.get("missing_assets", {})
                    }
                    and not (
                        Ar.IsPackageRelativePath(reference)
                        and Ar.SplitPackageRelativePathOuter(reference)[0] in {
                            mapping[source_identity(url)] for url in manifest.get("missing_assets", {})
                        }
                    )
                ):
                    raise ValueError(f"USD dependency was not localized: {reference}")
        materialized.append(
            {
                "path": row["path"],
                "source_url": row["url"],
                "source_sha256": row["sha256"],
                "sha256": sha(path),
                "size_bytes": path.stat().st_size,
                **({"omitted_ui_icon_attributes": omitted_icons} if path.suffix in {".usd", ".usda", ".usdc"} and omitted_icons else {}),
            }
        )
    (target / "manifest.json").write_text(
        json.dumps(
            {"asset_generation": manifest["asset_generation"],
             "source_root": manifest.get("source_root"), "files": materialized},
            indent=2,
        )
        + "\n"
    )
    if composed_report is not None:
        subprocess.run([
            sys.executable, "-I", str(Path(__file__).with_name("verify_composed_assets.py")),
            "--source-manifest", str(manifest_path), "--directory", str(target),
            "--report", str(composed_report),
        ], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--source-directory", type=Path, help="Already downloaded raw files; every byte is reverified")
    parser.add_argument("--composed-report", type=Path, help="Verify every composed root before accepting unresolved weaker authored references")
    args = parser.parse_args()
    fetch(args.manifest, args.target, args.source_directory, args.composed_report)
