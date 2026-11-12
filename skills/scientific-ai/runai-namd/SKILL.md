---
name: runai-namd
description: Run reviewed NAMD dynamics on the managed Scientific AI Run:ai service. Use for prepared HECBioSim inputs, the alanine minimization/equilibration/production workflow, qualified GPU modes and native cross-region restart.
license: Apache-2.0
---

# namd on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `namd`. Documented scientific version: `3.0.2`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

| Workflow | Scientific archive members | Reviewed controls |
|---|---|---|
| `hecbiosim-20k` | `benchmark.psf`, `benchmark.pdb`, `benchmark.coor`, `benchmark.vel`, `benchmark.xsc`, `par_all27_prot_lipid.prm` | Published `benchmark.in`, `measured.in` |
| `alanine-quickstart` | `alanine/system.pdb`, `alanine/system.prmtop`, `alanine/system.rst7` | Published `alanine/*.namd` controls |

Keep the complete template tree. Members stage under `data/`; the alanine
workflow runs inside its `alanine/` directory. A config file's relative topology,
coordinate and force-field references must resolve there. Arbitrary Tcl is not
accepted by these reviewed workflows.

## Choose the scientific workflow

Choose the live workflow's `gpu_mode` only when deliberately comparing a
qualified resident/offload mode. Otherwise preserve platform placement/defaults;
do not rewrite a saved run's mode when resuming. Keep thread count and scientific
steps explicit for matched performance comparisons. `checkpoint_steps` sets a
supported restart boundary, not permission to shorten the requested simulation.

The alanine workflow includes native preparation stages followed by segmented
dynamics. A dataset built for another force field or cell convention needs
scientific preparation before submission.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### hecbiosim-20k

MCP tool: `namd_hecbiosim_20k`. Execution: GPU.

```json
{"model":"namd","workflow":"hecbiosim-20k","version":"3.0.2","parameters":{"steps":50000,"checkpoint_steps":50000,"threads":8}}
```

### alanine-quickstart

MCP tool: `namd_alanine_quickstart`. Execution: GPU.

```json
{"model":"namd","workflow":"alanine-quickstart","version":"3.0.2","parameters":{"production_steps":10000,"checkpoint_steps":10000,"threads":4}}
```

## Interpret and retain results

Read native NAMD logs for actual first/final timesteps, finite energy and
measured ns/day at the stated atom count and mode. Verify restart coordinates,
velocities and extended-system/cell files together (`.coor`, `.vel`, `.xsc`).
Resume only with compatible native version, system and mode; preserve the
original deadline and source writer quiescence. A portable-state restart and
exact binary continuation are different guarantees.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
