---
name: runai-bindcraft2
description: Use managed BindCraft2 design and CPU score/rank/filter/campaign/archive workflows through Scientific AI Run:ai. Use for bounded native binder campaigns, caller-owned structures and tables, exact file staging and accepted-design interpretation.
license: Apache-2.0
---

# bindcraft2 on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `bindcraft2`. Documented scientific version: `1.0.4`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

| Workflow | Archive members and logical input |
|---|---|
| `design` | Root `settings.json` and its target/scaffold structures; default `data/inputs/settings.json` |
| `score` | Root `structure.pdb` (or supported structure selected with `input`); default `data/inputs/structure.pdb` |
| `rank`, `filter` | Complete `campaign/` native scientific tables/structures, or a supported CSV selected with `input` |
| `campaign_output`, `archive` | Complete `campaign/` native scientific data directory |

Members stage under `data/inputs/`. Top-level `parameters.input` selects a
logical file/directory there. Within design JSON, each `targets[].target_path`
and `binder_scaffold` resolves relative to the settings JSON's directory. For
example, root `settings.json` with `target_path:"targets/target.pdb"` requires
the archive member `targets/target.pdb`. It is not a bucket key or host path.

Preserve a campaign's `1_Trajectories`, `2_Refolded` and `3_Ranked` directories,
CSV filenames such as `!_Ranked.csv`, and structure references. Scoring accepts
reviewed PDB/mmCIF scientific data. Do not upload executable resume state.

## Choose the scientific workflow

Design JSON controls target chains/hotspots, binder lengths, seed, supported
modality/core/target presets, native losses/filters and bounded work. This managed
workflow **requires** a finite `max_trajectories` budget of 1–4096.
`number_of_final_designs` defaults to 1 and accepts 1–4096. Use the live nested
settings schema, not guessed names. Defaults do not establish that an
epitope or membrane geometry is scientifically appropriate.

Explicit `filters:false` or `filters:null` disables native candidate filters.
Results from that choice are unfiltered candidates; do not report them as having
passed the default acceptance filters or as experimentally validated binders.

`score` is CPU structural/sequence metric analysis; pre-existing prediction
confidence is an input claim, not newly inferred affinity. `rank` chooses named
available metrics and direction; `filter` applies explicit expressions/filters.
`campaign_output` summarizes/reranks supplied native campaign data, and `archive`
packages scientific trajectory data. These operations do not launch GPU design.

For a pilot, retain the native default scientific profile unless a deliberate
comparison is requested. Do not select a reduced benchmark profile, relax filters
or cap sampling to force an accepted-design goal to pass.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### design

MCP tool: `bindcraft2_design`. Execution: GPU.

```json
{"model":"bindcraft2","workflow":"design","version":"1.0.4","parameters":{}}
```

### score

MCP tool: `bindcraft2_score`. Execution: CPU.

```json
{"model":"bindcraft2","workflow":"score","version":"1.0.4","parameters":{"binder":"B","target":"A"}}
```

### rank

MCP tool: `bindcraft2_rank`. Execution: CPU.

```json
{"model":"bindcraft2","workflow":"rank","version":"1.0.4","parameters":{"metrics":["i_pTM"],"input":"data/inputs/campaign/3_Ranked/!_Ranked.csv"}}
```

### filter

MCP tool: `bindcraft2_filter`. Execution: CPU.

```json
{"model":"bindcraft2","workflow":"filter","version":"1.0.4","parameters":{"where":["i_pTM>=0.7"],"include_rejected":true}}
```

### campaign_output

MCP tool: `bindcraft2_campaign_output`. Execution: CPU.

```json
{"model":"bindcraft2","workflow":"campaign_output","version":"1.0.4","parameters":{}}
```

### archive

MCP tool: `bindcraft2_archive`. Execution: CPU.

```json
{"model":"bindcraft2","workflow":"archive","version":"1.0.4","parameters":{}}
```

## Interpret and retain results

Count attempted trajectories, accepted designs and native rejection reasons
separately. A trajectory, nonempty CSV or predicted confidence is not an accepted
binder. Budget exhaustion with zero accepted designs is an unmet scientific goal,
not a silently fulfilled successful campaign.

Check scoring columns and chain assignments, ranking order, filter membership,
campaign summaries and archive contents against the actual inputs. Native
closed-unit continuation retains completed work/accepted designs; it does not
restore arbitrary unfinished optimizer/GPU/RNG state. Keep the same owned run,
scientific settings and original deadline across authorized regional recovery.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
