"""Refresh portable example-validation schemas from a committed platform checkout."""

import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-repository", required=True, type=Path)
    args = parser.parse_args()
    repo = args.platform_repository.resolve()
    paths = [f"k8s-inference/catalog/runtime/schema/{model}-workflow-request.schema.json"
             for model in ("amber", "lammps", "namd")]
    if subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=repo).strip():
        raise ValueError("Commit the exact native schemas before publishing their client projection")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    value = {"source": "nebius-solutions-library k8s-inference/catalog/runtime/schema; contract evidence, not runtime/customer qualification",
             "source_commit": commit,
             "schemas": {model: json.loads((repo / path).read_text())
                         for model, path in zip(("amber", "lammps", "namd"), paths)}}
    target = Path(__file__).with_name("native-md-contracts.json")
    target.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"source_commit": commit, "models": list(value["schemas"])}))


if __name__ == "__main__":
    main()
