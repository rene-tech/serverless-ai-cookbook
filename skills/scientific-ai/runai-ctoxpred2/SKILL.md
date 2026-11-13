---
name: runai-ctoxpred2
description: Screen small molecules for hERG, Nav1.5 and Cav1.2 inhibition using CToxPred2 through the managed Scientific AI REST or typed MCP workflow. Use for computational ion-channel screening, including ordered batches and CSV/SDF libraries.
version: 0.1.0
license: Apache-2.0
---

# CToxPred2

Check authorized model discovery before submitting. Customer acceptance and commercial hosted-use qualification remain incomplete.

## screen-molecules

Use scientific version `2a31aa119e27b6b69a5588d18a01f2a27fef4524` when discovery
reports it qualified. This is short stateless CPU inference. An interrupted
unfinished operation recomputes under its original version and deadline; model
weights are not resumable execution checkpoints.

1. Set `SCIENTIFIC_AI_URL` to your configured service origin and
   `SCIENTIFIC_AI_TOKEN` from your approved secret store. Never paste credentials
   into molecular input, chat, logs or examples.
2. Discover `GET /v1/models?limit=100` and the `ctoxpred2` workflow schema. Use only your
   granted regions and the owner-bucket input/output mechanism it advertises.
3. Prepare an owner input archive with `settings.json` at its root. Supply one
   of `smiles`, ordered `molecules`, `csv`, `sdf`, or an archive-relative
   `input` plus `input_format` (`csv`, `sdf`, or native request `json`). See
   [the input example](references/settings.json). Input paths are relative to
   the archive root, without absolute paths, URLs or `..` components.
4. Upload the archive using standard S3 tooling and your existing bucket-scoped
   credentials. Compute its SHA-256 and byte count. Keep signed URLs private;
   use an unauthenticated client for signed downloads.
5. Submit `POST /v1/runs` with `model: ctoxpred2`, workflow `screen-molecules`,
   the discovered version, one `inputs` entry named `input.tar.gz` containing
   its actual owner key/hash/byte count, and `parameters: {}`. The example
   [portable client](references/screen.py) handles submission, polling and
   artifact discovery after you supply those actual values. API/MCP parameters
   explicitly override settings; omission preserves settings. Use discovery's
   typed `ctoxpred2_screen_molecules` MCP tool for the equivalent submission,
   then `md_run_status` and `md_run_artifacts` with the returned `run_id`.
6. Save the full request and one stable idempotency key in a private durable intent
   file **before** POST. The portable client requires `--state` and
   `--idempotency-key`; reuse both unchanged after an ambiguous response. Once
   acknowledged, keep polling the saved run ID instead of creating a new intent.
   Poll the durable run ID after acknowledgement. Inspect structured terminal
   errors; retry deterministic input failures only after correction. Use the
   advertised cancel operation when stopping unwanted work. Client disconnection
   alone does not cancel accepted work. Queueing and cold CPU startup count
   separately from model inference.
7. Retrieve the owner-delivered `predictions.json`, `predictions.csv`, and
   `science.json`, checking the artifact manifest's hashes and byte counts.
   Every input row retains its index and ID. Mixed invalid/valid input yields
   partial scientific output; invalid rows have errors and no predictions.

Prepare and upload the included synthetic example with standard S3 tooling, then
run the portable client. Set the placement, scientific version, owner bucket/key
and one stable request key from your connection details; retain that key on retry.
The commands use your existing AWS credential environment/profile:

```sh
tar -czf input.tar.gz -C references settings.json
aws --endpoint-url "$OWNER_S3_ENDPOINT" s3 cp input.tar.gz "s3://$OWNER_BUCKET/$OWNER_INPUT_KEY"
python references/screen.py --state ./ctox-intent.json --idempotency-key "$SCIENTIFIC_AI_REQUEST_KEY" --key "$OWNER_INPUT_KEY" --archive ./input.tar.gz --version "$SCIENTIFIC_AI_VERSION" --region "$SCIENTIFIC_AI_REGION"
```

`rf-ssl` is the deterministic default. `dl-sl` uses MC dropout; its supported
`forward_iterations` values are 100 (default), 500 and 1000, and
`dropout_rate` values are 0.1, 0.2 (default) and 0.3. These controls affect only
`dl-sl`. `seed` defaults to 0 and accepts integers 0–2147483647. Reproduce the
same ordered records, selected endpoints and 32-record chunk layout; splitting
a library changes MC draws. MC standard deviation is uncalibrated dispersion.

Select any subset of `hERG`, `Nav1.5`, and `Cav1.2` with `endpoints`, or omit it
for all three. CSV defaults to a `smiles` column; optional `smiles_column` and
`id_column` choose your columns. SDF IDs use `id_column` or `_Name`; coordinates
do not affect this 2D model. Preserve intended stereochemistry. Salts are flagged,
not stripped; no extra neutralization or tautomer standardization is applied.
IDs must be unique even for repeated structures. The current contract allows
1,000 records per operation and 16 MiB characters per inline CSV/SDF; use
owner-file input for larger transports within the discovered storage budget.

Class 1 is the upstream model’s blocker class. Positive-class and predicted-class scores are model outputs,
not calibrated clinical arrhythmia risk or proof of human safety. Native export
also retains InChIKey and RDKit molecular properties MW, AlogP, HBA, HBD, MPSA,
ROTB, AROMS and ALERTS. A valid output is not experimental efficacy evidence.

Reference: [CToxPred2 source](https://github.com/issararab/CToxPred2) and
[the scientific paper](https://doi.org/10.1021/acs.jcim.4c01102).

For typed MCP, call `ctoxpred2_screen_molecules` with this shape after replacing
the discovery and owner-input values, and saving that exact intent first:

```json
{"version":"<qualified-scientific-version>","region":"<authorized-region>","gpu":"cpu","inputs":[{"name":"input.tar.gz","key":"<owner-input-key>","sha256":"<actual-sha256>","size_bytes":206}],"parameters":{},"idempotency_key":"<saved-stable-request-key>"}
```

Use the archive's actual byte count. Optional overrides belong inside
`parameters`, for example `{"method":"dl-sl","forward_iterations":500,
"dropout_rate":0.1,"seed":17}`. For REST, put the saved key in the
`Idempotency-Key` header. Client timeouts preserve the accepted operation;
use `md_run_cancel` or `POST /v1/runs/{run_id}/cancel` to request cancellation.
