"""Restore exact provider support files in a private directory, then exec transfer."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile


def require(value, message):
    if not value:
        raise ValueError(message)


def bounded_bytes(path, size):
    require(type(size) is int and size > 0, "Invalid declared byte count")
    with Path(path).open("rb") as source:
        value = source.read(size + 1)
    require(len(value) == size, "Support payload size differs")
    return value


def relative_name(name):
    require(isinstance(name, str) and name and "\\" not in name and "\0" not in name,
            "Malformed support path")
    path = PurePosixPath(name)
    require(not path.is_absolute() and len(path.parts) == 1 and name not in (".", "..")
            and path.as_posix() == name, "Support files require plain relative names")
    return name


def restore(manifest_path, payload_path):
    manifest = json.loads(Path(manifest_path).read_bytes())
    require(set(manifest) == {"schema", "root", "files", "archive", "compressed", "source_identity"}
            and manifest["schema"] == "isaac-provider-support/v1", "Unknown support manifest")
    root = Path(manifest["root"])
    require(root.parent == Path("/tmp") and re.fullmatch(r"isaac-provider-code-[0-9a-f]{64}", root.name),
            "Support root is not an isolated task directory")
    require(root.name == "isaac-provider-code-" + manifest["source_identity"], "Support identity differs")
    files = manifest["files"]
    require(isinstance(files, dict) and {"command.json", "transfer.py", "run_bundle.py"} <= files.keys(),
            "Required support files are missing")
    for name, row in files.items():
        relative_name(name)
        require(set(row) == {"size_bytes", "sha256", "mode"} and type(row["size_bytes"]) is int
                and row["size_bytes"] > 0 and row["mode"] == 0o600
                and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "Invalid support file declaration")
    packed = bounded_bytes(payload_path, manifest["compressed"]["size_bytes"])
    require(hashlib.sha256(packed).hexdigest() == manifest["compressed"]["sha256"],
            "Compressed support payload hash differs")
    maximum = manifest["archive"]["size_bytes"]
    require(type(maximum) is int and maximum > 0, "Invalid archive byte count")
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as source:
        raw = source.read(maximum + 1)
    require(len(raw) == maximum and hashlib.sha256(raw).hexdigest() == manifest["archive"]["sha256"],
            "Support archive size/hash differs")
    # Validate every member before creating files. No extractall, links, overwrite,
    # reused directory or writes into the provider's injected mount are permitted.
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        members = archive.getmembers()
        names = [relative_name(member.name) for member in members]
        require(len(names) == len(set(names)) and set(names) == set(files), "Support archive members differ")
        decoded = {}
        for member in members:
            row = files[member.name]
            require(member.isfile() and not member.sparse and member.size == row["size_bytes"]
                    and member.mode == row["mode"], "Support member type/size/mode differs")
            source = archive.extractfile(member)
            require(source is not None, "Support member has no data")
            with source:
                value = source.read(member.size + 1)
            require(len(value) == member.size and hashlib.sha256(value).hexdigest() == row["sha256"],
                    "Support file hash differs")
            decoded[member.name] = value
    os.mkdir(root, 0o700)  # Existing or uncertain startup is a hard stop, never replay.
    os.chmod(root, 0o700)
    require(root.stat().st_uid == os.geteuid(), "Support directory ownership differs")
    for name, value in decoded.items():
        path = root / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(value)
            target.flush()
            os.fsync(target.fileno())
            os.fchmod(target.fileno(), files[name]["mode"])
        observed = path.lstat()
        require(stat.S_ISREG(observed.st_mode) and observed.st_uid == os.geteuid()
                and stat.S_IMODE(observed.st_mode) == files[name]["mode"]
                and hashlib.sha256(path.read_bytes()).hexdigest() == files[name]["sha256"],
                "Restored support file integrity differs")
    return root, manifest


def launch(manifest_path, payload_path, transfer_path):
    root, manifest = restore(manifest_path, payload_path)
    transfer_path = Path(transfer_path).resolve(strict=True)
    configuration = json.loads(transfer_path.read_bytes())
    require(configuration["command_sha256"] == hashlib.sha256((root / "command.json").read_bytes()).hexdigest(),
            "Restored command differs from the scoped transfer configuration")
    print(json.dumps({"event": "isaac-provider-support-restored", "uid": os.geteuid(),
                      "files": len(manifest["files"]), "source_identity": manifest["source_identity"],
                      "compressed_sha256": manifest["compressed"]["sha256"]}), flush=True)
    os.execv(sys.executable, [sys.executable, "-I", str(root / "transfer.py"),
                             "--config", str(transfer_path), "--command", str(root / "command.json")])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "payload", "transfer"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    launch(args.manifest, args.payload, args.transfer)
