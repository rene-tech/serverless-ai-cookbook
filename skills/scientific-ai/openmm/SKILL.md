---
name: openmm
description: Prepare, submit, resume and analyze classical OpenMM molecular dynamics on Scientific AI, including solvated PDB/mmCIF, prepared Amber/GROMACS inputs, explicit equilibration/production and physical-state continuation.
license: Apache-2.0
---

# OpenMM on Scientific AI

Read `scientific-gateway`, then the [shared MD transport](../scientific-batch/references/native-md.md).
Discover App `openmm` with `get_model_schema`; use its exact typed
`submit_openmm_workflow` tool and `run-workflow` contract. The engine is
OpenMM 8.6.1, not an NVIDIA NIM. Skill installation does not establish live
qualification or access.

## Scientific protocol

Identify the topology, coordinate/particle order, protonation, force field,
water/ion model, periodic box, ensemble, timestep, constraints, duration and seed.
Do not infer ligand parameters from a structure or change a scientist's settings
to make a run pass. The typed App supports:

- PDB/mmCIF with OpenMM's bundled force-field XML names, optional hydrogen
  addition and explicit solvation. Supply compatible force-field/water choices.
- Prepared Amber PRMTOP + INPCRD/RST7, or GROMACS TOP + GRO with every include
  bundled. These inputs already carry their parameters.
- Ordered `minimize`, `equilibrate` and `production` phases; finite dynamics
  steps, Langevin-middle or Verlet, and optional isotropic NPT for periodic
  Langevin dynamics. Temperature/pressure changes are explicit phase choices.

Arbitrary Python, uploaded force-field scripts, custom serialized System or
Integrator, replica exchange and enhanced-sampling extensions are not exposed
by this App. Do not imply all OpenMM library features are supported.

`backend: cuda` is the default accelerated path; `backend: cpu` intentionally
selects CPU execution when scientifically appropriate. No failure silently
switches backend. Precision and hydrogen-mass repartitioning are explicit;
neither a larger timestep nor a short successful run establishes stability.

## Inputs, examples and durable execution

Use the live artifact contract: `openmm-inputs`, `openmm-input-bundle/v1`,
gzip `application/x-tar`. Bundle relative paths with the existing
`../gromacs/scripts/make-input-bundle.py`; never invent uploaded handles.
For a public demonstration, [make-example.py](scripts/make-example.py) downloads
hash-pinned upstream solvated `alanine`, `protein` or GROMACS `ionic` inputs and
creates `input.tar.gz`, `parameters.json` and provenance. It does not submit.
`--starter-pack` additionally creates an integrity-bound recipe compatible with
the existing `run_starter_example` tool, under `molecular-dynamics/<example>`.
Choose a new caller-owned directory and an explicit backend. Its short NPT
protocol is an execution example, not a converged experiment.

For a complete chat request, include submission, verified artifact recovery,
analysis and final report in a durable `scientific-workflow/v2` study. Use
`scientific-batch` for the current batch phase fields. The native file manifest
is `native-files.json`; the installed `native_md_preview.py` accepts it for a
timing report and final-coordinate preview without running another simulation.
Preserve the original operation, study directory and idempotency key.

## Recovery and results

Each closed segment publishes an acknowledged native checkpoint before the
next segment. Resume an interrupted operation through `resume_scientific_run`;
do not resubmit completed phases. Compatible binary checkpoints preserve
internal state, but compatibility depends on runtime, System/Integrator and
device. Cross-device portable State restores positions, velocities, box, time
and step count—not RNG history or a bitwise identical stochastic trajectory.
An explicit new operation may use `system.state` with matching topology/order;
this is not an identical-replay promise. Neither form is a process snapshot.

Verify segment boundaries, final steps, finite energies and every DCD trajectory
with its matching `structure.cif`. mmCIF is authoritative; PDB is provided only
where its atom names/size are representable. Original topology identifiers stay
in `openmm-output/prepared/topology.json`; blank PDB chain IDs receive valid
export IDs in mmCIF. Keep all trajectories, State XML, binary checkpoints,
state CSV, structures, logs and manifests. Report integration ns/day separately
from startup, queue, checkpoint publication and total elapsed time. Evaluate
equilibration, ensemble statistics and convergence independently.

For version/license details, read [official sources](references/sources.md).
