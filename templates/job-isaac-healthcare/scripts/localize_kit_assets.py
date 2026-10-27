"""Select the verified local Isaac mirror without changing simulation code."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path("/opt/i4h/third_party/IsaacLab-ffff603")
ASSET_ROOT = Path("/opt/i4h-assets/v0.9.0-7cf86a1")
REMOTE = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0"
SETTING = r'^(persistent\.isaac\.asset_root\.(?:default|cloud|nvidia) = )"{value}"$'


def localize(root=ROOT, asset_root=ASSET_ROOT):
    kit = root / "apps/isaaclab.python.kit"
    receipt_path = asset_root / "kit-localization.json"
    local = str(asset_root / "external/Isaac/6.0")
    before = kit.read_bytes()
    after, count = re.subn(
        SETTING.format(value=re.escape(REMOTE)),
        lambda match: match.group(1) + json.dumps(local),
        before.decode(), flags=re.MULTILINE,
    )
    original_sha = hashlib.sha256(before).hexdigest()
    if count == 0:
        # Prove current bytes and the reversible original source. Merely
        # finding a local path is not an inherited compatibility proof.
        previous = json.loads(receipt_path.read_bytes())
        original, restored = re.subn(
            SETTING.format(value=re.escape(local)),
            lambda match: match.group(1) + json.dumps(REMOTE),
            before.decode(), flags=re.MULTILINE,
        )
        if (restored != 3 or previous["sha256"] != hashlib.sha256(before).hexdigest()
                or previous["local_asset_root"] != local or previous["source_asset_root"] != REMOTE
                or previous["source_sha256"] != hashlib.sha256(original.encode()).hexdigest()):
            raise RuntimeError("Inherited IsaacLab localization differs from its exact source proof")
        original_sha = previous["source_sha256"]
    elif count != 3:
        raise RuntimeError("Pinned IsaacLab asset-root configuration changed")
    if after.encode() != before:
        kit.write_bytes(after.encode())
    receipt = {
        "file": "apps/isaaclab.python.kit", "source_sha256": original_sha,
        "before_sha256": hashlib.sha256(before).hexdigest(),
        "sha256": hashlib.sha256(kit.read_bytes()).hexdigest(),
        "source_asset_root": REMOTE, "local_asset_root": local,
        "already_localized": count == 0,
        "changes": "Only default/cloud/nvidia asset-root settings; physics and control code unchanged",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    localize()
