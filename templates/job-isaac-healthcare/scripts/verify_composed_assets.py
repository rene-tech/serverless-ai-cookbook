"""Audit localized USD roots without flattening or changing authored opinions.

Run this CPU build gate with networking disabled. A missing authored texture is
permitted only when the complete composed-root/variant audit proves that every
known use is overridden. This is an asset-source proof, not a renderer test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import traceback
import zipfile
from collections import deque
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from pxr import Ar, Pcp, Sdf, Usd, UsdUtils


ASSET_TYPES = (Sdf.ValueTypeNames.Asset, Sdf.ValueTypeNames.AssetArray)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(value):
    parts = urlsplit(value)
    if parts.scheme in {"http", "https"}:
        if parts.query or parts.fragment or parts.username:
            raise ValueError("Asset source URL contains nonidentity fields")
        return urlunsplit(("https", parts.netloc, quote(unquote(parts.path), safe="/"), "", ""))
    return value


def local_path(directory, value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("Manifest asset path leaves its directory")
    return directory / path


def source_path(url, source_root):
    url, source_root = identity(url), identity(source_root)
    if url.startswith(source_root):
        return unquote(url[len(source_root):])
    parts = urlsplit(url)
    return "external/" + parts.netloc + unquote(parts.path)


def assets(value):
    if isinstance(value, Sdf.AssetPath):
        return [value]
    if value is None or isinstance(value, Sdf.ValueBlock):
        return []
    return list(value)


def value_record(value):
    return [{"authored": item.path, "resolved": item.resolvedPath} for item in assets(value)]


def anchored(reference, layer):
    if not reference or urlsplit(reference).scheme:
        return identity(reference)
    if Ar.IsPackageRelativePath(reference):
        outer, member = Ar.SplitPackageRelativePathOuter(reference)
        return Ar.JoinPackageRelativePath(anchored(outer, layer), member)
    layer_name = layer.realPath or layer.identifier
    if Path(layer_name).suffix.lower() == ".usdz" and Path(layer_name).is_file():
        with zipfile.ZipFile(layer_name) as archive:
            layer_name = Ar.JoinPackageRelativePath(layer_name, archive.namelist()[0])
    if Ar.IsPackageRelativePath(layer_name) and not Path(reference).is_absolute():
        outer, member = Ar.SplitPackageRelativePathOuter(layer_name)
        member = posixpath.normpath(posixpath.join(posixpath.dirname(member), reference))
        if member.startswith("../") or member.startswith("/"):
            raise ValueError("Package-relative asset leaves its pinned archive")
        return Ar.JoinPackageRelativePath(outer, member)
    if Path(reference).is_absolute():
        return str(Path(reference).resolve())
    return str((Path(layer_name).parent / reference).resolve())


def verify(source_manifest, directory):
    source_manifest, directory = Path(source_manifest).resolve(), Path(directory).resolve()
    source = json.loads(source_manifest.read_bytes())
    local_manifest = directory / "manifest.json"
    localized = json.loads(local_manifest.read_bytes())
    report = {
        "schema": "isaac-healthcare-composed-assets/v1", "status": "failed",
        "scope": "all seed roots, authored variant combinations, default and asset time samples",
        "usd_version": list(Usd.GetVersion()), "verifier_sha256": sha(__file__),
        "source_manifest_sha256": sha(source_manifest),
        "localized_manifest_sha256": sha(local_manifest),
        "roots": [], "missing_authored_assets": {}, "format_limitations": [], "errors": [],
        "writes_to_asset_files": False, "temporary_variant_selection_layers": True,
        "renderer_execution": "not-performed",
    }
    errors = report["errors"]
    source_rows = {row["path"]: row for row in source["files"]}
    local_rows = {row["path"]: row for row in localized["files"]}
    if len(source_rows) != len(source["files"]) or len(local_rows) != len(localized["files"]):
        raise ValueError("Duplicate asset manifest path")
    if source_rows.keys() != local_rows.keys():
        raise ValueError("Localized inventory differs from source inventory")
    pinned = {}
    by_url = {}
    for name, row in source_rows.items():
        file = local_path(directory, name)
        actual = local_rows[name]
        if file.is_symlink() or not file.is_file():
            raise ValueError(f"Localized asset is not a regular file: {name}")
        if file.stat().st_size != actual["size_bytes"] or sha(file) != actual["sha256"]:
            raise ValueError(f"Localized asset bytes changed: {name}")
        if actual.get("source_sha256") != row["sha256"]:
            raise ValueError(f"Localized asset source binding changed: {name}")
        if identity(actual.get("source_url", "")) != identity(row["url"]):
            raise ValueError(f"Localized asset URL binding changed: {name}")
        key = str(file.resolve())
        pinned[key] = {"path": name, "source_url": row["url"],
                       "source_sha256": row["sha256"], "sha256": actual["sha256"]}
        by_url[identity(row["url"])] = key
    builtin = {}
    for name, proof in source.get("builtin_material_provenance", {}).items():
        file = Path(proof["path"])
        if not file.is_absolute() or not file.is_file() or sha(file) != proof["sha256"]:
            raise ValueError(f"Installed builtin material bytes differ: {name}")
        builtin[name] = {"path": str(file.resolve()), "sha256": proof["sha256"]}
    report["installed_builtin_materials"] = builtin
    patterns = {}
    for url, entry in source.get("udim_patterns", {}).items():
        pattern = str(local_path(directory, entry["path"]).resolve())
        tiles = [by_url.get(identity(tile)) for tile in entry["tiles"]]
        if "<UDIM>" not in pattern or not tiles or any(tile not in pinned for tile in tiles):
            raise ValueError("UDIM pattern has no complete pinned tile inventory")
        matcher = re.compile(re.escape(pattern).replace(re.escape("<UDIM>"), r"\d{4}"))
        if not all(matcher.fullmatch(tile) for tile in tiles):
            raise ValueError("UDIM tile identity differs from its declared pattern")
        patterns[pattern] = tiles
    missing = {}
    for url, evidence in source.get("missing_assets", {}).items():
        path = str(local_path(directory, source_path(url, source["source_root"])).resolve())
        if path in pinned or Path(path).exists():
            raise ValueError("A declared missing asset is actually present")
        missing[path] = {"source_url": url, "download_evidence": evidence,
                         "uses": [], "observations": [], "inactive_observations": []}

    package_members = {}

    def package_record(path):
        if path in package_members:
            return package_members[path]
        outer, member = Ar.SplitPackageRelativePathOuter(path)
        if outer not in pinned or Ar.IsPackageRelativePath(member):
            return None
        if member != posixpath.normpath(member) or member.startswith(("/", "../")):
            return None
        with zipfile.ZipFile(outer) as archive:
            matches = [item for item in archive.infolist() if item.filename == member]
            if len(matches) != 1 or matches[0].is_dir():
                return None
            with archive.open(matches[0]) as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            record = {"kind": "pinned_package_member", "archive": pinned[outer],
                      "archive_local_path": outer, "member": member, "sha256": digest,
                      "size_bytes": matches[0].file_size, "local_path": path}
            package_members[path] = record
            return record

    declared_packages = {}
    for url, evidence in source.get("package_members", {}).items():
        archive_url, member = evidence["archive_url"], evidence["member"]
        if identity(url) != identity(Ar.JoinPackageRelativePath(archive_url, member)):
            raise ValueError("Package member source identity does not match its archive/member fields")
        outer = by_url.get(identity(archive_url))
        if outer is None:
            outer = str(local_path(directory, source_path(archive_url, source["source_root"])).resolve())
            if outer not in missing:
                raise ValueError("Package member archive is neither pinned nor declared missing")
        path = Ar.JoinPackageRelativePath(outer, member)
        declared_packages[path] = {"source_url": url, "archive_url": archive_url, "member": member}
        if outer in pinned and package_record(path) is None:
            missing[path] = {"source_url": url, "download_evidence": {
                "reason": "member_absent_in_pinned_package", "archive": pinned[outer], "member": member},
                "uses": [], "observations": [], "inactive_observations": []}

    def resolve(reference, layer=None):
        if not reference:
            return {"kind": "empty"}
        if reference in builtin:
            return {"kind": "installed_builtin", **builtin[reference]}
        path = anchored(reference, layer) if layer else str(Path(reference).resolve()) if Path(reference).is_absolute() else reference
        if Ar.IsPackageRelativePath(path):
            package = package_record(path)
            if package:
                return package
            outer, member = Ar.SplitPackageRelativePathOuter(path)
            if outer in missing:
                return {"kind": "declared_missing", "local_path": outer,
                        "source_url": missing[outer]["source_url"], "requested_member": member}
        if path in pinned:
            return {"kind": "pinned_file", **pinned[path], "local_path": path}
        if path in patterns:
            return {"kind": "pinned_udim", "local_path": path, "tiles": patterns[path]}
        if path in missing:
            return {"kind": "declared_missing", "local_path": path, "source_url": missing[path]["source_url"]}
        return {"kind": "unresolved", "reference": reference, "local_path": path}

    layers = {}
    unknown_missing_uses = []
    layer_names = [file for file in pinned if Path(file).suffix.lower() in {".usd", ".usda", ".usdc", ".usdz"}]
    for file in pinned:
        if Path(file).suffix.lower() == ".usdz":
            with zipfile.ZipFile(file) as archive:
                names = archive.namelist()
                if len(names) != len(set(names)):
                    raise ValueError("Pinned package contains duplicate member identities")
                for member in names:
                    if Path(member).suffix.lower() in {".usd", ".usda", ".usdc"}:
                        layer_names.append(Ar.JoinPackageRelativePath(file, member))
    for file in layer_names:
        layer = Sdf.Layer.FindOrOpen(file)
        if not layer:
            raise ValueError(f"Pinned USD layer cannot be opened: {file}")
        layers[file] = layer
        recognized = set()

        def visit(location):
            spec = layer.GetAttributeAtPath(location)
            if not spec or spec.typeName not in ASSET_TYPES:
                return
            values = [("default", spec.default)]
            values.extend((time, layer.QueryTimeSample(location, time))
                          for time in layer.ListTimeSamplesForPath(location))
            for time, value in values:
                for item in assets(value):
                    state = resolve(item.path, layer)
                    if state["kind"] == "declared_missing":
                        path = state["local_path"]
                        recognized.add(path)
                        missing[path]["uses"].append({
                            "layer": layer.realPath or layer.identifier,
                            "source": pinned.get(file) or package_record(file), "attribute": str(location),
                            "time": time, "authored": item.path,
                        })
                    elif state["kind"] == "unresolved":
                        errors.append({**state, "kind": "unclassified_authored_asset", "layer": file,
                                       "attribute": str(location), "time": time})
        layer.Traverse(Sdf.Path.absoluteRootPath, visit)
        for category, references in zip(("sublayer", "reference_or_asset", "payload"),
                                        UsdUtils.ExtractExternalReferences(file)):
            for reference in references:
                state = resolve(reference, layer)
                if state["kind"] == "declared_missing" and state["local_path"] not in recognized:
                    unknown_missing_uses.append({"layer": file, "category": category, **state})
                elif state["kind"] == "unresolved":
                    errors.append({**state, "kind": "unclassified_external_reference", "layer": file,
                                   "category": category})
    errors.extend({**use, "kind": "missing_nonattribute_dependency"} for use in unknown_missing_uses)

    def stack_record(attr, time):
        result = []
        for spec, offset in attr.GetPropertyStackWithLayerOffsets(time):
            result.append({
                "layer": spec.layer.realPath or spec.layer.identifier, "attribute": str(spec.path),
                "default": value_record(spec.default),
                "time_samples": [{"time": sample, "stage_time": sample * offset.scale + offset.offset,
                                  "value": value_record(spec.layer.QueryTimeSample(spec.path, sample))}
                                 for sample in spec.layer.ListTimeSamplesForPath(spec.path)],
                "layer_offset": {"offset": offset.offset, "scale": offset.scale},
            })
        return result

    def composition_error(error, stage, root_record):
        # Python Pcp exposes only errorType/rootSite, not C++ assetPath fields.
        # Recognize the exact general diagnostic shape; any other error fails.
        message = str(error)
        match = re.fullmatch(
            r"Could not open asset @([^@]+)@ for payload introduced by @([^@]+)@<([^>]+)> -- "
            r"Cannot determine file format for @([^@]+)@\.", message)
        if error.errorType == Pcp.ErrorType_InvalidAssetPath and match:
            target, source_layer, site, _ = match.groups()
            path = str(Path(target).resolve())
            layer = layers.get(str(Path(source_layer).resolve()))
            spec = layer.GetPrimAtPath(site) if layer else None
            payloads = spec.payloadList.GetAppliedItems() if spec else []
            if (path in pinned and Sdf.FileFormat.FindByExtension(path) is None
                    and any(anchored(item.assetPath, layer) == path for item in payloads)):
                record = {"root": root_record["source_url"], "variants": root_record["variants"],
                          "kind": "pinned_payload_without_usd_format_plugin", "asset": pinned[path],
                          "local_path": path, "site": site, "source_layer": source_layer,
                          "diagnostic": message,
                          "meaning": "Bytes are closed; this USD build leaves the payload unreadable. No geometry is substituted."}
                report["format_limitations"].append(record)
                return {"classification": "format_limitation", **record}
        record = {"kind": "composition_error", "root": root_record["source_url"],
                  "variants": root_record["variants"], "diagnostic": message}
        errors.append(record)
        return record

    seeds = source.get("seed_urls")
    if not isinstance(seeds, list) or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Source manifest needs distinct explicit seed_urls")
    for seed in seeds:
        file = by_url.get(identity(seed))
        if file not in pinned:
            raise ValueError(f"Seed is not a pinned asset: {seed}")
        if file not in layers:
            report["roots"].append({"source_url": seed, "path": pinned[file]["path"],
                                    "kind": "pinned_non_layer_asset", "provenance": pinned[file],
                                    "composition": "not_applicable"})
            continue
        pending, seen = deque([{}]), set()
        while pending:
            requested = pending.popleft()
            session = Sdf.Layer.CreateAnonymous("composed-assets-session.usda")
            stage = Usd.Stage.Open(layers[file], session, load=Usd.Stage.LoadAll)
            if not stage:
                raise ValueError(f"Pinned root cannot be composed: {seed}")
            stage.SetEditTarget(session)
            # Ancestor variant selections establish nested variant sites first.
            for (prim_path, name), choice in sorted(requested.items(), key=lambda item: (item[0][0].count("/"), item[0])):
                prim = stage.GetPrimAtPath(prim_path)
                if prim and name in prim.GetVariantSets().GetNames():
                    prim.GetVariantSet(name).SetVariantSelection(choice)
            prims = list(Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)))
            selections, choices = {}, {}
            for prim in prims:
                # A variant on an inactive prim can itself reactivate that prim.
                for name in prim.GetVariantSets().GetNames():
                    key = (str(prim.GetPath()), name)
                    selections[key] = prim.GetVariantSet(name).GetVariantSelection()
                    choices[key] = prim.GetVariantSet(name).GetVariantNames()
            state_key = tuple(sorted(selections.items()))
            if state_key in seen:
                continue
            seen.add(state_key)
            for key, alternatives in choices.items():
                for choice in alternatives:
                    if choice != selections[key]:
                        pending.append({**selections, key: choice})
            record = {"source_url": seed, "path": pinned[file]["path"], "kind": "composed_usd_root",
                      "variants": [{"prim": key[0], "set": key[1], "selected": choice}
                                   for key, choice in sorted(selections.items())],
                      "used_layers": [], "composition_errors": [], "asset_values": []}
            for used in stage.GetUsedLayers():
                if used == session:
                    continue
                path = used.realPath or used.identifier
                provenance = pinned.get(path) or (package_record(path) if Ar.IsPackageRelativePath(path) else None)
                if provenance is None:
                    errors.append({"kind": "unlisted_composed_layer", "root": seed, "layer": path})
                record["used_layers"].append({"layer": path, "provenance": provenance})
            record["composition_errors"] = [composition_error(error, stage, record)
                                            for error in stage.GetCompositionErrors()]
            for prim in prims:
                if not prim.IsActive():
                    prim_stack = list(prim.GetPrimStack())
                    active_opinions = [spec for spec in prim_stack if spec.HasInfo("active")]
                    if active_opinions and active_opinions[0].active is False:
                        stack = [{"layer": spec.layer.realPath or spec.layer.identifier,
                                  "prim": str(spec.path),
                                  "active": spec.active if spec.HasInfo("active") else None,
                                  "source": pinned.get(spec.layer.realPath)} for spec in prim_stack]
                        for item in missing.values():
                            contributing = set()
                            for use in item["uses"]:
                                for spec in prim_stack:
                                    if ((spec.layer.realPath or spec.layer.identifier) == use["layer"]
                                            and Sdf.Path(use["attribute"]).GetPrimPath().HasPrefix(spec.path)):
                                        contributing.add((use["layer"], use["attribute"]))
                            if contributing:
                                item["inactive_observations"].append({
                                    "root": seed, "variants": record["variants"],
                                    "inactive_ancestor": str(prim.GetPath()), "strongest_active": False,
                                    "prim_stack": stack, "contributing_uses": [list(use) for use in sorted(contributing)]})
                    continue
                if not prim.IsLoaded():
                    continue
                for attr in prim.GetAttributes():
                    if attr.GetTypeName() not in ASSET_TYPES:
                        continue
                    times = set(attr.GetTimeSamples())
                    default_stack = stack_record(attr, Usd.TimeCode.Default())
                    times.update(sample["stage_time"] for spec in default_stack for sample in spec["time_samples"])
                    remaining, sampled = deque([None, *sorted(times)]), set()
                    while remaining:
                        time = remaining.popleft()
                        if time in sampled:
                            continue
                        sampled.add(time)
                        code = Usd.TimeCode.Default() if time is None else Usd.TimeCode(time)
                        stack = stack_record(attr, code)
                        for spec in stack:
                            remaining.extend(sample["stage_time"] for sample in spec["time_samples"]
                                             if sample["stage_time"] not in sampled)
                        values = value_record(attr.Get(code))
                        selected = []
                        for value in values:
                            state = resolve(value["resolved"] or value["authored"])
                            selected.append({**value, "resolution": state})
                            if state["kind"] in {"declared_missing", "unresolved"}:
                                errors.append({**state, "kind": "unresolved_composed_asset", "root": seed,
                                               "variants": record["variants"], "attribute": str(attr.GetPath()),
                                               "time": "default" if time is None else time})
                        observation = {"attribute": str(attr.GetPath()), "time": "default" if time is None else time,
                                       "values": selected, "stack": stack,
                                       "resolve_source": str(attr.GetResolveInfo(code).GetSource())}
                        record["asset_values"].append(observation)
                        for path, item in missing.items():
                            uses = {(use["layer"], use["attribute"]) for use in item["uses"]}
                            contributing = [(spec["layer"], spec["attribute"]) for spec in stack
                                            if (spec["layer"], spec["attribute"]) in uses]
                            if contributing:
                                item["observations"].append({"root": seed, "variants": record["variants"],
                                    **observation, "contributing_uses": [list(use) for use in contributing],
                                    "selected_missing": any(value["resolution"].get("local_path") == path
                                                            for value in selected)})
            report["roots"].append(record)
    for path, item in missing.items():
        observed = {tuple(use) for obs in item["observations"] for use in obs["contributing_uses"]}
        inactive = {tuple(use) for obs in item["inactive_observations"] for use in obs["contributing_uses"]}
        expected = {(use["layer"], use["attribute"]) for use in item["uses"]}
        proven = bool(expected) and expected <= observed | inactive and not any(obs["selected_missing"] for obs in item["observations"])
        item["classification"] = (
            "inactive_or_overridden_in_all_composed_roots_and_variants" if proven and inactive
            else "overridden_in_all_composed_roots_and_variants" if proven
            else "unproven_or_selected")
        item["local_path"] = path
        if not proven:
            errors.append({"kind": "missing_asset_without_complete_override_proof", "source_url": item["source_url"],
                           "unobserved_uses": [list(use) for use in sorted(expected - observed - inactive)]})
        report["missing_authored_assets"][item["source_url"]] = item
    report["summary"] = {"seed_roots": len(seeds),
                         "composed_configurations": sum(row["kind"] == "composed_usd_root" for row in report["roots"]),
                         "pinned_non_layer_seeds": sum(row["kind"] == "pinned_non_layer_asset" for row in report["roots"]),
                         "pinned_files": len(pinned), "missing_authored_assets": len(missing),
                         "format_limitations": len(report["format_limitations"]), "errors": len(errors)}
    report["package_members"] = package_members
    report["declared_package_members"] = declared_packages
    report["status"] = "passed" if not errors else "failed"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args.source_manifest, args.directory)
    except Exception as error:
        report = {"schema": "isaac-healthcare-composed-assets/v1", "status": "failed",
                  "verifier_sha256": sha(__file__), "error": f"{type(error).__name__}: {error}",
                  "traceback": traceback.format_exc()}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "summary": report.get("summary"), "error": report.get("error")}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
