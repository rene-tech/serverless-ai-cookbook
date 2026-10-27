"""Materialize a job-owned SDK overlay without modifying the installed source.

Project code is executed as customer-authored code inside the job's isolation
boundary. Archive validation prevents extraction outside that boundary; it is
not a Python sandbox.
"""

import os
import shutil
import tarfile
from pathlib import Path, PurePosixPath

from .contract import checked, digest, json_loads, schema


def relative_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or "\x00" in value:
        raise ValueError("Project paths must be relative and cannot traverse parents")
    return path


def contained_path(root, value, *, directory=False):
    path = root.joinpath(*relative_path(value).parts)
    # Input archives cannot contain links, including at any path ancestor.
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("Project input path contains a symlink")
        cursor = cursor.parent
    if not path.exists() or (directory and not path.is_dir()):
        raise ValueError(f"Project input does not exist: {value}")
    return path


def extract_project(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    with tarfile.open(source, "r:*") as archive:
        members = archive.getmembers()
        required = sum(item.size for item in members if item.isfile())
        if required > shutil.disk_usage(destination).free:
            raise ValueError("Project archive exceeds available job scratch space")
        for item in members:
            path = relative_path(item.name)
            normalized = path.as_posix()
            if normalized == "." and item.isdir():
                continue
            if normalized in seen:
                raise ValueError(f"Duplicate project archive path: {normalized}")
            seen.add(normalized)
            if not item.isfile() and not item.isdir():
                raise ValueError("Project archive supports regular files and directories only")
            target = destination.joinpath(*path.parts)
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(item) as incoming, target.open("xb") as output:
                shutil.copyfileobj(incoming, output)
            # Preserve executable source scripts without granting special permissions.
            target.chmod(0o755 if item.mode & 0o111 else 0o644)


def _materialize(directory):
    """Copy-on-write one trusted base directory, never follow it for writes."""
    if directory.is_symlink():
        source = directory.resolve(strict=True)
        if not source.is_dir():
            raise ValueError(f"Overlay directory conflicts with installed file: {directory.name}")
        directory.unlink()
        directory.mkdir()
        for child in source.iterdir():
            (directory / child.name).symlink_to(child, target_is_directory=child.is_dir())
    else:
        directory.mkdir(exist_ok=True)


def overlay_tree(base, overlay, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for child in base.iterdir():
        if child.name in (".git", "runs", "__pycache__"):
            continue
        (destination / child.name).symlink_to(child, target_is_directory=child.is_dir())
    (destination / "runs").mkdir()
    if overlay is None:
        return
    for source in sorted(overlay.rglob("*")):
        relative = source.relative_to(overlay)
        target = destination / relative
        parent = destination
        for part in relative.parts[:-1]:
            parent = parent / part
            _materialize(parent)
        if source.is_dir():
            _materialize(target)
        else:
            if target.is_symlink() or target.is_file():
                target.unlink()
            shutil.copyfile(source, target)
            target.chmod(source.stat().st_mode & 0o777)


def prepare_project(archive, work, base):
    project_dir = work / "project"
    if archive is not None:
        extract_project(archive, project_dir)
    else:
        project_dir.mkdir(parents=True, exist_ok=False)
    manifest_file = project_dir / "project.json"
    manifest = (json_loads(manifest_file.read_bytes()) if manifest_file.exists()
                else {"schema": "isaac-healthcare-project/v2"})
    checked(manifest, schema("project"), "project")
    overlay = project_dir / "overlay"
    if overlay.exists() and not overlay.is_dir():
        raise ValueError("Project overlay must be a directory")
    effective = work / "sdk"
    overlay_tree(base, overlay if overlay.exists() else None, effective)
    for marker in ("DESIGN.md", "common", "engine"):
        if not (effective / marker).exists():
            raise ValueError(f"Effective SDK root is missing {marker}")
    python_paths = []
    # All source packages share the installed dependency environment. Discovery
    # follows package directories, not workflow names or accepted fixture hashes.
    for parent in (effective, effective / "tasks", effective / "tools"):
        if parent.is_dir():
            for child in sorted(parent.iterdir()):
                if child.is_dir() and any(item.is_dir() and item.name.startswith("i4h_") for item in child.iterdir()):
                    python_paths.append(str(child))
    python_paths.extend(str(contained_path(project_dir, value, directory=True))
                        for value in manifest.get("python_paths", []))
    asset_root = manifest.get("asset_root")
    if asset_root is not None:
        asset_root = str(contained_path(project_dir, asset_root, directory=True))
    inventory = {
        path.relative_to(project_dir).as_posix(): {"sha256": digest(path), "size_bytes": path.stat().st_size}
        for path in sorted(project_dir.rglob("*")) if path.is_file()
    }
    return {"effective_root": str(effective), "project_dir": str(project_dir),
            "python_paths": python_paths, "asset_root": asset_root,
            "manifest": manifest, "inventory": inventory}


def apply_project_defaults(values, context):
    result = dict(values)
    manifest = context["manifest"]
    result["workflow"] = result["workflow"] or manifest.get("default_workflow")
    result["mode"] = result["mode"] or manifest.get("default_mode")
    for name in ("checkpoint", "dataset", "patient_twin"):
        if result.get(name) is not None:
            result[name] = str(contained_path(Path(context["project_dir"]), result[name]))
    return result
