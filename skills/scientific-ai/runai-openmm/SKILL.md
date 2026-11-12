---
name: runai-openmm
description: Run the reviewed OpenMM CUDA molecular-dynamics workflow on the managed Scientific AI Run:ai service. Use for prepared topology/coordinate input, fixed reviewed Python controls, physical outputs and compatible checkpoint continuation.
license: Apache-2.0
---

# openmm on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `openmm`. Documented scientific version: `8.6.1.dev-b399af4`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

The `hecbiosim-20k` archive contains `benchmark.top`, `benchmark.crd` and the
published reviewed `benchmark.py`. Members stage below `data/`. Preserve the
Python control byte-for-byte; arbitrary customer Python execution is outside
this workflow. The topology and coordinates must describe the same system.

## Choose the scientific workflow

The workflow performs reviewed minimization and Langevin-middle production,
using the declared temperature/pressure, timestep and mixed precision. Public
`steps` and `threads` controls do not expose arbitrary integrator/system code.
For a different physical protocol, check the live reviewed capability rather
than inserting custom Python into the input archive.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### hecbiosim-20k

MCP tool: `openmm_hecbiosim_20k`. Execution: GPU.

```json
{"model":"openmm","workflow":"hecbiosim-20k","version":"8.6.1.dev-b399af4","parameters":{}}
```

## Interpret and retain results

Inspect `openmm-output` native results, state/energy tables, final coordinates
and checkpoints. Verify actual integration progress, finite energies and system
identity. A valid serialized System alone is not completed dynamics.

Native binary checkpoint restore requires compatible runtime/system/platform;
portable state reconstruction is a distinct guarantee. Resume preserves the
same version, precision, requested work and original cumulative deadline.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
