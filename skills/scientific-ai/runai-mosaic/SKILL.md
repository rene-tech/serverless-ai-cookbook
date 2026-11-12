---
name: runai-mosaic
description: Run reviewed Mosaic protein-binder design through the managed Scientific AI Run:ai API and MCP. Use for a canonical target FASTA, position-based hotspots, supported optimization objectives and interpretable design outputs.
license: Apache-2.0
---

# mosaic on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `mosaic`. Documented scientific version: `0.1.0`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Archive `target.fasta` and `settings.json` at the root, staging below
`data/inputs/`. The FASTA contains exactly one canonical protein sequence.
Hotspots are sorted unique one-based target positions, not PDB chain/residue
identifiers. Confirm their biological mapping before submitting.

## Choose the scientific workflow

Use `count`, seed, binder length and optimizer steps for a bounded design task.
Supported objective weights cover contact, within-contact, pLDDT, inverse folding,
helix and radius terms; at least one objective must be active. A requested target
radius needs a nonzero radius weight. Step size, momentum, clipping, scale,
recycling, sampling and optional optimizer/PSSM outputs follow the live schema.
Do not change objectives or shorten optimization merely to claim a speedup.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### design

MCP tool: `mosaic_design`. Execution: GPU.

```json
{"model":"mosaic","workflow":"design","version":"0.1.0","parameters":{}}
```

## Interpret and retain results

Verify generated sequences/structures, target mapping, requested lengths and
objective/quality traces. Distinguish attempted optimization from a scientifically
accepted binder; predicted scores do not establish experimental binding.
Completed native design units can be retained during recovery, while unfinished
work may repeat. Inspect the live checkpoint guarantee before promising
mid-optimizer or RNG restoration.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
