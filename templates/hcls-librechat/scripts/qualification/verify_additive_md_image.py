"""Prove protected client/skill bytes survived an additive MD analysis layer."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


# Run system Python, not an application interpreter, with no network or mounts.
# The app supervisor is never started and no customer bucket is attached.
INVENTORY = r'''
import hashlib, json, os, stat
from pathlib import Path
roots = ["/opt/scientific-client", "/opt/clinical-client", "/opt/clawbio-venv",
         "/opt/clawbio", "/opt/bionemo", "/opt/hcls-librechat",
         "/app/skill", "/app/librechat.yaml", "/tmp/test-skills-installed.cjs"]
rows = {}
for name in roots:
    root = Path(name)
    if not root.exists():
        raise RuntimeError("Protected path is missing: " + name)
    for path in [root, *sorted(root.rglob("*"))] if root.is_dir() else [root]:
        info = path.lstat()
        row = {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}
        if path.is_symlink():
            row.update(kind="symlink", target=os.readlink(path))
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    digest.update(chunk)
            row.update(kind="file", bytes=info.st_size, sha256=digest.hexdigest())
        elif path.is_dir():
            row.update(kind="directory")
        else:
            raise RuntimeError("Unexpected protected filesystem entry: " + str(path))
        rows[str(path)] = row
print(json.dumps(rows, sort_keys=True))
'''


def inspect(image):
    return json.loads(subprocess.check_output(["docker", "image", "inspect", image]))[0]


def inventory(image):
    return json.loads(subprocess.check_output([
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--entrypoint", "/usr/bin/python3", image, "-B", "-c", INVENTORY,
    ]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    before, after = inspect(args.base), inspect(args.candidate)
    old_layers, new_layers = before["RootFS"]["Layers"], after["RootFS"]["Layers"]
    if new_layers[:len(old_layers)] != old_layers:
        raise RuntimeError("Candidate does not retain the exact base layers")
    # Labels may describe the new layer. No behavior-changing image config may differ.
    config_before = {k: v for k, v in before["Config"].items() if k != "Labels"}
    config_after = {k: v for k, v in after["Config"].items() if k != "Labels"}
    if config_before != config_after:
        raise RuntimeError("Candidate changed application image configuration")
    old, new = inventory(args.base), inventory(args.candidate)
    for name, data in (("base-files.json", old), ("candidate-files.json", new)):
        (args.output / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    changed = sorted(name for name in old.keys() | new.keys() if old.get(name) != new.get(name))
    allowed = ["/app/skill/files.sha256.json", "/app/skill/scientific-batch/references/native-md.md"]
    if changed != allowed:
        raise RuntimeError("Unexpected protected file change: " + repr(changed))
    receipt = {
        "status": "passed", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "base": args.base, "candidate": args.candidate,
        "base_id": before["Id"], "candidate_id": after["Id"],
        "base_layers_preserved": len(old_layers), "additive_layers": len(new_layers) - len(old_layers),
        "application_config_unchanged": True,
        "protected_entries": len(old), "intentional_changed_entries": changed,
        "inventory_sha256": {name: hashlib.sha256((args.output / name).read_bytes()).hexdigest()
                             for name in ("base-files.json", "candidate-files.json")},
        "api_client_unchanged": True, "extension_skills_unchanged": True,
        "customer_ready": False,
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
