"""Derive built-in marker asset seeds from pinned installed IsaacLab source.

This build-time audit does not import IsaacLab or execute configuration code.
It does not change markers, scene settings, or customer workflow eligibility.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(node, names):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal(node.left, names) + literal(node.right, names)
    if isinstance(node, ast.JoinedStr):
        result = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                result.append(part.value)
            elif isinstance(part, ast.FormattedValue) and part.conversion == -1 and part.format_spec is None:
                result.append(literal(part.value, names))
            else:
                raise ValueError("Unsupported dynamic marker asset expression")
        return "".join(result)
    raise ValueError("Marker asset expression is not a static source-declared path")


def inspect(marker_root, kit_config, kit_receipt):
    receipt = json.loads(kit_receipt.read_bytes())
    original, localized = receipt["source_asset_root"], receipt["local_asset_root"]
    if urlsplit(original).scheme != "https" or urlsplit(original).query or urlsplit(original).fragment:
        raise ValueError("Kit source root must be an ordinary immutable-source HTTPS path")
    current = kit_config.read_bytes()
    if hashlib.sha256(current).hexdigest() != receipt["sha256"]:
        raise ValueError("Installed Kit settings differ from the exact localization receipt")
    pattern = r'^(persistent\.isaac\.asset_root\.(?:default|cloud|nvidia) = )"' + re.escape(localized) + '"$'
    restored, count = re.subn(pattern, lambda match: match.group(1) + json.dumps(original), current.decode(), flags=re.MULTILINE)
    if count != 3 or hashlib.sha256(restored.encode()).hexdigest() != receipt["source_sha256"]:
        raise ValueError("Kit-root source mapping is not exactly reversible")
    names = {"NUCLEUS_ASSET_ROOT_DIR": original,
             "NVIDIA_NUCLEUS_DIR": original + "/NVIDIA",
             "ISAAC_NUCLEUS_DIR": original + "/Isaac",
             "ISAACLAB_NUCLEUS_DIR": original + "/Isaac/IsaacLab"}
    sources, references, primitive_calls = [], [], []
    for path in sorted(marker_root.rglob("*.py")):
        if path.is_symlink():
            raise ValueError("Marker source tree contains a symbolic link")
        text = path.read_text()
        module = ast.parse(text, filename=str(path))
        relative = path.relative_to(marker_root).as_posix()
        sources.append({"path": relative, "sha256": sha(path)})
        for statement in module.body:
            # Config names are retained for provenance, never used as an allowlist.
            owner = None
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                owner = statement.targets[0].id
            for node in ast.walk(statement):
                if not isinstance(node, ast.Call):
                    continue
                function = ast.unparse(node.func)
                if function.endswith("Cfg"):
                    primitive_calls.append({"source": relative, "line": node.lineno, "configuration": owner, "constructor": function})
                for item in node.keywords:
                    # Declared file-backed marker inputs must all be explained.
                    if item.arg not in {"usd_path", "mdl_path", "texture_path"}:
                        continue
                    value = literal(item.value, names)
                    parsed = urlsplit(value)
                    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
                        raise ValueError("A declared marker file has no qualified ordinary HTTPS source")
                    references.append({"source": relative, "line": item.value.lineno,
                                       "configuration": owner, "constructor": function,
                                       "field": item.arg, "expression": ast.get_source_segment(text, item.value),
                                       "url": value})
    if not sources or not references:
        raise ValueError("Installed marker source audit found no file-backed declarations")
    return {"schema": "isaaclab-default-marker-sources/v1", "marker_source_files": sources,
            "kit_config_sha256": sha(kit_config), "kit_receipt_sha256": sha(kit_receipt),
            "source_asset_root": original, "local_asset_root": localized,
            "references": references, "configuration_constructors": primitive_calls,
            "seed_urls": sorted({row["url"] for row in references}),
            "scope": "All declared file-backed defaults in the installed marker source tree; recursive dependencies require a separate pinned closure.",
            "imports_or_configuration_execution": False, "scene_or_physics_changes": False}


def verify_installed(marker_root, kit_config, kit_receipt, source_manifest, asset_root, composed_report):
    """Bind every installed default to the existing recursive offline proof."""
    observed = inspect(marker_root, kit_config, kit_receipt)
    source = json.loads(source_manifest.read_bytes())
    local_manifest = asset_root / "manifest.json"
    localized = json.loads(local_manifest.read_bytes())
    composed = json.loads(composed_report.read_bytes())
    if (composed.get("status") != "passed" or composed.get("errors")
            or composed.get("source_manifest_sha256") != sha(source_manifest)
            or composed.get("localized_manifest_sha256") != sha(local_manifest)):
        raise ValueError("Default marker closure has no matching complete composed-asset proof")
    provenance = source.get("default_marker_assets")
    fields = ("schema", "source_asset_root", "marker_source_files", "references", "seed_urls")
    if provenance != {key: observed[key] for key in fields}:
        raise ValueError("Default marker source declarations differ from the pinned manifest audit")
    source_rows = {row["url"]: row for row in source["files"]}
    local_rows = {row["source_url"]: row for row in localized["files"]}
    if len(source_rows) != len(source["files"]) or len(local_rows) != len(localized["files"]):
        raise ValueError("Asset manifest contains duplicate source identities")
    checked = []
    remote = observed["source_asset_root"].rstrip("/") + "/"
    for url in observed["seed_urls"]:
        if url not in source.get("seed_urls", []) or url not in source_rows or url not in local_rows:
            raise ValueError("An installed default marker is missing from the pinned asset closure: " + url)
        if not url.startswith(remote):
            raise ValueError("Default marker URL is outside its verified Kit root")
        source_row, local_row = source_rows[url], local_rows[url]
        expected = Path(observed["local_asset_root"]) / url.removeprefix(remote)
        actual = asset_root / local_row["path"]
        if (source_row["path"] != local_row["path"] or actual != expected
                or actual.is_symlink() or not actual.is_file()
                or asset_root.resolve() not in actual.resolve().parents):
            raise ValueError("Default marker file is absent or its source-to-Kit mapping changed: " + url)
        if (local_row.get("source_sha256") != source_row["sha256"]
                or actual.stat().st_size != local_row["size_bytes"] or sha(actual) != local_row["sha256"]):
            raise ValueError("Default marker bytes differ from the pinned localized inventory: " + url)
        configurations = [row for row in composed["roots"] if row.get("source_url") == url]
        if (not configurations or any(row.get("kind") != "composed_usd_root"
                                      or row.get("composition_errors") for row in configurations)):
            raise ValueError("Default marker has no successful recursive USD root proof: " + url)
        checked.append({"source_url": url, "path": local_row["path"], "sha256": local_row["sha256"],
                        "composed_configurations": len(configurations)})
    return {"status": "passed", "source_files": len(observed["marker_source_files"]),
            "file_declarations": len(observed["references"]), "roots": checked,
            "recursive_proof_sha256": sha(composed_report), "gpu_execution": "not-performed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker-root", type=Path, required=True)
    parser.add_argument("--kit-config", type=Path, required=True)
    parser.add_argument("--kit-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--composed-report", type=Path)
    args = parser.parse_args()
    verification = (args.source_manifest, args.asset_root, args.composed_report)
    if any(verification) and not all(verification):
        parser.error("Installed verification requires source-manifest, asset-root, and composed-report together")
    result = (verify_installed(args.marker_root, args.kit_config, args.kit_receipt, *verification)
              if all(verification) else inspect(args.marker_root, args.kit_config, args.kit_receipt))
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
