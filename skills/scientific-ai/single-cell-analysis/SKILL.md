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

For batch fields call `get_model_schema` with
`{"model_id":"scvi-scanvi","tool_name":"submit_scvi_scanvi"}`. The exact
protocol selector is `scientific-batch-v1`; current discovery also accepts the
`scientific-batch` execution-family selector. A compact
discovery call with `summary_only: true` lists both native and batch tools.

## Inspect and choose the scientific method

1. Inspect the `.h5ad`: unique cell/gene IDs, sparse format, shape, available
   `obs` columns and raw counts in `X`, `raw.X` or a named `layers/<name>`.
   Check finite, nonnegative integer counts in bounded chunks, not just a small
   sample. For large matrices inspect HDF5 datasets directly with `h5py` or use
   tested disk-backed slices; never load a whole atlas into the client merely
   because backed slicing failed. AnnData may eagerly load named layers even
   when its main matrix is backed. Never silently replace counts with
   normalized/log-transformed data.
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

### Portable input layout

`train` requires exactly one finalized manifest entry: `anndata`, semantic type
`anndata-counts/v1`, MIME `application/x-hdf5`, compression `none`. Its payload is
the actual `.h5ad` file, not a tar or a CSV. Select raw counts with
`counts_source: "X"`, `"raw.X"` or `"layers/COUNTS_LAYER"`; batch/label keys must
name real `obs` columns. A parameter-file shape is
`{"schema":"fs2-serve.nebius.ai/scvi-workflow-request/v1","method":"scvi","mode":"train","counts_source":"X"}`;
inspect the input before choosing those values.

`map-query` requires both `anndata` and `reference`. Upload the reference as
`scvi-reference/v1`, MIME `application/x-tar`, compression `gzip`; its native
archive contains `reference.json` and model files at the root. Use an exported
reference with the matching scientific method/runtime. Do not invent those
model files, add a wrapper directory, or put H5AD inside the reference archive.
The `reference` entry is not allowed in `train` mode. The complete live contract
publishes these rules as `required_if`, `allowed_if` and `exact_entries_by_mode`.

On a laptop, install the separate portable file client. `upload-artifact.py`
can finalize each file independently with its exact MIME/compression. Construct
one canonical manifest from those actual `artifact.json` receipts:

```python
import json
from pathlib import Path

manifest = {
    "schema": "fs2-serve.nebius.ai/scientific-artifact-manifest/v1",
    "entries": [
        {"name": "anndata", "semantic_type": "anndata-counts/v1",
         "artifact": json.loads(Path("uploads/anndata/artifact.json").read_text())},
        {"name": "reference", "semantic_type": "scvi-reference/v1",
         "artifact": json.loads(Path("uploads/reference/artifact.json").read_text())}
    ]
}
Path("manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
```

This example is for `map-query`; omit `reference` for training. Finalize that
manifest with MIME `application/vnd.fs2.scientific-manifest+json` and compression
`none`. Call `submit_scvi_scanvi` with top-level `request` and `idempotency_key`;
the request contains `operation: "fit-transform"`, the finalized manifest pointer
and your model `parameters`. The generic one-source batch helper does not assemble
this two-entry mapping manifest: use this complete-manifest typed-MCP route or
the existing workbench `scvi-batch.py --reference` path. Do not submit a mapping
request with only the H5AD entry.

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

The file client waits up to 900 seconds on an explicit key-capacity rejection
before admission, retaining the exact request and idempotency key. This is not a
queued GPU operation yet. It does not retry scientific/validation errors or
invent another job. If that wait expires, retain uploads and the study receipt;
retry the same original invocation once a slot is available. `--recover-only`
requires an admitted operation ID and is not the pre-admission retry command.

Large uploads can take minutes. Run the helper through the workbench's managed
background execution, retain the handle/log, and observe it. Do not kill and
resubmit merely because a foreground tool wait expires. Exit **75** means a
durable operation is still pending (including result publication). Continue:

```bash
/opt/scientific-client/bin/python /opt/bionemo/scvi-batch.py \
  --output /workspace/my-study/run-001 --recover-only --wait-seconds 60
```

Exit 75 stops the local helper. The remote job continues, but its local files
do **not** download themselves afterwards. If the user asked for completed
results, retain a managed background recovery command with an appropriate wait
budget, or recover the same operation on their next request. Distinguish
remote completion, bucket export and verified local download. Do not promise
an automatic notification or local delivery unless a running task provides it.

Keep the same output directory and API identity. Never submit a replacement
while a retained operation is queued/running. Inspect the log path returned by
the helper (also in `workbench.json`), admission,
status and result receipts when there is an error. A failed scientific run is
not successful integration. Stop and report the native diagnostic.

Each attempt has a separate file under `logs/`: the S3 mount does not support
appending to an existing file. Old `client.log` files remain historical evidence.
Recovery is supported directly in the mounted study directory; do not move its
receipts to scratch or invent a new operation to work around storage errors.

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
