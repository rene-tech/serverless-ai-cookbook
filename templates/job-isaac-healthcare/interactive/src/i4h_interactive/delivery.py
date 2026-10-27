"""Full-byte output delivery to two already-authorized immutable object targets."""

import hashlib
import json
import tarfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def put(url, path, media_type):
    if urlsplit(url).scheme != "https":
        raise ValueError("an App-authorized HTTPS output target is required")
    with path.open("rb") as stream:
        response = httpx.put(
            url,
            content=iter(lambda: stream.read(4 * 1024 * 1024), b""),
            headers={
                "Content-Length": str(path.stat().st_size),
                "Content-Type": media_type,
                "X-FS2-Artifact-SHA256": sha(path),
            },
            timeout=60,
            follow_redirects=False,
        )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError("interactive output delivery failed; do not replay science")


def deliver(root, sid, output, *, data_root=None):
    root = Path(root)
    files = {}
    data = Path(data_root) if data_root is not None else root / "output"
    for path in sorted(data.rglob("*")):
        relative = path.relative_to(data)
        # Kit caches and internal project context are not scientific artifacts.
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError("scientific output may not escape its session")
        if path.is_file():
            files[relative.as_posix()] = {
                "sha256": sha(path),
                "size_bytes": path.stat().st_size,
            }
    archive = root / "output.tar"
    with tarfile.open(archive, "x", format=tarfile.PAX_FORMAT) as tar:
        for name in files:
            tar.add(data / name, arcname=name, recursive=False)
    receipt = {
        "schema": "isaac-interactive-delivery/v1",
        "session_id": sid,
        "files": files,
        "archive": {"sha256": sha(archive), "size_bytes": archive.stat().st_size},
        "scientific_validation": "not_inferred_from_delivery",
    }
    path = root / "delivery.json"
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    put(output["archive_put_url"], archive, "application/x-tar")
    put(output["receipt_put_url"], path, "application/json")
    return receipt
