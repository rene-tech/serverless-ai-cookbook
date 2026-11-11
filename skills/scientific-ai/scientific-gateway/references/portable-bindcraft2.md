# BindCraft2 design and CPU analysis from a portable client

These are **BindCraft2 1.0.4** contracts, not BindCraft1. Access is currently
restricted to approved internal research identities. Third-party hosted access
remains held; this guide does not grant access or a licence. Discover `bindcraft2` and `bindcraft2-analysis` with your
own connection before uploading. Use the portable client's environment-variable
configuration; no LibreChat, container path or key in a prompt is required.

Both Apps accept one plain, uncompressed tar archive:

| Manifest field | Exact value |
| --- | --- |
| `name` | `campaign` |
| `semantic_type` | `bindcraft2-input-tar/v1` |
| inner artifact `media_type` | `application/x-tar` |
| inner artifact `compression` | `none` |
| outer manifest `media_type` | `application/vnd.fs2.scientific-manifest+json` |

The published 128 GiB artifact ceiling is a transport limit, not a promise that
a campaign of that size fits memory or completes. Use the live schema if it
differs from this versioned example.

## GPU design: a bounded public-target example

`submit_bindcraft2` accepts only `operation: design`. Its API `parameters`
select the archive-relative settings file. Scientific settings belong **inside
that file**, not at the top level of the MCP arguments.

Run from the extracted portable-client directory. This downloads the exact
upstream public PD-L1 example, then packs it with a two-trajectory campaign.
The `benchmark` core preset fixes reproducibility settings and disables native
autotuning/desperation; it does not relax the native acceptance filters.
Two trajectories may produce **zero accepted designs**. That is an exhausted
campaign, not a successful binder discovery or an API failure.

```bash
mkdir -p inputs runs
mkdir inputs/bc2-design
mkdir inputs/bc2-design/targets
curl --fail --location \
  'https://raw.githubusercontent.com/PacesaLab/BindCraft2/d502f19a187a1bc8c05e833ca9cbab7bc1934fe7/settings/target/structures/hPDL1.pdb' \
  --output inputs/bc2-design/targets/hPDL1.pdb
cat > inputs/bc2-design/settings.json <<'EOF'
{
  "core": "benchmark",
  "modality": "binder",
  "targets": [{
    "name": "hPDL1",
    "target_path": "targets/hPDL1.pdb",
    "chains": "A",
    "hotspots": "54,56,66,115"
  }],
  "binder_lengths": [60],
  "campaign_seed": 0,
  "number_of_final_designs": 1,
  "max_trajectories": 2
}
EOF
tar -C inputs/bc2-design -cf inputs/bc2-design.tar settings.json targets
printf '%s\n' '{"input_path":"settings.json"}' > inputs/bc2-design-parameters.json

.venv/bin/python invoke-scientific-batch.py \
  --model bindcraft2 --tool submit_bindcraft2 --operation design \
  --source inputs/bc2-design.tar --media-type application/x-tar --compression none \
  --entry-name campaign --semantic-type bindcraft2-input-tar/v1 \
  --parameters inputs/bc2-design-parameters.json \
  --idempotency-key bc2-pdl1-60-seed0-two-trajectories-001 \
  --display-name 'BindCraft2 bounded PD-L1 design' \
  --output runs/bc2-design --wait-seconds 1800
```

`input_path` resolves from the archive root. Each `targets[].target_path` and an
optional `binder_scaffold` resolve from the **settings JSON's directory**. For
example, `input_path: configs/settings.json` with
`target_path: targets/receptor.pdb` selects
`configs/targets/receptor.pdb` inside the archive. Add a scaffold as a real file
under that directory and set `binder_scaffold` to its relative path; preserve
the scaffold's native `mutate_positions`/modality settings. Scaffold design is
not qualified merely by the de novo example above. Do not use absolute paths,
`..`, symlinks, or paths to another owner's data.

Replace the public target with your own structure when intended, and update
chains and hotspots to its real residue numbering. Native PDB/mmCIF targets
and FASTA targets have different semantics; sequence-only targets have no
structural hotspot numbering. Do not copy the example's hotspot numbers onto
another target. `project_folder`, GPU/worker allocation and `resume` are
execution-owned and cannot be set in the campaign. The hosted command does not
currently expose automatic durable campaign continuation or intra-step resume.

## CPU score: an existing two-chain structure

`submit_bindcraft2_analysis` accepts `score`, `rank`, `filter`,
`campaign-output` and `archive`; these are separate from GPU design. This
example scores the upstream public IL-2 receptor two-chain structure as a
**geometry demonstration**, with chain B assigned to the binder role and A
to the target role. It is not a designed or experimentally validated binder.
For your own complex, use its actual chain roles and structure instead.

```bash
mkdir inputs/bc2-score
curl --fail --location \
  'https://raw.githubusercontent.com/PacesaLab/BindCraft2/d502f19a187a1bc8c05e833ca9cbab7bc1934fe7/settings/target/structures/hIL2R_beta_gamma.pdb' \
  --output inputs/bc2-score/complex.pdb
tar -C inputs/bc2-score -cf inputs/bc2-score.tar complex.pdb
cat > inputs/bc2-score-parameters.json <<'EOF'
{"input_path":"complex.pdb","binder":"B","target":"A"}
EOF

.venv/bin/python invoke-scientific-batch.py \
  --model bindcraft2-analysis --tool submit_bindcraft2_analysis --operation score \
  --source inputs/bc2-score.tar --media-type application/x-tar --compression none \
  --entry-name campaign --semantic-type bindcraft2-input-tar/v1 \
  --parameters inputs/bc2-score-parameters.json \
  --idempotency-key bc2-public-complex-geometry-001 \
  --display-name 'BindCraft2 CPU structure metrics' \
  --output runs/bc2-score --wait-seconds 1800
```

The score operation reads one structure (`structure.pdb` is the default
`input_path`); explicit role parameters remove chain-order ambiguity. Native
coordinate-derived metrics do not reconstruct missing prediction confidence,
and they are not calibrated binding affinity, Kd, or Rosetta energy estimates.
The retained ordinary public analysis check exercised **rank**. Native CPU
score execution and this API contract have been checked separately; do not
describe this example as a completed current-release public score run until
its own result and artifacts are verified.

## Campaign tables and other analysis operations

For a completed campaign, keep its native directory structure inside the tar:

```text
campaign/
  1_Trajectories/!_Trajectories.csv
  2_Refolded/!_Refolded.csv
  3_Ranked/!_Ranked.csv
  ... native structures and metadata, when produced ...
```

Set `input_path: campaign` for campaign analysis. `rank` can select
`table: accepted`, `candidates` or `trajectories`, with
`metrics: ["i_pTM"]` only when that table actually contains `i_pTM`.
`top` bounds returned rows, not design generation. A missing metric is an
error; do not invent confidence values. Ranking supplied table values is not
refolding or fresh prediction. A structure-folder ranking computes the native
available structure metrics; prediction confidence cannot be inferred from
coordinates alone. Use `list_metrics: true` to inspect available native metrics.

`filter` takes native predicates in `where` and can use an archive-root-relative
`filters_file`. `include_rejected` retains rejected rows. `campaign-output`
produces the campaign summary; `archive` packages native campaign files.
These operations preserve their inputs and are not a campaign-resume command.
Optional parameters apply only to their own operation; do not send `metrics`
to `score` or `binder` to `filter`.

## The actual MCP arguments, polling and verified download

For each command, the helper uploads/finalizes the tar, creates a manifest
with `name`, `semantic_type` and the verified artifact reference, then uploads
that manifest. Its saved `request.json` contains the **exact typed tool
arguments**: `schema: fs2-serve.nebius.ai/scientific-run-request/v1`, the selected
`operation`, `service_class: customer-batch`, the finalized `input_manifest`,
the parameter object, client context and the stable idempotency key. Inspect
that file to reproduce a direct MCP call; never replace its artifact pointer
with a laptop path or invent an artifact ID. The named tools take these fields
directly, not an extra `request` wrapper.

The helper saves `receipt.json`, polls the accepted operation and verifies the
declared SHA-256/size of every downloaded artifact. If its wait ends first,
observe that same operation rather than starting another design:

```bash
.venv/bin/python invoke-scientific-batch.py \
  --observe-output runs/bc2-design --wait-seconds 1800
```

Select structures, tables and `bindcraft2-result/v1` from the verified output
manifest, not ordinal filenames. Inspect `science.outcome`, accepted-design
counts, failed/rejected trajectories and native settings before interpreting a
result. File integrity, computational acceptance and experimental binding are
three different claims.

Native details: [versioned settings reference](https://github.com/PacesaLab/BindCraft2/blob/d502f19a187a1bc8c05e833ca9cbab7bc1934fe7/docs/source/reference.md)
and [native analysis outputs](https://github.com/PacesaLab/BindCraft2/blob/d502f19a187a1bc8c05e833ca9cbab7bc1934fe7/docs/source/outputs.md).
