"""Select the immutable local asset tree, then call upstream's unchanged arena CLI."""

import os
import sys

from i4h_arena.assets import constants

local_root = (
    os.environ.get("I4H_ASSET_PATH", "/opt/i4h-assets/v0.9.0-7cf86a1/").rstrip("/")
    + "/"
)
original_root = constants.ASSET_PATH
for name, value in tuple(vars(constants).items()):
    if isinstance(value, str) and value.startswith(original_root):
        setattr(constants, name, local_root + value.removeprefix(original_root))

from i4h_arena.cli import main as arena_main


def main():
    # Keep upstream scientific arguments intact while using SimulationApp's
    # supported portable-root option for writable per-scenario Kit state.
    workflow_args = sys.argv[1:]
    if kit_root := os.environ.get("ISAAC_HEALTHCARE_KIT_ROOT"):
        sys.argv = [sys.argv[0], "--portable-root", kit_root]
    return arena_main(workflow_args)


if __name__ == "__main__":
    sys.exit(main())
