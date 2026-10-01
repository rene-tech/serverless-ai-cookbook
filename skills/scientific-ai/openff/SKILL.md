---
name: openff
description: Prepare small-molecule ligands with OpenFF Sage, CPU AM1-BCC and GROMACS export. Use for force-field selection, stereospecific ligand parameterization and charge/export checks; not protein preparation or MD execution.
license: Apache-2.0
---

# OpenFF ligand preparation

This is a CPU preparation workflow, not a GPU model App. A skill is instructions,
not a software installation or proof that a customer's runtime has OpenFF.
The shared Scientific AI workbench release packages its CPU runtime at
`/opt/openff/bin/python`. External MCP clients must supply that runtime themselves.
Use the installed environment; do not install or repair
packages inside a customer's chat. Missing dependencies are a concrete blocker,
not a reason to leave a turn indefinitely thinking.

## Match the request

- **Recommendation:** read [force-field selection](../gromacs/references/ligand-parameterization.md),
  explain compatibility and one next step. Do not execute, invent code, or infer
  atom/stereocentre counts from visual inspection of SMILES.
- **Parameterization:** preserve the exact chemical identity, stereochemistry,
  protonation/formal charge, input conformer when supplied, and requested method.
  Undefined stereochemistry or an unresolved chemical choice requires a question.
  First run `/opt/openff/bin/python /opt/bionemo/prepare-openff.py --inspect-identity --smiles 'EXACT_INPUT'`.
  This read-only probe computes isomeric SMILES and CIP labels without creating
  files, assigning charges or choosing an isomer. Ask using those computed choices;
  never label @/@@ as R/S from memory or manually rewrite the returned SMILES.
  The preparation helper rejects undefined stereo; do not offer it as a valid route.
- **MD simulation:** parameterization is only one preparation stage. Hand the
  resulting files and provenance to the selected engine skill after checking
  protein/lipid/water compatibility. Never call a ligand bundle MD-ready.

Sage is the OpenFF **2.x** family; Parsley is **1.x**. Pin an installed `.offxml`
version and its digest. AM1-BCC via RDKit/AmberTools runs on CPUs. Do not silently
replace it with NAGL, RESP or another charge model. Parameter coverage and a finite
energy are checks, not proof of molecule-specific predictive accuracy.

## Hosted workbench path

1. Check once for `/opt/openff/bin/python` and the packaged
   `/opt/bionemo/prepare-openff.py`. If absent, report that precise dependency.
   Do not search arbitrary temporary environments or install conda/pip packages.
2. Read the helper's `--help`. For a **SMILES-only standalone ligand** request,
   run it with `--smiles`, an explicit `--force-field openff-2.2.1.offxml` (or the
   customer's selected installed Sage version), and a fresh `--output` directory.
   Pass the SMILES as one correctly quoted argument, never rewrite stereochemistry.
   This helper creates a conformer; it is not a supplied-pose preservation route.
3. Follow the existing execution ID to its terminal status. AM1-BCC may take
   minutes on CPUs. Report that phase truthfully; do not launch a second charge
   calculation while the first runs. Inspect nested status and exit code.
4. Read `preparation.json` and `manifest.json`; verify actual files and hashes.
   A failed export means incomplete work even if charges were calculated.
   `charges.json` and `charged-ligand.sdf` preserve the expensive charge result
   if a later step fails. Diagnose the failed stage rather than blindly rerunning.
5. Deliver the real `.top`, `.gro`, charged structure, force-field definition
   and provenance. State the exact version, charge sum and measured checks.
   Keep the handoff concise: link the output directory, name the method and
   version, formal charge/charge sum, verified checks and limitations. Leave
   the full numeric inventory in the provenance files; do not rephrase box
   side lengths as a volume or add unrequested scientific conclusions.

The helper's GROMACS box is **artificial, empty and padded by 1 nm** for export.
It is not a solvated simulation box or a recommended receptor protocol. The CPU
OpenMM single-point check is not a GROMACS energy-equivalence test. The helper
does **not** perform `grompp`, protein/membrane assembly, solvation, equilibration
or MD. Never claim those have passed. SDF and GRO coordinates may differ by the
documented translation into the export box, not by molecular identity.

## When a different preparation route is needed

For supplied poses, mixtures, unusual elements, alternative charge methods or
protein-ligand systems, consult the installed Toolkit/Interchange documentation
and preserve the requested protocol. Do not silently funnel them into the
SMILES-only helper. Before MD, validate atom identity/order, bonded and nonbonded
parameters, exclusions, units and 1–4 scaling. Preprocess with the target engine
and compare matched-coordinate energies/forces where supported. Mixing a Sage
ligand with arbitrary CHARMM or AMBER parameters is not automatically valid.

For a reproducible operator setup see [the environment specification](environment.yml).
Workbench builds use its fully resolved, SHA-256-pinned Linux package lock in
`templates/hcls-librechat/openff/conda-linux-64.lock`. Older images and external
clients may not include this runtime, so check the interpreter before execution.
Do not provision it from a user's scientific task without an explicit setup request.

## Primary documentation

- [Official installation and coordinated dependencies](https://docs.openforcefield.org/en/latest/install.html)
- [Sage-to-GROMACS/Amber export and validation example](https://docs.openforcefield.org/en/latest/examples/openforcefield/openff-toolkit/using_smirnoff_in_amber_or_gromacs/export_with_interchange.html)
- [Interchange export limitations](https://docs.openforcefield.org/projects/interchange/en/stable/using/edges.html)
- [Toolkit API](https://docs.openforcefield.org/projects/toolkit/en/stable/api/generated/openff.toolkit.topology.Molecule.html)
