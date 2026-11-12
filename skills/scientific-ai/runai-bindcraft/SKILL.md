---
name: runai-bindcraft
description: Run reviewed BindCraft native campaigns or explicit trajectory generation on managed Scientific AI Run:ai. Use for target-conditioned binder design, accepted-design budgets, native filters/profiles and closed-trajectory recovery.
license: Apache-2.0
---

# bindcraft on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `bindcraft`. Documented scientific version: `source-7cd4ace1b740`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Archive root `target.pdb`; the `trajectories` template also includes
`settings.json`. They stage under `data/inputs/`. `input` and optional
`settings_file` parameters select supported files in that logical input tree.
Map requested target chains/hotspots to actual PDB identifiers and preserve the
scientific target. Do not upload arbitrary executable Python or native runtime state.

## Choose the scientific workflow

Use `design` for the full native whole-campaign behavior, including supported
process-wide adaptive counters. Use `design-campaign` for the reviewed bounded
accepted-design campaign with closed-trajectory checkpoints. Use `trajectories`
only when relaxed native trajectories are the requested product; ProteinMPNN/
refolding are disabled there, so those outputs are not accepted binders.

Set binder-length range, target chains/hotspots, seed, accepted-design goal and
maximum trajectory budget deliberately. Advanced/filter profiles, ProteinMPNN
lane and typed scientific settings follow the live contract. Preserve scientific
filter thresholds and the caller's native settings; do not weaken them to make
a qualification run pass.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### design

MCP tool: `bindcraft_design`. Execution: GPU.

```json
{"model":"bindcraft","workflow":"design","version":"source-7cd4ace1b740","parameters":{"count":1,"accepted_designs":1}}
```

### design-campaign

MCP tool: `bindcraft_design_campaign`. Execution: GPU.

```json
{"model":"bindcraft","workflow":"design-campaign","version":"source-7cd4ace1b740","parameters":{"accepted_designs":1,"max_trajectories":100}}
```

### trajectories

MCP tool: `bindcraft_trajectories`. Execution: GPU.

```json
{"model":"bindcraft","workflow":"trajectories","version":"source-7cd4ace1b740","parameters":{"max_trajectories":2}}
```

## Interpret and retain results

Verify target/binder chains, sequence/length, native filter outcomes and the
requested accepted-design goal. Report attempted trajectories, accepted designs
and rejected candidates separately. B200 trajectory evidence alone does not
qualify accepted-design behavior; follow the actual live supported envelope.

Campaign recovery retains completed trajectories and their verified outputs;
whole-campaign adaptive state and closed-trajectory continuation have different
guarantees. Do not promise restoration of an interrupted optimizer or identical
RNG continuation. Preserve the original run/version/deadline.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
