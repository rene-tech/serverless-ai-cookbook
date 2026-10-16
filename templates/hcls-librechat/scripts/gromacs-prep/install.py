#!/usr/bin/env python3
"""Add or roll back the CPU preparation command without restarting LibreChat.

Stage the immutable prefix from the qualified image, verify the transfer digest,
then run install. Rollback restores only this command; no workspace is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

VERSION = "2026.4"
SOURCE_SHA256 = "58eda60979b124fcf9dff8b1b63cedfbc72fdb36d99e921dc1bdc310571098b6"


def inventory(directory: Path) -> dict[str, str]:
    result = {}
    for path in sorted(directory.rglob("*")):
        name = str(path.relative_to(directory))
        if path.is_symlink():
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError(f"Prefix link escapes installation: {name}")
            result[name] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def install(source: Path, root: Path) -> dict:
    source = source.resolve(strict=True)
    root = root.resolve(strict=True)
    if (source / "SOURCE-SHA256").read_text().strip() != SOURCE_SHA256:
        raise ValueError("Unexpected GROMACS source digest")
    source_inventory = inventory(source)
    destination = root / f"opt/gromacs-prep/{VERSION}"
    command = root / "usr/local/bin/gmx"
    command.parent.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if inventory(destination) != source_inventory:
            raise ValueError("Existing immutable version differs; refusing to overwrite it")
    else:
        temporary = destination.with_name(f".install-{uuid.uuid4().hex}")
        shutil.copytree(source, temporary, symlinks=True)
        os.replace(temporary, destination)
    binary = destination / "bin/gmx"
    version = subprocess.run([str(binary), "--version"], check=True, capture_output=True, text=True).stdout
    if not re.search(r"GROMACS version:\s+2026\.4\b", version) or not re.search(r"GPU support:\s+disabled", version):
        raise ValueError("Installed command is not the qualified CPU build")
    if command.is_symlink() and command.resolve() == binary.resolve():
        return {"changed": False, "command": str(command), "version": VERSION}
    receipt_dir = destination.parent / "patches" / uuid.uuid4().hex
    receipt_dir.mkdir(parents=True)
    if command.is_symlink():
        previous = {"kind": "symlink", "target": os.readlink(command)}
    elif command.is_file():
        shutil.copy2(command, receipt_dir / "previous-gmx")
        previous = {"kind": "file", "sha256": hashlib.sha256(command.read_bytes()).hexdigest()}
    elif command.exists():
        raise ValueError("Existing gmx is not a file or link")
    else:
        previous = {"kind": "absent"}
    receipt = {"schema": "gromacs-preparation-patch/v1", "root": str(root),
               "command": str(command), "installed_target": str(binary), "previous": previous,
               "binary_sha256": source_inventory["bin/gmx"], "version": VERSION}
    receipt_path = receipt_dir / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    staged_link = command.with_name(f".gmx-{receipt_dir.name}")
    staged_link.symlink_to(binary)
    os.replace(staged_link, command)
    return {"changed": True, "receipt": str(receipt_path), "command": str(command), "version": VERSION}


def rollback(receipt_path: Path) -> dict:
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("schema") != "gromacs-preparation-patch/v1":
        raise ValueError("Unrecognized patch receipt")
    command = Path(receipt["root"]) / "usr/local/bin/gmx"
    if str(command) != receipt["command"] or not command.is_symlink() or os.readlink(command) != receipt["installed_target"]:
        raise ValueError("Command changed since this patch; refusing to replace it")
    previous = receipt["previous"]
    staged = command.with_name(f".gmx-rollback-{uuid.uuid4().hex}")
    if previous["kind"] == "absent":
        command.unlink()
    elif previous["kind"] == "symlink":
        staged.symlink_to(previous["target"])
        os.replace(staged, command)
    elif previous["kind"] == "file":
        backup = receipt_path.parent / "previous-gmx"
        if hashlib.sha256(backup.read_bytes()).hexdigest() != previous["sha256"]:
            raise ValueError("Backup command changed")
        shutil.copy2(backup, staged)
        os.replace(staged, command)
    else:
        raise ValueError("Unrecognized previous command state")
    return {"rolled_back": True, "command": str(command), "prefix_retained": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    add = subcommands.add_parser("install")
    add.add_argument("--source", type=Path, required=True)
    add.add_argument("--root", type=Path, default=Path("/"), help="Installation root; override only for isolated tests")
    undo = subcommands.add_parser("rollback")
    undo.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.source, args.root) if args.action == "install" else rollback(args.receipt)))
