---
name: runai-proteina-complexa
description: Run reviewed Proteina-Complexa generation, full design, filtering, evaluation and analysis on the managed Scientific AI Run:ai service. Use for protein/ligand/AME variants, owner-supplied targets, scientific metrics and staged recovery.
license: Apache-2.0
---

# proteina-complexa on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `proteina-complexa`. Documented scientific version: `1.1.0`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Every operation reads root `settings.json`, staged as
`data/inputs/settings.json`. Generation/design settings may include a custom
`target` with `bundle_path`, `target_input`, `hotspot_residues`, `binder_length`
and optional `pdb_id`. `bundle_path` resolves from the archive input root, so
`targets/target.pdb` names that actual member, not a remote URL or host path.
Preserve source structure numbering and chemical identity.

Filter/evaluate/analyze additionally require `source_directory` in settings,
such as `data/inputs/prior`, with the complete previous native structures/tables
tree. Copy scientific outputs, not executable configuration or another owner's
checkpoint. Do not flatten or rename table-to-structure references.

## Choose the scientific workflow

Select `variant` (`protein`, `ligand`, `ame`) and a compatible target/weight
family through the live contract. `generate` is reward-free sampling; `design`
includes generation, native filtering, refolding/evaluation and analysis. Full
design needs its supported reward configuration; AME full design requires
`reward_model="rf3"`. Do not turn a requested full design into generation only.

Optional ESM, designability, codesignability and co-sequence-recovery metrics are
explicit opt-ins with qualified assets. Protein targets and ligand/AME inputs
need compatible inverse-folding models. CPU filtering/aggregation are separate
from GPU generation/evaluation. Reuse completed native stages when supported.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### generate

MCP tool: `proteina-complexa_generate`. Execution: GPU.

```json
{"model":"proteina-complexa","workflow":"generate","version":"1.1.0","parameters":{}}
```

### design

MCP tool: `proteina-complexa_design`. Execution: GPU.

```json
{"model":"proteina-complexa","workflow":"design","version":"1.1.0","parameters":{}}
```

### filter

MCP tool: `proteina-complexa_filter`. Execution: CPU.

```json
{"model":"proteina-complexa","workflow":"filter","version":"1.1.0","parameters":{}}
```

### evaluate

MCP tool: `proteina-complexa_evaluate`. Execution: GPU.

```json
{"model":"proteina-complexa","workflow":"evaluate","version":"1.1.0","parameters":{}}
```

### analyze

MCP tool: `proteina-complexa_analyze`. Execution: CPU.

```json
{"model":"proteina-complexa","workflow":"analyze","version":"1.1.0","parameters":{}}
```

## Interpret and retain results

Verify structures, native rewards/filter decisions, refolding or interface
metrics and aggregation row/structure identifiers. Generated coordinates alone
do not establish designability or affinity. Report unavailable optional metrics
instead of filling them with invented values.

Recovery preserves completed stages and verified owner outputs. Unfinished
stages may recompute; preserve variant, target, version, settings and deadline.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
