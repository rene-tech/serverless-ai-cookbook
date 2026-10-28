"""Prepare a pinned USD dependency manifest before building an offline runtime.

This is an operator build tool, not an inference-time downloader. Seed URLs must
be explicitly supplied. Every fetched byte is hashed; unresolved dependencies
fail the build rather than being silently fetched by a customer's simulation.
"""

import argparse
import hashlib
import importlib.util
import itertools
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from pxr import Ar, Sdf, UsdUtils


def mdl_dependencies(path, source_url, builtin_provenance):
    spec = importlib.util.spec_from_file_location(
        "isaac_pinned_mdl_dependencies", Path(__file__).with_name("mdl_dependencies.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.extract_dependencies(
        path.read_bytes().decode("utf-8"), source_url=source_url,
        builtin_material_provenance=builtin_provenance,
    )


def normalized_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
        raise ValueError(f"Dependency is not an ordinary public HTTP asset: {value}")
    if parsed.query or parsed.fragment:
        raise ValueError("Asset identities must not contain queries or fragments")
    return urlunsplit(("https", parsed.netloc, quote(unquote(parsed.path), safe="/"), "", ""))


def local_name(url, source_root):
    if url.startswith(source_root):
        name = unquote(url[len(source_root) :])
    else:
        parsed = urlsplit(url)
        name = "external/" + parsed.netloc + unquote(parsed.path)
    path = Path(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("Asset path leaves the staged tree")
    return path.as_posix()


def udim_tiles(url):
    """Expand a public S3 UDIM pattern using its authoritative paginated key list."""
    parsed = urlsplit(url)
    if not parsed.netloc.endswith(".amazonaws.com") or ".s3" not in parsed.netloc:
        raise ValueError("UDIM expansion needs an explicit supported S3 source or a local project asset set")
    key = unquote(parsed.path).lstrip("/")
    prefix = key.split("<UDIM>", 1)[0]
    matcher = re.compile(re.escape(key).replace(re.escape("<UDIM>"), r"\d{4}"))
    continuation, found, seen = None, [], set()
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if continuation:
            params["continuation-token"] = continuation
        listing = urlunsplit(("https", parsed.netloc, "/", urlencode(params), ""))
        with urlopen(listing, timeout=120) as response:
            document = ET.fromstring(response.read())
        for item in document.findall("{*}Contents/{*}Key"):
            if item.text and matcher.fullmatch(item.text):
                found.append(normalized_url("https://" + parsed.netloc + "/" + item.text))
        if document.findtext("{*}IsTruncated") != "true":
            break
        continuation = document.findtext("{*}NextContinuationToken")
        if not continuation or continuation in seen:
            raise ValueError("Incomplete or repeated S3 asset listing")
        seen.add(continuation)
    if not found:
        raise FileNotFoundError(f"No authoritative tiles found for {url}")
    return sorted(set(found))


def dependencies(path):
    """Separate material-editor icon metadata from composed/rendering assets.

    The original USD stays unchanged. A reference is optional only if removing
    the standard UI icon attributes eliminates every use of that reference.
    """
    layer = Sdf.Layer.FindOrOpen(str(path))
    if layer is None:
        raise ValueError(f"Unreadable pinned USD: {path}")
    original = set(itertools.chain.from_iterable(UsdUtils.ExtractExternalReferences(layer.identifier)))
    icons = {}
    def visit(location):
        attribute = layer.GetAttributeAtPath(location)
        if attribute and attribute.name == "ui:nodegraph:node:icon" and isinstance(attribute.default, Sdf.AssetPath):
            icons[str(location)] = attribute.default.path
    layer.Traverse(Sdf.Path.absoluteRootPath, visit)
    filtered = Sdf.Layer.CreateAnonymous("dependency-classification.usda")
    filtered.TransferContent(layer)
    for location in icons:
        attribute = filtered.GetAttributeAtPath(location)
        attribute.owner.RemoveProperty(attribute)
    required = set(itertools.chain.from_iterable(UsdUtils.ExtractExternalReferences(filtered.identifier)))
    return original, {reference: [name for name, value in icons.items() if value == reference]
                      for reference in original - required}


def discover(seeds, source_root, directory, *, asset_generation, builtins, maximum_bytes=None, record_missing=False, builtin_provenance=None, previous=None):
    directory.mkdir(parents=True, exist_ok=True)
    pending = [normalized_url(url) for url in seeds]
    visited, rows, paths, patterns = set(), [], set(), {}
    required, optional, missing_ui = set(pending), {}, {}
    uses, missing, packages, mdl = {}, {}, {}, {}
    total = 0
    previous_rows = {normalized_url(row["url"]): row for row in (previous or {}).get("files", [])}
    while pending:
        url = pending.pop(0)
        if url in visited:
            continue
        visited.add(url)
        name = previous_rows[url]["path"] if url in previous_rows else local_name(url, source_root)
        if Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
            raise ValueError("Previously pinned asset path leaves the staged tree")
        if name in paths:
            raise ValueError("Distinct asset URLs resolve to the same local file")
        paths.add(name)
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".download")
        checksum, length = hashlib.sha256(), 0
        if destination.is_file():
            with destination.open("rb") as existing:
                while block := existing.read(4 * 1024**2):
                    checksum.update(block)
                    length += len(block)
        else:
            print(json.dumps({"fetch": url, "path": name}), flush=True)
            try:
                source = urlopen(Request(url, headers={"User-Agent": "Isaac-asset-manifest/2"}), timeout=120)
            except HTTPError as error:
                if error.code == 404 and url in optional and url not in required:
                    missing_ui[url] = {"status": 404, "uses": optional[url]}
                    print(json.dumps({"missing_optional_material_editor_icon": url}), flush=True)
                    continue
                if error.code == 404 and record_missing:
                    missing[url] = {"reason": "HTTP404", "uses": uses.get(url, [])}
                    print(json.dumps({"unresolved_authored_asset": url, "status": 404}), flush=True)
                    continue
                raise
            with source:
                with temporary.open("xb") as output:
                    while block := source.read(4 * 1024**2):
                        length += len(block)
                        if maximum_bytes is not None and total + length > maximum_bytes:
                            raise ValueError("Explicit operator asset download budget exhausted")
                        output.write(block)
                        checksum.update(block)
                    output.flush()
                    os.fsync(output.fileno())
            temporary.rename(destination)
        total += length
        prior = previous_rows.get(url)
        if prior and (prior["sha256"], prior["size_bytes"]) != (checksum.hexdigest(), length):
            raise ValueError("Previously pinned source bytes changed")
        rows.append({
            "path": name, "url": url, "original_reference": url.replace("https://", "http://", 1),
            "sha256": checksum.hexdigest(), "size_bytes": length,
        })
        if destination.suffix.lower() in {".usd", ".usda", ".usdc"}:
            references, ui_only = dependencies(destination)
            for reference in sorted(references):
                if reference in builtins:
                    continue
                if not reference:
                    raise ValueError("Empty asset dependency")
                if Ar.IsPackageRelativePath(reference):
                    outer, member = Ar.SplitPackageRelativePathOuter(reference)
                    dependency = normalized_url(urljoin(url, outer))
                    identity = Ar.JoinPackageRelativePath(dependency, member)
                    packages[identity] = {"archive_url": dependency, "member": member}
                    uses.setdefault(dependency, []).append({"source": url, "reference": reference})
                    required.add(dependency)
                    if dependency not in visited:
                        pending.append(dependency)
                    continue
                if "<UDIM>" in reference:
                    pattern = urljoin(url, reference)
                    uses.setdefault(pattern, []).append({"source": url, "reference": reference})
                    try:
                        tiles = udim_tiles(pattern)
                    except FileNotFoundError:
                        if not record_missing:
                            raise
                        missing[pattern] = {"reason": "no-authoritative-UDIM-tiles", "uses": uses[pattern]}
                        print(json.dumps({"unresolved_authored_UDIM": pattern}), flush=True)
                        continue
                    patterns[pattern] = {"path": local_name(pattern, source_root), "tiles": tiles}
                    pending.extend(tiles)
                    continue
                dependency = normalized_url(urljoin(url, reference))
                uses.setdefault(dependency, []).append({"source": url, "reference": reference})
                if reference in ui_only:
                    optional.setdefault(dependency, []).append({"source": url, "attributes": ui_only[reference]})
                else:
                    required.add(dependency)
                    if dependency in missing_ui:
                        raise ValueError("An unavailable UI icon is also a required rendering/composition asset")
                if dependency not in visited:
                    pending.append(dependency)
        elif destination.suffix.lower() == ".mdl":
            evidence = mdl_dependencies(destination, url, builtin_provenance or {})
            mdl[url] = evidence
            for dependency in evidence["required"]:
                target = normalized_url(dependency["url"])
                uses.setdefault(target, []).append({"source": url, **dependency})
                required.add(target)
                if dependency.get("pattern"):
                    if "<UDIM>" not in dependency["url"]:
                        raise ValueError("MDL sequence/UVTILE assets require an explicit complete inventory")
                    tiles = udim_tiles(dependency["url"])
                    patterns[dependency["url"]] = {
                        "path": local_name(dependency["url"], source_root), "tiles": tiles,
                    }
                    pending.extend(tiles)
                elif target not in visited:
                    pending.append(target)
        progress = {"files": len(rows), "bytes": total, "pending": len(pending), "last": name}
        (directory / "discovery-progress.json").write_text(json.dumps(progress, indent=2) + "\n")
        print(json.dumps(progress), flush=True)
    return {
        "schema": "isaac-healthcare-asset-sources/v1",
        "asset_generation": asset_generation,
        "source_root": source_root,
        "seed_urls": sorted(set(normalized_url(url) for url in seeds)),
        "files": sorted(rows, key=lambda row: row["path"]),
        "builtin_materials": sorted(builtins),
        "builtin_material_provenance": builtin_provenance or {},
        "package_members": packages,
        "udim_patterns": patterns,
        "missing_optional_ui_assets": missing_ui,
        "missing_assets": missing,
        "mdl_dependencies": mdl,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=Path, required=True, help="JSON list of explicit asset URLs")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--asset-generation", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--builtin", action="append", default=["OmniPBR.mdl"])
    parser.add_argument("--builtin-manifest", type=Path, help="Installed Kit MDL relative names and file hashes")
    parser.add_argument("--maximum-bytes", type=int)
    parser.add_argument("--record-missing", action="store_true", help="Audit only: record proven missing authored references; final build still requires composed-root qualification")
    parser.add_argument("--previous-manifest", type=Path, help="Preserve already-pinned byte identities and image paths")
    args = parser.parse_args()
    builtins = set(args.builtin)
    builtin_provenance = {}
    if args.builtin_manifest:
        builtin_provenance = json.loads(args.builtin_manifest.read_text())
        builtins.update(builtin_provenance)
    result = discover(
        json.loads(args.seeds.read_text()), args.source_root, args.directory,
        asset_generation=args.asset_generation, builtins=builtins, maximum_bytes=args.maximum_bytes,
        record_missing=args.record_missing, builtin_provenance=builtin_provenance,
        previous=json.loads(args.previous_manifest.read_text()) if args.previous_manifest else None,
    )
    args.manifest.write_text(json.dumps(result, indent=2) + "\n")
