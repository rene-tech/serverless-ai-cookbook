"""Apply the reviewed camera-control fix to the pinned upstream source."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path("/opt/i4h")
PACKAGE = Path("/opt/isaac-healthcare")
PATCH = PACKAGE / "patches/soarm-camera-disable.patch"
FILES = (
    "arena/i4h_arena/scenes/soarm_scissors.py",
    "arena/i4h_arena/embodiments/so_arm.py",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


subprocess.run(["git", "-C", str(ROOT), "apply", "--check", str(PATCH)], check=True)
before = {path: sha(ROOT / path) for path in FILES}
subprocess.run(["git", "-C", str(ROOT), "apply", str(PATCH)], check=True)
(PACKAGE / "upstream-patches.json").write_text(
    json.dumps(
        {
            "schema": "isaac-healthcare-upstream-patches/v1",
            "patches": [
                {
                    "id": "soarm-camera-disable-v1",
                    "patch": PATCH.name,
                    "patch_sha256": sha(PATCH),
                    "reason": "Honor explicit camera disable in the SOARM scene and its observation terms",
                    "files": [
                        {
                            "path": path,
                            "source_sha256": before[path],
                            "sha256": sha(ROOT / path),
                        }
                        for path in FILES
                    ],
                }
            ],
        },
        indent=2,
    )
    + "\n"
)
