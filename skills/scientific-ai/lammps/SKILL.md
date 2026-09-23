---
name: lammps
description: Prepare, submit, resume and analyze native LAMMPS molecular or materials simulations on Scientific AI. Use for NVIDIA-packaged KOKKOS CUDA workflows, minimization, classical or reactive dynamics, potential-based studies, trajectory analysis, independent replicas and explicit native restart protocols. Discover the installed packages and qualified workflow before promising advanced features.
license: Apache-2.0
---

# LAMMPS on Scientific AI

Read `scientific-gateway`, then the [shared MD transport](../scientific-batch/references/native-md.md).
App ID: **lammps**. This is NVIDIA's NGC HPC container behind the platform's
scientific-batch API, not an HTTP NIM, a folding network or a docking service.
Installing this skill does not establish live availability or qualification.

## Preserve the native scientific protocol

Identify the question, system, units, atom style, potential/force-field files,
boundary conditions, charge treatment, ensemble, timestep, duration, random
seeds, output cadence and required analyses. Prefer the scientist's prepared
LAMMPS scripts. Ask about missing scientific choices; do not silently invent a
potential, convert units or describe arbitrary defaults as industry standards.

The selected NVIDIA build is LAMMPS 22 July 2025 with KOKKOS CUDA and a Serial
host backend. It is not the latest online manual. Use live runtime/package
metadata to verify styles. KOKKOS acceleration is not the separate `GPU` package;
`-sf gpu` is not an available substitute. Unaccelerated styles can spend time on
the CPU even in a GPU job. Do not silently switch a requested GPU protocol to CPU.

`backend: kokkos-cuda` selects one MPI rank and one GPU per job. `backend: cpu`
is an explicit native alternative, not a promise of a CPU-priced scheduler lane.
`threads` controls eligible CPU styles; this image's KOKKOS host backend remains
single-threaded. More threads need matched-system evidence, not an assumption.

## Input and parameters

Discover `get_model_schema(model_id="lammps", protocol="scientific-batch-v1")`.
The typed operation is `run-workflow`, initially `submit_lammps_workflow`.
Bundle the actual scripts, included files, data, potentials and restart context.
The input role is `lammps-inputs` / `lammps-input-bundle/v1`, gzip `application/x-tar`.
Use the shared client instead of fabricating artifact identifiers.

[Prepared workflow parameters](examples/native-workflow.json) show a parameter
object, not an executable scientific protocol. Replace filenames with inspected
inputs and set requested steps/duration in the native scripts. Each job has
ordered steps with `id`, `input`, optional `directory`, `variables`, `backend`
and `expected_outputs`. Variables are native `-var` arguments, not shell text.
Names beginning `fs2_` belong to the runner. Multiple jobs schedule independent
simulations; they do not distribute one simulation over multiple nodes.

The native engine retains its scripting language, loops, fixes, computes,
minimization and analysis commands. A compiled package alone is not a validated
scientific workflow. Check current evidence for requested free-energy, reactive,
ML-potential or specialized features before making support claims.

## Restart explicitly

An arbitrary script gets completed-stage recovery, not a checkpoint of its
interpreter. To resume inside a production stage, supply `continuation` with
the complete continuation script, restart file, integer progress file and
absolute target step. The script must use the offered `${fs2_segment_seconds}`
timer, write its closed restart and actual timestep after each segment, and
preserve outputs using `${fs2_segment}` or another non-overwriting naming scheme.
The worker checks the restart's actual timestep, not just the marker.

`read_restart` does not restore all fixes, computes, variables or output setup.
Re-declare the full continuation context, including constraints and thermostat
fix IDs needed to recover their native saved state. Do not run `reset_timestep`
or recreate velocities just to bypass a continuation mismatch. Check both script
and binary compatibility before moving a restart between versions or hardware.
See [restart guidance and source documentation](references/native-workflows.md).

## Validate and interpret

Read all expected trajectory frames, inspect atom IDs/count, timestep continuity,
finite thermodynamics, lost-atom warnings and model-specific stability checks.
Keep raw logs and package/GPU dispatch metadata. ReaxFF charge equilibration and
reactive changes need appropriate checks; a short finite trajectory is not proof
that the chosen structure or potential is scientifically valid.

Report atom-timesteps/second or steps/second. Convert to ns/day only when the
declared units and timestep define real time. Reduced `units lj` does not supply
a universal nanosecond conversion. Compare identical atom count, precision,
potential, neighbor settings, output cadence and GPU count. NVIDIA multi-GPU
or aggregate-throughput charts are not single-GPU acceptance targets.

Preserve failed results and offer a concrete correction without silently changing
the experiment. The shared reference describes bucket recovery and CUDA snapshot
limitations; native binary restart is not GPU process snapshotting.
