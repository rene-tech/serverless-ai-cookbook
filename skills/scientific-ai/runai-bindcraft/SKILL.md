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

Before using default inputs, confirm the live `design` schema
`example.inputs[0].sha256` is
`e63ec3845f51b3f3513033c70467e44a3c1bb958b8d3b206c0413b00f85e2f07`
and its archive contract names root `target.pdb`. During a rollout, wait for
that contract or supply your own archive from the optional PD-L1 pilot below.

```json
{"model":"bindcraft","workflow":"design","version":"source-7cd4ace1b740","parameters":{"seed":912083,"minimum_length":67,"maximum_length":67,"accepted_designs":1,"max_trajectories":20,"target_chains":"A","hotspots":"A37,A39,A98,A104,A106","mpnn_lane":"vanilla","advanced_profile":"legacy","filter_profile":"legacy"}}
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

## Optional bounded PD-L1 pilot

This target-specific example is separate from the canonical catalog target.
Download the exact tested public target from NVIDIA's pinned source below. It
contains chain A residues 1–115; preserve its coordinates, numbering and bytes.
Different PD-L1 structures do not reproduce this example's target/hotspots.

```sh
mkdir -p prepared-inputs
curl --fail --location --silent --show-error \
  https://raw.githubusercontent.com/NVIDIA-BioNeMo/Proteina-Complexa/54058860d43444c7289873f77d3e50b5b02348cd/assets/target_data/bindcraft_targets/PD-L1.pdb \
  -o prepared-inputs/target.pdb
printf '%s  %s\n' \
  5e949950d8255ec3bf390b8bf24f5c71c6ac8fc65bc553d7e477563c9599b93e \
  prepared-inputs/target.pdb | sha256sum --check
tar -czf input.tar.gz -C prepared-inputs target.pdb
```

The target is 74,614 bytes. Choose an authorized `INPUT_KEY` in your own bound
bucket. Use the portable procedure's Python reference-generation block on this
archive to create `input-reference.json`, then its S3 upload command. This
archive has only root `target.pdb`; its compressed hash/size come from your own
archive, not an operator's bucket. Compose the exact scientific request:

```sh
jq -n --slurpfile input input-reference.json '{
  model:"bindcraft", workflow:"design", version:"source-7cd4ace1b740",
  region:"eu-north1", gpu:"h100", inputs:[$input[0]],
  parameters:{seed:912083, minimum_length:67, maximum_length:67,
    accepted_designs:1, max_trajectories:20, target_chains:"A",
    hotspots:"A37,A39,A98,A104,A106", mpnn_lane:"vanilla",
    advanced_profile:"legacy", filter_profile:"legacy"}
}' > request.json
```

Confirm EU-North1/H100 access, then submit this file using the portable REST
procedure. In MCP, call `bindcraft_design` with the same `version`, `region`,
`gpu`, `inputs` and `parameters`, plus the saved `idempotency_key`; omit
`model`/`workflow`. Keep the full trajectory ceiling and native filters.
The cap counts closed/relaxed native units; failed low-confidence or clashing
attempts can be additional. The original cumulative two-week deadline still applies.
Managed success also requires at least one correctly mapped requested hotspot
to have an atom within 4 Å of a binder atom. Generic native filter acceptance
alone does not establish this product criterion.
The scientific goal is one native filter-passing design, not guaranteed binding
or guaranteed acceptance within the budget. Report `NATIVE_GOAL_NOT_MET` and
rejections honestly; do not search seeds or weaken filters to force a pass.
