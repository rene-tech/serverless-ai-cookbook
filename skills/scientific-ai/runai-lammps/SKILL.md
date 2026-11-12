---
name: runai-lammps
description: Run reviewed LAMMPS molecular dynamics through the managed Scientific AI Run:ai API and MCP. Use for the prepared benchmark or alanine workflow, native Kokkos/CUDA execution, thermo output and restart continuation.
license: Apache-2.0
---

# lammps on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `lammps`. Documented scientific version: `22Jul2025+shake988b963.r2`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

| Workflow | Scientific archive members | Reviewed controls |
|---|---|---|
| `hecbiosim-20k` | `benchmark.data` | Published `benchmark.in`, `measured.in`, `measured-resume.in` |
| `alanine-quickstart` | `system-shake.lmp`, `system-original.lmp` and the complete published parameter/include tree | Published minimization/NVT/NPT/production and resume `.in`/`.inc` files |

Members stage below `data/`. Use the current complete template; an older
benchmark archive without the reviewed resume control is not interchangeable.
Retain all referenced force-field coefficients and native restart definitions.
Use scientific data inputs, not arbitrary replacement LAMMPS programs.

## Choose the scientific workflow

Preserve units, atom style, force field, constraints and precision. Choose
`steps` for the benchmark or `production_end_step` for the alanine workflow;
the latter is an absolute target step, not automatically additional time.
`checkpoint_seconds` controls supported segmentation. Never reduce constraints
or change the system to manufacture a faster benchmark.

Use the qualified GPU build selected by the platform. A faster GPU family is
not guaranteed to improve a small or constraint-bound system; report actual
native work and CPU/GPU utilization at matched settings.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### hecbiosim-20k

MCP tool: `lammps_hecbiosim_20k`. Execution: GPU.

```json
{"model":"lammps","workflow":"hecbiosim-20k","version":"22Jul2025+shake988b963.r2","parameters":{}}
```

### alanine-quickstart

MCP tool: `lammps_alanine_quickstart`. Execution: GPU.

```json
{"model":"lammps","workflow":"alanine-quickstart","version":"22Jul2025+shake988b963.r2","parameters":{}}
```

## Interpret and retain results

Check thermo tables and native logs for finite energies, correct step advance
and physical units. Verify the binary restart plus all required coefficients;
preserve trajectory/output cadence. Report steps/s or ns/day with timestep,
atom count and force-field settings.

Compatible native continuation restores the latest verified restart and resumes
to the original target step. An interrupted command may repeat its unfinished
segment; do not describe a fresh simulation as checkpoint continuation.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
