---
name: runai-mdprecheck
description: Inspect molecular-dynamics inputs with the CPU-only MDPrecheck workflows on the managed Scientific AI Run:ai service. Use for prepared GROMACS TPR intake or source topology/coordinate/MDP checks and bounded diagnostic probes.
license: Apache-2.0
---

# mdprecheck on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `mdprecheck`. Documented scientific version: `0.1.0+git.1ab41dd`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

| Workflow | Scientific archive members |
|---|---|
| `hecbiosim-20k` | `benchmark.tpr` |
| `alanine-source` | `system.gro`, `system.top`, `production.mdp` and referenced topology includes; preserve the complete source template |

Members stage below `data/`. A TPR-only input is a legitimate prepared-system
input; do not claim its original source topology/MDP can always be reconstructed.
Source-file checks require the actual matching source files.

## Choose the scientific workflow

This is a CPU service; leave GPU selection unset. Use `probes` only from the
current schema, with `threads` and supported `nsteps` for bounded diagnostic
work. Do not automatically turn a requested inspection into a production MD run.
Offer scientific repairs only when findings and source data support them;
warnings are not permission to change force field, stereochemistry or protocol.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### hecbiosim-20k

MCP tool: `mdprecheck_hecbiosim_20k`. Execution: CPU.

```json
{"model":"mdprecheck","workflow":"hecbiosim-20k","version":"0.1.0+git.1ab41dd","parameters":{"threads":2,"probes":[]}}
```

### alanine-source

MCP tool: `mdprecheck_alanine_source`. Execution: CPU.

```json
{"model":"mdprecheck","workflow":"alanine-source","version":"0.1.0+git.1ab41dd","parameters":{"threads":2,"nsteps":1000,"probes":["energy","minimize","stability"]}}
```

## Interpret and retain results

Read the structured report, probe results and retained diagnostic outputs.
Separate successful execution of the check from scientific `pass`, `warn` or
`fail` findings. Explain the evidence and affected input; do not claim minimized
coordinates prove correct stereochemistry or a converged simulation.

Short checks are normally restarted rather than continued from a native MD
checkpoint. Preserve input/version/owner identity and avoid duplicate work after
an uncertain submission.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
