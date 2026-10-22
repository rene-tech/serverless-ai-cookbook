#!/usr/bin/env python3
"""Create reproducible public solvated examples; never submits work or changes a protocol silently."""

import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

REVISION = "b399af4725573963b46d6c1083fdcf7a37615857"
BASE = f"https://raw.githubusercontent.com/openmm/openmm/{REVISION}/wrappers/python/"
SOURCES = {
    "alanine": {
        "alanine.prmtop": (
            "tests/systems/alanine-dipeptide-explicit.prmtop",
            "c45ad8bdcdfc62584add4093edde188f4ab986f831da6c11a83e017873592106",
        ),
        "alanine.inpcrd": (
            "tests/systems/alanine-dipeptide-explicit.inpcrd",
            "b2c167dc2be9aaba742ce85b44570a885c1ba1cb1d8ecddd29dab8878bb9b5e6",
        ),
    },
    "ionic": {
        "ionic.top": (
            "tests/systems/ionic.top",
            "394f995453dcc22eaa9f6a0eda326f9db72aa86753b2566b697e9972927152be",
        ),
        "ionic.gro": (
            "tests/systems/ionic.gro",
            "3c4db6cf0e2082972996aeb4af4710a9400246ee45a1cf2edb5aab7b36ea0031",
        ),
    },
    "protein": {
        "protein.pdb": (
            "openmm/app/data/test.pdb",
            "28063e62f8686dc0ec27c723a9d39bf29327874fcf4fd990090d22dc5f925470",
        ),
    },
}
SYSTEMS = {
    "alanine": {
        "format": "amber",
        "coordinates": "alanine.inpcrd",
        "topology": "alanine.prmtop",
    },
    "ionic": {"format": "gromacs", "coordinates": "ionic.gro", "topology": "ionic.top"},
    "protein": {
        "format": "pdb",
        "coordinates": "protein.pdb",
        "forcefields": ["amber99sb.xml", "tip3p.xml"],
    },
}


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = args.output / "inputs"
    inputs.mkdir()
    provenance = []
    for name, (relative, digest) in SOURCES[args.example].items():
        url = BASE + relative
        if args.cache and (args.cache / name).is_file():
            raw = (args.cache / name).read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=60) as response:
                raw = response.read()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Upstream bytes failed integrity verification: {name}")
        (inputs / name).write_bytes(raw)
        provenance.append(
            {"file": name, "url": url, "sha256": digest, "size_bytes": len(raw)}
        )
    with tarfile.open(args.output / "input.tar.gz", "w:gz") as archive:
        for source in sorted(inputs.iterdir()):
            item = archive.gettarinfo(str(source), arcname=source.name)
            item.uid = item.gid = item.mtime = 0
            item.uname = item.gname = ""
            with source.open("rb") as stream:
                archive.addfile(item, stream)
    phases = [
        {
            "id": "minimize",
            "kind": "minimize",
            "max_iterations": 500,
            "tolerance_kj_mol_nm": 10,
        },
        {
            "id": "equilibrate",
            "kind": "equilibrate",
            "steps": args.equilibration_steps,
            "pressure_bar": 1.0,
            "temperature_k": args.temperature,
            "report_interval": args.report_interval,
        },
        {
            "id": "production",
            "kind": "production",
            "steps": args.steps,
            "pressure_bar": 1.0,
            "temperature_k": args.temperature,
            "report_interval": args.report_interval,
            "checkpoint_interval_steps": args.segment_steps,
        },
    ]
    value = {
        "schema": "fs2-serve.nebius.ai/openmm-workflow-request/v1",
        "backend": args.backend,
        "random_seed": args.seed,
        "jobs": [
            {
                "id": args.example,
                "system": {
                    **SYSTEMS[args.example],
                    "nonbonded_method": "PME",
                    "nonbonded_cutoff_nm": 0.9,
                    "constraints": "HBonds",
                },
                "steps": phases,
            }
        ],
    }
    for name, data in (
        ("parameters.json", value),
        (
            "provenance.json",
            {
                "source_revision": REVISION,
                "files": provenance,
                "purpose": "Software qualification, not a converged scientific study",
                "protocol": "2 fs Langevin-middle, periodic PME, 300 K by default, 1 bar NPT",
            },
        ),
    ):
        (args.output / name).write_text(json.dumps(data, indent=2) + "\n")
    if args.starter_pack:
        case = f"molecular-dynamics/{args.example}"
        prefix = case + "/openmm"
        destination = args.output / prefix
        destination.mkdir(parents=True)
        for name in ("input.tar.gz", "parameters.json", "provenance.json"):
            shutil.copyfile(args.output / name, destination / name)
        template = {"entries": [{"name": "openmm-inputs", "semantic_type": "openmm-input-bundle/v1", "artifact": {"$file": prefix + "/input.tar.gz", "compression": "gzip", "media_type": "application/x-tar"}}]}
        recipe = {"recipes": [{"model_id": "openmm", "tool_name": "submit_openmm_workflow", "arguments": {"operation": "run-workflow", "parameters": value, "input_manifest": {"$manifest": prefix + "/input-manifest.template.json"}}}], "expected": {"description": "OpenMM public execution example; not converged sampling. Includes minimization and finite NPT equilibration/production."}}
        for name, data in ((prefix + "/input-manifest.template.json", template), (case + "/recipes.json", recipe)):
            (args.output / name).write_text(json.dumps(data, indent=2) + "\n")
        objects = [{"path": path.relative_to(args.output).as_posix(), "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(args.output.rglob("*")) if path.is_file()]
        (args.output / "manifest.json").write_text(json.dumps({"schema": "fs2-serve.nebius.ai/customer-starter-pack/v1", "version": "openmm-8.6.1-" + args.example, "objects": objects}, indent=2) + "\n")
    print(
        json.dumps(
            {
                "example": args.example,
                "backend": args.backend,
                "production_steps": args.steps,
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", choices=SOURCES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--starter-pack", action="store_true", help="Also emit a hash-bound pack for the existing run_starter_example client.")
    parser.add_argument("--backend", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--steps", type=int, default=50000)
    parser.add_argument("--equilibration-steps", type=int, default=5000)
    parser.add_argument("--segment-steps", type=int, default=25000)
    parser.add_argument("--report-interval", type=int, default=1000)
    parser.add_argument("--temperature", type=float, default=300)
    parser.add_argument("--seed", type=int, default=2026)
    main(parser.parse_args())
