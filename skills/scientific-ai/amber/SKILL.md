---
name: amber
description: Prepare, run, continue and analyze AMBER molecular-dynamics studies on Scientific AI using PMEMD CUDA/CPU and AmberTools. Use for native MDIN workflows, explicit or implicit solvent, independent replicas, alchemical windows, topology preparation and trajectory analysis; distinguish supported execution from demonstrated sampling or free-energy convergence.
license: Apache-2.0
---

# AMBER on Scientific AI

Read `scientific-gateway` and the [shared MD transport](../scientific-batch/references/native-md.md).
App ID: **amber**. This private runtime combines official PMEMD26 with pinned
AmberTools26; it is not an NVIDIA NIM. A skill does not grant model access or
establish qualification. Discover the App, current schema and supported runtime
before submitting. The deployment is for operator-approved academic use under
the confirmed AMBER agreement, not unrestricted redistribution of PMEMD.

## Choose and preserve the scientific protocol

Confirm the system, force field, solvent/ions, protonation, periodic box,
restraints, ensemble, temperature/pressure control, timestep, constraints,
duration, seeds and output cadence. Do not treat a predicted structure, docking
pose or unparameterized ligand as a ready MD system. LEaP warnings require
inspection, especially missing parameters, unusual residue charges and bad
contacts. A successful topology build is not equilibration.

PMEMD backends are `cuda-spfp`, `cuda-dpfp` and `cpu`. Precision is a scientific
and performance choice, not an interchangeable speed switch. Use published
evidence for the requested protocol/GPU; the initial sodium TI regression has
a retained SPFP temperature-tolerance exception, while its DPFP comparison
passes. Do not silently loosen tolerances or switch the customer's precision.

Each job is one native process using at most one GPU. Independent replicas or
lambda windows can queue concurrently; they are not coupled replica exchange,
MPI, multi-node execution or evidence of MPS support. AmberTools in this image
is the CPU-only conda-forge build. Do not promise GPU SANDER, QM/MM, PBSA or
every executable in the upstream suite through this App's current typed steps.

## Native input and typed submission

Discover `get_model_schema(model_id="amber", protocol="scientific-batch-v1")`.
Use operation `run-workflow`, tool `submit_amber_workflow`, input role
`amber-inputs` and semantic type `amber-input-bundle/v1`. Upload a complete
gzip-tar bundle of relative-path dependencies using the shared client, never
inline archive data or a LibreChat path as a remote artifact ID.

The [example parameters](examples/native-workflow.json) describe an ordered
workflow. They need the scientist's real native files; they are not a ready
physical system or recommended universal simulation length. Each job contains
ordered steps, with `input` relative to `directory`:

- `tleap`: native LEaP script, with explicit expected topology/coordinate files.
- `pmemd`: MDIN, `topology`, `coordinates`, optional restraint `reference`,
  backend and output stem. Set `task: minimization` for minimization; dynamics
  requires `expected_nsteps` equal to the actual MDIN `nstlim`.
- `cpptraj`: native trajectory-analysis script and optional topology.
- `parmed`: native ParmEd script with optional topology/coordinates.

Tool steps require nonempty `expected_outputs`. Scripts and scientific options
remain native; the platform does not rewrite MDIN, force fields or trajectories.
Use a distinct PMEMD output prefix per stage. The wrapper assigns `.mdout`,
`.rst7`, `.nc`, `.mdvel`, `.mden` and `.mdinfo` filenames; which files contain
output still depends on the native protocol and cadence.

## Continuation, storage and analysis

For continuation use the matching topology and completed restart coordinates,
velocities and cell, with appropriate native `irest`/`ntx` and restraint
reference. Do not regenerate velocities when continuing production. Check
native time, atom count and frame boundaries. Native restart does not promise
bitwise serialization of every stochastic thermostat state.

The current worker commits the full stopped workspace after successful stages.
An interrupted active stage retries from the preceding committed stage; it does
not resume an arbitrary partial `.rst7`. Split long production into explicit,
scientifically consistent stages if preemptible recovery is important. Choose
stage lengths with the scientist and account for checkpoint/export overhead.
GPU process snapshots are separate and require exact-image restore evidence;
neither native restart nor a registry-cached image proves snapshot acceleration.

Use `output_destination: customer-bucket` for the assigned tenant/user bucket.
Keep manifests, every trajectory segment, restart, energy/derivative output,
native log and input provenance. Estimate total output including checkpoints
against the actual bucket quota; requesting a larger workspace budget does not
enlarge storage. Retrieve and verify results before reporting success.

Report atom count, achieved steps/time, finite coordinates and energies,
temperature/pressure behavior, expected versus observed frames, warnings and
continuation consistency. Keep native ns/day separate from queue, preparation,
export and total turnaround time. Stability over a short run is not convergence.

For TI/FEP, require the actual transformation, topology/masks, lambda schedule,
soft-core settings, equilibration/production lengths, seeds and estimator.
Preserve derivative and cross-state energy data needed for the chosen analysis.
Analyze overlap, correlation/effective samples, uncertainty and convergence;
successfully running one window is not a binding-free-energy result. Never
translate unsupported AMBER methods to another engine without agreement.

See [official documentation and feature boundaries](references/sources.md).
