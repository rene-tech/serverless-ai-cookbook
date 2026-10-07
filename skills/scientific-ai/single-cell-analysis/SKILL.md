---
name: single-cell-analysis
description: Prepare raw-count AnnData and run durable hosted scVI/scANVI integration, annotation or reference mapping through REST/MCP. Use for large single-cell studies, training recovery, latent embeddings and label probabilities; do not imply an exposed differential-expression API.
license: Apache-2.0
---

# Single-cell analysis

Read `scientific-gateway`; discover App `scvi-scanvi` and its current public
schema. Prefer `scientific-batch-v1`, typed tool `submit_scvi_scanvi`, for real
studies. The older `integrate_single_cell_native`/`scvi-integrate.py` path is a
separate small-demo adapter with 64 MiB/100,000-cell limits. Those are **not**
limits of the new batch API; do not route a large study through that adapter.

## Inspect and choose the scientific method

1. Inspect the `.h5ad`: unique cell/gene IDs, sparse format, shape, available
   `obs` columns and raw counts in `X`, `raw.X` or a named `layers/<name>`.
   Check finite, nonnegative integer counts in bounded chunks, not just a small
   sample. Never silently replace counts with normalized/log-transformed data.
2. Use `method: scvi` for unsupervised integration or `method: scanvi` for
   annotation, with `mode: train`. Use `mode: map-query` with a matching retained
   reference archive and matching method. For scANVI select
   the real label column and explicit unlabeled category; a fully labeled
   training set is valid. Do not invent batch columns or biological labels.
3. Record seed, batch/label keys, counts source, HVG selection, latent dimensions,
   training epochs and early stopping. `max_epochs: null` uses scvi-tools' dataset
   heuristic; scANVI/query epochs are separate. Never shorten training or subset
   cells simply to make a tool finish. A visualization subsample is not a
   training subsample and must be labeled separately.
4. Select the live execution profile: routine single GPU with 128 GiB RAM or
   atlas with 256 GiB RAM, currently qualified on H100. Batch uploads currently
   accept up to 25 GiB; expanded matrix and training memory remain constraints.
   Eight admitted operations does not guarantee eight immediately available
   GPUs. Queued work retains its operation ID. API limits/schema take priority.

## Submit once, then recover the same operation

Upload files outside chat and submit immutable artifact references. Never put
HDF5/base64 or large matrices into MCP arguments. The full LibreChat workbench
ships a pinned copy of the platform's REST/MCP file client:

```bash
/opt/scientific-client/bin/python /opt/bionemo/scvi-batch.py \
  --input /workspace/my-study/counts.h5ad \
  --parameters /workspace/my-study/parameters.json \
  --output /workspace/my-study/run-001 \
  --idempotency-key my-study-run-001 --protocol mcp --wait-seconds 60
```

`parameters.json` is the model parameter object from the live batch schema,
not the entire submission envelope. Set its `output_prefix` to a study-specific
bucket prefix. A starting example is at
`/opt/bionemo/scvi-client/parameters.example.json`; inspect columns first.
For mapping add `--reference /workspace/prior-study/reference.tar.gz`.
Other MCP clients can use the same public upload/submit/status/result APIs;
installing this skill alone does not install a Python executor or client image.

Large uploads can take minutes. Run the helper through the workbench's managed
background execution, retain the handle/log, and observe it. Do not kill and
resubmit merely because a foreground tool wait expires. Exit **75** means a
durable operation is still pending (including result publication). Continue:

```bash
/opt/scientific-client/bin/python /opt/bionemo/scvi-batch.py \
  --output /workspace/my-study/run-001 --recover-only --wait-seconds 60
```

Keep the same output directory and API identity. Never submit a replacement
while a retained operation is queued/running. Inspect `client.log`, admission,
status and result receipts when there is an error. A failed scientific run is
not successful integration. Stop and report the native diagnostic.

## Validate and deliver

The batch path returns all-cell latent embeddings, cell IDs, training curves,
model/reference checkpoints, provenance and hashes. scANVI also returns predicted
labels and normalized label probabilities. UMAP is optional and can be sampled.
The helper checks every downloaded artifact, row alignment, finite values and
probability normalization before reporting success. Keep `output-validation.json`
and the operation ID with the study. The output `integrated.h5ad` preserves
selected count data and embeddings; it is not corrected expression by default.

These checks prove artifact consistency, **not biological accuracy**. Compare
batch mixing and biological conservation, and evaluate annotation on genuinely
held-out labels. Avoid reference leakage. Differential expression is not exposed
merely because upstream scvi-tools supports it.

Training recovery uses full Lightning checkpoints (including optimizer/state),
not GPU-process snapshots. Platform-recognized interruption can retry from those
checkpoints; a terminal failed/cancelled job is not a user-resumable GROMACS job.
Do not claim a GPU snapshot is a cache of a customer's fitted analysis.

Method documentation: https://docs.scvi-tools.org/en/stable/tutorials/index.html
