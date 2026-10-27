"""Select the pinned local Isaac asset mirror without changing simulation code."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path("/opt/i4h/third_party/IsaacLab-ffff603")
KIT = ROOT / "apps/isaaclab.python.kit"
ASSET_ROOT = Path("/opt/i4h-assets/v0.9.0-7cf86a1")
REMOTE = (
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0"
)
LOCAL = str(ASSET_ROOT / "external/Isaac/6.0")

before = KIT.read_bytes()
after, count = re.subn(
    r'^(persistent\.isaac\.asset_root\.(?:default|cloud|nvidia) = )"'
    + re.escape(REMOTE)
    + r'"$',
    lambda match: match.group(1) + json.dumps(LOCAL),
    before.decode(),
    flags=re.MULTILINE,
)
if count != 3:
    raise RuntimeError("Pinned IsaacLab asset-root configuration changed")
KIT.write_text(after)
(ASSET_ROOT / "kit-localization.json").write_text(
    json.dumps(
        {
            "file": "apps/isaaclab.python.kit",
            "source_sha256": hashlib.sha256(before).hexdigest(),
            "sha256": hashlib.sha256(KIT.read_bytes()).hexdigest(),
            "source_asset_root": REMOTE,
            "local_asset_root": LOCAL,
            "changes": "Only default/cloud/nvidia asset-root settings; physics and control code unchanged",
        },
        indent=2,
    )
    + "\n"
)
