---
name: runai-admet-ai
description: Screen small molecules with managed ADMET-AI 2.0.1, including learned assay endpoints, molecular descriptors, owner-file batches and per-row errors through Scientific AI REST or MCP.
license: Apache-2.0
---

# ADMET-AI on Scientific AI Run:ai

Read the shared [scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client](../runai-scientific-gateway/references/client.md) for secure
credentials, owner-bucket uploads, idempotency, polling and verified downloads.
Use `SCIENTIFIC_AI_URL` and the caller's `SCIENTIFIC_AI_TOKEN`; a native Run:ai
dashboard credential is not a managed scientific API token. No new account,
bucket, credentials or local scientific-engine installation is required.

Current evidence covers bounded CPU research execution. Commercial hosting is
blocked by unresolved bundled-data/dependency rights. GPU execution and plotting
are not qualified; scientific version `2.0.1` does not imply a qualified GPU build.
This skill grants no model or data licence and makes no clinical-safety claim.

## screen-molecules

Discover the authorized contract and copy its versioned example:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/admet-ai?workflow=screen-molecules" > model.json
jq '.workflows["screen-molecules"].example' model.json > request.json
```

The referenced archive must exist in **your own** bound bucket. The example
contains twelve ordinary molecules in `settings.json`, preserving IDs and
stereochemistry, and requests the full panel. Use the shared client's
submit/poll/download steps with that request. The expected result has twelve
successful rows, 52 values per row and the same IDs/order; a shape check alone
does not validate predictions on new chemistry.

For a separately keyed endpoint-subset variation:

```sh
jq '.parameters.endpoints=["hERG","molecular_weight","stereo_centers"]' \
  request.json > request-subset.json
```

Use a new request directory and idempotency key for the changed body. Endpoint
selection changes returned outputs; the current engine still computes its full
panel internally. Omitted or explicit-null `endpoints` selects all 41 learned
properties/assays and 11 calculated descriptors/alerts.

In MCP, discover `md_models` with `{"model":"admet-ai","detail":true}`. Call
`admet-ai_screen_molecules` with the same `version`, `inputs`, `parameters` and
saved `idempotency_key`, omitting REST `model` and `workflow`. Poll `md_run_status`
and retrieve `md_run_artifacts` using the exact returned public run ID. Do not
create a second request after a client disconnect or ambiguous submission.

## Supply your own molecules

Always provide `input.tar.gz` with archive-root `settings.json`. Exactly one
non-null source supplies molecular rows: `smiles`, `molecules`, an inline CSV/SDF
field where advertised, or a referenced input file. Keep settings and referenced
files together without a `data/` wrapper; no scripts, links or executable state.
Use the shared portable client's upload/reference steps and replace the example
`inputs` with your exact owner object key, compressed SHA-256 and byte count.

A settings-only archive can contain:

```json
{"smiles":"CCO","endpoints":["molecular_weight","hERG"]}
```

For a CSV archive containing `settings.json` and `molecules.csv`:

```json
{"input":"molecules.csv","input_format":"csv","smiles_column":"smiles","id_column":"id","endpoints":["molecular_weight","hERG"]}
```

Here `input` is **archive-relative**, not `data/inputs/molecules.csv`. The managed
worker resolves it inside this run's private input directory. SDF uses its
requested identifier property or `_Name`; coordinates do not influence this 2D
predictor. A referenced native JSON request uses `input_format:"json"` and the
same discoverable scientific schema. Follow the live schema for accepted fields.

Explicit API scientific controls override file settings; omitted fields preserve
them and explicit null clears a file setting. Changing source type requires
clearing the prior source: for example, overriding the seeded twelve-molecule
file with `parameters:{"molecules":null,"smiles":"CCO"}`. Do not accidentally
combine two sources. Preserve charges, salts, stereochemistry and unique row IDs;
no automatic salt stripping, neutralization or tautomer conversion is performed.
Repeated structures with different IDs remain independent rows.

## Inspect results and failures

Retrieve and verify the actual inventory using the shared client. Scientific
outputs are `data/outputs/screen/predictions.json`, `predictions.csv` and
`science.json`. Check row order/IDs, canonical structures, per-row status and
errors, endpoint labels, units and species. Invalid rows remain with errors and
no predictions; mixed batches can complete with partial scientific output, while
a wholly invalid batch fails input validation. Classification scores are not
human-safety determinations. Do not silently discard failed rows.

Requests are bounded at 1,000 molecules; larger libraries need stable batches
with distinct request keys and retained run IDs within the documented owner
queue. Short jobs may queue. Stateless interrupted work recomputes through the
existing lifecycle; no optimizer or simulation-state checkpoint is available.
Final-upload retries are bounded to 300 seconds, then temporary scratch is deleted
even during a bucket outage and any unsynced data loss must be reported.

DrugBank percentiles, ATC-filtered references and reference plots are not enabled
by this qualification. Code licensing is not permission to use or redistribute
restricted reference data. Do not compare v2 timings/predictions with published
v1 results as though they were the same trained ensemble. Keep private image,
registry and native deployment identities out of customer outputs and skills.
