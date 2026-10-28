"""Verify actual isolated Arena/transport imports; never add a source PYTHONPATH."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(package, transport=False):
    package = Path(package)
    if not sys.flags.isolated:
        raise ValueError("Use the installed interpreter with -I")
    record = json.loads((package / "graceful-shutdown-provenance.json").read_bytes())
    if record["schema"] != "isaac-interactive-graceful-shutdown/v1":
        raise ValueError("Unknown shutdown provenance")
    if sha(Path(record["patch"])) != record["patch_sha256"]:
        raise ValueError("Shutdown patch provenance differs")
    if transport:
        from i4h_interactive import workflow

        source = package / "src/i4h_interactive/workflow.py"
        loaded = Path(workflow.__file__).resolve()
        if loaded == source.resolve() or sha(loaded) != sha(source):
            raise ValueError(
                "Installed transport workflow differs from packaged source"
            )
        module = "i4h_interactive.workflow"
    else:
        from i4h_arena import runner

        loaded = Path(runner.__file__).resolve()
        if (
            loaded != Path(record["source"]).resolve()
            or sha(loaded) != record["sha256"]
        ):
            raise ValueError("Actual Arena import differs from patched runner")
        module = "i4h_arena.runner"
    return {
        "interpreter": sys.executable,
        "isolated": bool(sys.flags.isolated),
        "module": module,
        "loaded_path": str(loaded),
        "sha256": sha(loaded),
        "provenance": record,
        "gpu_execution": "not_tested_by_this_cpu_import_gate",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path("/opt/interactive"))
    parser.add_argument("--transport", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.package, args.transport), sort_keys=True))
