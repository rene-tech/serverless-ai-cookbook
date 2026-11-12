---
name: runai-rfd4-proteina
description: Run reviewed RFD4-Proteina annotated, sharded and reward-guided protein design on the managed Scientific AI Run:ai service. Use for annotated-CIF inputs, supported native sampling/search controls and resumable completed design units.
license: Apache-2.0
---

# rfd4-proteina on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `rfd4-proteina`. Documented scientific version: `source-ed63183a7f27`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Archive annotated `input.cif` and `settings.json` at the root; they stage
below `data/inputs/`. Preserve annotations, chains, residues and any model-specific
constraint fields. A plain unannotated structure is not automatically equivalent
to a prepared design request.

## Choose the scientific workflow

Choose `annotated-design` for the reviewed annotated native request,
`native-sharded-design` when completed replicate units must survive interruption,
or `reward-guided-search` for the supported search/beam controls. Read actual
`num_replicates`, `batch_size`, `nsteps`, seed and recycling/compilation settings.
Trajectory saving and CA-only versus all-atom output are explicit choices.

Reward search may expose beam width, branching and rollout/state saving. External
oracles, independent refolding, Foldseek and PEFT are not implicitly supplied by
this service. Never copy private model sampling state from another owner.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### annotated-design

MCP tool: `rfd4-proteina_annotated_design`. Execution: GPU.

```json
{"model":"rfd4-proteina","workflow":"annotated-design","version":"source-ed63183a7f27","parameters":{}}
```

### native-sharded-design

MCP tool: `rfd4-proteina_native_sharded_design`. Execution: GPU.

```json
{"model":"rfd4-proteina","workflow":"native-sharded-design","version":"source-ed63183a7f27","parameters":{}}
```

### reward-guided-search

MCP tool: `rfd4-proteina_reward_guided_search`. Execution: GPU.

```json
{"model":"rfd4-proteina","workflow":"reward-guided-search","version":"source-ed63183a7f27","parameters":{}}
```

## Interpret and retain results

Check final structures and native metric tables against the annotated target,
actual requested replicates and requested trajectory atom/frame layout. Preserve
identifiers across search results, sampling states and structural outputs.
An incomplete beam is a partial result, not a finished design campaign.

Sharded recovery can retain completed units and continue unfinished work in an
authorized compatible region. A sampling-state output file does not by itself
prove arbitrary mid-process restore or bit-for-bit RNG continuation.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
