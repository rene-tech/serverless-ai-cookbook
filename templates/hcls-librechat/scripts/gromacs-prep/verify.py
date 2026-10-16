#!/usr/bin/env python3
"""Exercise real CPU GROMACS preparation; never submit or run a simulation.

The optional --tpr is read-only. All generated files go to a new output folder.
The fixture tests tooling, not physical validity or production MD performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


VERSION = "2026.4"
SOURCE_SHA256 = "58eda60979b124fcf9dff8b1b63cedfbc72fdb36d99e921dc1bdc310571098b6"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_dump(path: Path) -> dict:
    """Hash all dumped physics except the filename header and intended nsteps."""
    digest = hashlib.sha256()
    parameters = {}
    with path.open() as stream:
        for line in stream:
            match = re.match(r"\s*(nsteps|dt|init-step|tinit|natoms)\s*=\s*(\S+)", line)
            if match:
                key, value = match.groups()
                parameters[key] = float(value) if key in {"dt", "tinit"} else int(value)
                if key == "nsteps":
                    continue
            if line.rstrip().endswith(".tpr:"):
                continue
            digest.update(line.encode())
    return {"parameters": parameters, "physics_sha256_except_nsteps": digest.hexdigest()}


def verify(gmx: str, output: Path, source_tpr: Path | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    commands = []
    environment = {**os.environ, "GMX_MAXBACKUP": "0", "LC_ALL": "C"}

    def command(name: str, args: list[str], *, succeeds: bool = True) -> Path:
        stdout = output / f"{name}.stdout.txt"
        stderr = output / f"{name}.stderr.txt"
        with stdout.open("w") as out, stderr.open("w") as err:
            process = subprocess.run(
                [gmx, *args], cwd=output, env=environment,
                stdout=out, stderr=err, stdin=subprocess.DEVNULL, timeout=180,
            )
        commands.append({"args": args, "exit_code": process.returncode,
                         "stdout": stdout.name, "stderr": stderr.name})
        if (process.returncode == 0) != succeeds:
            raise RuntimeError(f"Unexpected GROMACS result for {name}: {process.returncode}; see {stderr}")
        return stdout

    version = command("version", ["--version"]).read_text()
    if not re.search(r"GROMACS version:\s+2026\.4(?:\s|$)", version):
        raise RuntimeError("The preparation binary is not pinned GROMACS 2026.4")
    if not re.search(r"GPU support:\s+disabled", version):
        raise RuntimeError("The preparation binary must be CPU-only")
    prefix_match = re.search(r"Data prefix:\s+(.+)", version)
    if not prefix_match:
        raise RuntimeError("GROMACS did not expose its force-field data prefix")
    prefix = Path(prefix_match.group(1).strip())
    if (prefix / "SOURCE-SHA256").read_text().strip() != SOURCE_SHA256:
        raise RuntimeError("Unrecognized GROMACS source identity")
    shutil.copyfile(prefix / "share/gromacs/top/spc216.gro", output / "water.gro")
    (output / "water.top").write_text(
        '#include "oplsaa.ff/forcefield.itp"\n'
        '#include "oplsaa.ff/spc.itp"\n\n'
        "[ system ]\nCPU preparation compatibility fixture\n\n[ molecules ]\nSOL 216\n"
    )
    (output / "water.mdp").write_text(
        "integrator = md\ndt = 0.002\nnsteps = 500000\n"
        "cutoff-scheme = Verlet\nnstlist = 20\nrlist = 0.8\n"
        "coulombtype = PME\nrcoulomb = 0.8\nvdwtype = Cut-off\nrvdw = 0.8\n"
        "constraints = h-bonds\nconstraint-algorithm = lincs\npbc = xyz\n"
        "tcoupl = v-rescale\ntc-grps = System\ntau-t = 1.0\nref-t = 300\n"
        "pcoupl = no\ngen-vel = yes\ngen-temp = 300\ngen-seed = 16102026\n"
        "nstxout = 0\nnstvout = 0\nnstfout = 0\nnstenergy = 500\n"
        "nstlog = 500\nnstxout-compressed = 500\n"
    )
    source_hashes = {name: sha256(output / name) for name in ("water.gro", "water.top", "water.mdp")}
    command("grompp", ["grompp", "-f", "water.mdp", "-c", "water.gro", "-p", "water.top",
                       "-o", "original.tpr", "-pp", "processed.top", "-po", "effective.mdp"])

    def conversion(label: str, original: Path, steps: int) -> dict:
        before = sha256(original)
        baseline = inspect_dump(command(f"{label}-before", ["dump", "-s", str(original)]))
        converted = output / f"{label}-duration-only.tpr"
        command(f"{label}-convert", ["convert-tpr", "-s", str(original), "-nsteps", str(steps), "-o", str(converted)])
        after = inspect_dump(command(f"{label}-after", ["dump", "-s", str(converted)]))
        if sha256(original) != before:
            raise RuntimeError("Original TPR changed")
        if after["parameters"]["nsteps"] != steps:
            raise RuntimeError("Converted TPR has the wrong step count")
        if baseline["physics_sha256_except_nsteps"] != after["physics_sha256_except_nsteps"]:
            raise RuntimeError("TPR conversion changed dumped physics beyond nsteps")
        command(f"{label}-check", ["check", "-s1", str(converted), "-s2", str(converted)])
        command(f"{label}-editconf", ["editconf", "-f", str(converted), "-o", f"{label}-extracted.gro"])
        atom_count = int((output / f"{label}-extracted.gro").read_text().splitlines()[1])
        if atom_count != baseline["parameters"]["natoms"]:
            raise RuntimeError("Coordinate extraction changed the atom count")
        return {"input_sha256": before, "output_sha256": sha256(converted),
                "before": baseline, "after": after, "original_unchanged": True,
                "physics_except_nsteps_unchanged": True, "extracted_atoms": atom_count,
                "structural_repair_claimed": False}

    fixture = conversion("fixture", output / "original.tpr", 5000000)
    if fixture["extracted_atoms"] != 648 or fixture["before"]["parameters"]["nsteps"] != 500000:
        raise RuntimeError("Fixture construction is not the intended 216-water system")
    command("missing-source", ["grompp", "-f", "water.mdp", "-c", "water.gro",
                               "-p", "missing.top", "-o", "must-not-exist.tpr"], succeeds=False)
    if (output / "must-not-exist.tpr").exists():
        raise RuntimeError("Missing topology unexpectedly produced a TPR")
    for name, expected in source_hashes.items():
        if sha256(output / name) != expected:
            raise RuntimeError(f"Fixture source changed: {name}")
    report = {"schema": "gromacs-preparation-acceptance/v1", "version": VERSION,
              "source_sha256": SOURCE_SHA256, "fixture": fixture,
              "missing_source_rejected": True, "simulation_executed": False,
              "qualification": "CPU preparation only; not scientific validation or MD performance",
              "source_hashes": source_hashes, "commands": commands}
    if source_tpr is not None:
        # The explicitly requested 10 ns demonstration has dt=0.002 ps.
        supplied_dump = inspect_dump(command("supplied-inspect", ["dump", "-s", str(source_tpr)]))
        dt = supplied_dump["parameters"]["dt"]
        steps = round(10000 / dt)
        if abs(steps * dt - 10000) > 1e-8:
            raise RuntimeError("10 ns is not exactly representable by supplied dt")
        report["supplied_input"] = conversion("supplied", source_tpr, steps)
    (output / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gmx", default=shutil.which("gmx") or "/opt/gromacs-prep/2026.4/bin/gmx")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tpr", type=Path, help="Optional read-only TPR for an additional 10 ns duration-only conversion")
    args = parser.parse_args()
    result = verify(args.gmx, args.output.resolve(), args.tpr.resolve() if args.tpr else None)
    print(json.dumps({"passed": True, "version": VERSION, "fixture_atoms": result["fixture"]["extracted_atoms"],
                      "supplied_input_checked": "supplied_input" in result, "simulation_executed": False,
                      "report": str(args.output.resolve() / "acceptance.json")}))
