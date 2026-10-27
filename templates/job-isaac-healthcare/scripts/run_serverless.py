"""Use local POSIX scratch for HDF5, then publish closed files to a bucket mount."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from isaac_healthcare_runtime.contract import digest
from isaac_healthcare_runtime.runtime import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    if args.output_prefix.exists():
        raise ValueError(
            "Output prefix already exists; choose a new run prefix without replacing earlier results"
        )
    with tempfile.TemporaryDirectory(prefix="isaac-healthcare-") as scratch:
        output = Path(scratch)
        run(args.input, json.loads(args.parameters.read_bytes()), output)
        args.output_prefix.mkdir(parents=True, exist_ok=False)
        manifest = {}
        for name in ("result.json", "simulation.tar"):
            source, destination = output / name, args.output_prefix / name
            shutil.copyfile(source, destination)
            expected = digest(source)
            if digest(destination) != expected:
                raise RuntimeError(
                    "Published result differs from the completed local file"
                )
            manifest[name] = {"sha256": expected, "size_bytes": source.stat().st_size}
        # Whole-file publication; no append, truncate, rename or chmod on object storage.
        (args.output_prefix / "completion.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    print(
        json.dumps({"output_prefix": str(args.output_prefix), "delivery": "verified"})
    )


if __name__ == "__main__":
    main()
