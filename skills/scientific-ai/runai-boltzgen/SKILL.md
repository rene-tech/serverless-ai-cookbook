---
name: runai-boltzgen
description: Run reviewed BoltzGen protein, peptide, small-molecule, nanobody, antibody and redesign protocols through the managed Scientific AI Run:ai service. Use for native YAML scientific inputs, inverse-folding controls, filtering and interpretable ranked designs.
license: Apache-2.0
---

# boltzgen on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `boltzgen`. Documented scientific version: `0.3.2`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Archive `design.yaml`, `settings.json` and all referenced structure/YAML
files at their declared relative paths. They stage below `data/inputs/`.
Referenced includes resolve relative to the YAML that contains them; keep the
whole dependency tree. Only reviewed scientific structures and safe YAML data
are accepted, not executable modules or interpolated code.

## Choose the scientific workflow

Choose the intended protocol from the live schema: `protein-anything`,
`peptide-anything`, `protein-small_molecule`, `nanobody-anything`,
`antibody-anything` or `protein-redesign`. Preserve target chemistry and constraints.
Select balanced/diverse/adherence checkpoint variants deliberately.

`num_designs` must fit `diffusion_batch_size`; `budget` cannot exceed the actual
candidate count. Inverse-fold-only and skip-inverse-fold modes are distinct.
Ranking weights, additional filters, RMSD thresholds and size buckets change
scientific selection; do not relax them to manufacture a successful result.
Use the live qualified GPU profile; a B200 request historically required the
explicit supported `use_kernels="false"` path. Do not claim unqualified kernel
defaults work or silently override an explicit caller choice.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### design

MCP tool: `boltzgen_design`. Execution: GPU.

```json
{"model":"boltzgen","workflow":"design","version":"0.3.2","parameters":{"num_designs":20,"budget":1,"protocol":"protein-anything"}}
```

## Interpret and retain results

Inspect structures, sequence/chemistry identity, native filters and ranking
tables. Report attempted, valid and selected designs separately. Zero candidates
passing native filters is an explicit scientific outcome, not proof of a usable
binder. Keep phase timing separate from accepted-design yield.

Recovery retains completed native pipeline stages. An unfinished stage may
recompute; this is not arbitrary mid-diffusion GPU process restoration.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
