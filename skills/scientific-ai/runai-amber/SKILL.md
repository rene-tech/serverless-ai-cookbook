---
name: runai-amber
description: Run reviewed AMBER/PMEMD molecular dynamics on the managed Scientific AI Run:ai service. Use for the finite HECBioSim example or alanine minimization, equilibration, production and analysis with native restart data.
license: Apache-2.0
---

# amber on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `amber`. Documented scientific version: `26.0`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

| Workflow | Scientific archive members | Reviewed controls |
|---|---|---|
| `hecbiosim-20k` | `benchmark.top`, `benchmark.rst` | Published `benchmark.in`, `measured.in` |
| `alanine-quickstart` | `system.prmtop`, `system.rst7`, `system.pdb` | Published minimization/NVT/NPT/production inputs, `inspect.parmed`, `analyze.in` |

Members stage directly below `data/`. Copy the complete published template,
including its provenance and reviewed controls. The topology, coordinates,
box and restart velocities must describe the same system; do not substitute an
unparameterized predicted PDB for the required AMBER inputs.

## Choose the scientific workflow

The HECBioSim workflow executes a prepared finite dynamics segment. The alanine
workflow performs reviewed inspection, minimization, equilibration, production
and trajectory analysis. `steps` or `production_steps` controls native work;
`checkpoint_steps` controls supported segment boundaries, not a new trajectory.
Use published bounds: a very short checkpoint interval can exceed the native
workflow's available stage budget.

Preserve native SPFP precision and the user's physics. Platform access remains
subject to the caller's AMBER entitlement; this skill grants no licence rights.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### hecbiosim-20k

MCP tool: `amber_hecbiosim_20k`. Execution: GPU.

```json
{"model":"amber","workflow":"hecbiosim-20k","version":"26.0","parameters":{"steps":50000,"threads":8}}
```

### alanine-quickstart

MCP tool: `amber_alanine_quickstart`. Execution: GPU.

```json
{"model":"amber","workflow":"alanine-quickstart","version":"26.0","parameters":{"production_steps":10000,"threads":1}}
```

## Interpret and retain results

Read native output/MDINFO for completed step counts, finite energy and ensemble
behavior. Verify restart (`.rst7`) and trajectory/analysis outputs rather than
equating exit zero with correct sampling. Compare ns/day at matched system,
steps, precision and I/O settings.

Recovery continues from the last verified native restart and matching topology;
coordinates, velocities and periodic-box state must remain consistent. Preserve
the original cumulative execution deadline and owner bucket.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
