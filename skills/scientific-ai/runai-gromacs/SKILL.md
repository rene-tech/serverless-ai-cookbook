---
name: runai-gromacs
description: Run reviewed single-GPU GROMACS molecular-dynamics workflows through the managed Scientific AI Run:ai service. Use for prepared TPR execution or the explicit alanine preparation/equilibration/production workflow, native results and compatible checkpoint continuation.
license: Apache-2.0
---

# gromacs on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `gromacs`. Documented scientific version: `2026.4`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

| Workflow | Scientific archive members | Reviewed controls |
|---|---|---|
| `hecbiosim-20k` | `benchmark.tpr` containing the intended system and protocol | None supplied by the caller |
| `alanine-quickstart` | `system.gro`, `system.top` and referenced topology includes | Published `minimize.mdp`, `nvt.mdp`, `npt.mdp`, `production.mdp` |

Archive members stage directly below logical `data/`. Copy the complete published
template from the caller's bucket; keep its reviewed controls unchanged. A new
prepared TPR must encode the intended system, force field and protocol. The
`steps` control changes the finite benchmark length; inspect timestep and
continuation state before interpreting steps as a physical duration.

## Choose the scientific workflow

Choose `hecbiosim-20k` for a prepared TPR. Choose `alanine-quickstart` for
the explicit reviewed minimization → NVT → NPT → production example. It is not a
general script-upload interface. Multi-node MPI and arbitrary custom GROMACS
command graphs are outside this service's current reviewed workflow envelope.

Use MDPrecheck when requested for input assessment; a warning requires scientific
interpretation, not an automatic repair or changed force field. Preserve the
user's timestep, output cadence, precision and sampling protocol.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### hecbiosim-20k

MCP tool: `gromacs_hecbiosim_20k`. Execution: GPU.

```json
{"model":"gromacs","workflow":"hecbiosim-20k","version":"2026.4","parameters":{"steps":50000,"threads":8}}
```

### alanine-quickstart

MCP tool: `gromacs_alanine_quickstart`. Execution: GPU.

```json
{"model":"gromacs","workflow":"alanine-quickstart","version":"2026.4","parameters":{"threads":8}}
```

## Interpret and retain results

Inspect native logs for actual completed integration steps, finite energies and
the selected ensemble. Check trajectory/energy files (`.xtc`/`.trr`, `.edr`),
coordinates (`.gro`) and native `.cpt` checkpoints as applicable. Report ns/day
only with the same atom count, timestep, physics and output cadence. A finite
quickstart does not demonstrate equilibration or convergence.

Resume the same owned run from a verified native checkpoint, preserving system,
version, original deadline and requested duration semantics. A different input
TPR or an already-finished checkpoint is not proof of interrupted continuation.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
