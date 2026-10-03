"""Record the exact additive client overlay, without claiming live qualification."""

import argparse
import hashlib
import json
from pathlib import Path
import re


def record(overlay: Path, revision: str, base: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Provide the exact committed client revision")
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", base):
        raise ValueError("Provide the immutable current workbench base image")
    root = overlay / "app/skill"
    manifest = json.loads((root / "manifest.json").read_text())
    names = (
        "app/skill/manifest.json",
        "app/skill/files.sha256.json",
        "opt/bionemo/invoke-scientific-batch.py",
        "opt/bionemo/native_md_artifacts.py",
        "opt/bionemo/scientific_verified_results.py",
        "opt/bionemo/report-native-md.py",
    )
    value = {
        "schema": "scientific-ai/gromacs-client-release/v1",
        "source_repository": "https://github.com/rene-tech/serverless-ai-cookbook",
        "source_revision": revision,
        "base_image": base,
        "skills_version": manifest["version"],
        "files_sha256": {
            name: hashlib.sha256((overlay / name).read_bytes()).hexdigest()
            for name in names
        },
        "backend_contract": json.loads(
            (root / "gromacs/references/mpi-contract-source.json").read_text()
        ),
        "qualification": "Source/image provenance only; live API/MCP/GPU acceptance is separate.",
    }
    target = overlay / "opt/hcls-librechat/gromacs-mpi-release.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as handle:
        handle.write(json.dumps(value, indent=2) + "\n")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    print(record(args.overlay, args.revision, args.base))


if __name__ == "__main__":
    main()
