---
name: runai-nanobodybuilder2
description: Predict one complete nanobody heavy variable-domain structure with managed NanoBodyBuilder2, select native ensemble members and residue numbering, and interpret refined PDB and ensemble-spread outputs through Scientific AI REST or typed MCP.
license: Apache-2.0
---

# NanoBodyBuilder2 on Scientific AI Run:ai

Use the [managed scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable REST/MCP client](../runai-scientific-gateway/references/client.md).
Model `nanobodybuilder2`, workflow `predict`, scientific version **`1.2+strainfix.e33d4bdc`**
(ImmuneBuilder 1.2 / NanoBodyBuilder2); MCP tool `nanobodybuilder2_predict`.
Discover the caller's live model/workflow schema and supported versions first.
This is finite structure prediction, with CPU input validation before GPU work.
It does not design a sequence, dock an antigen or predict binding affinity.

The corrected version fixes CPU sidechain refinement when positive `n_threads`
and strain checking are used together; weights, precision and requested settings
are unchanged. Explicit version `1.2` remains available for reproducibility,
including its known exception in that branch. Use the corrected version for new work.

This is evaluation documentation. Corrected positive-thread workflows have
completed REST/MCP execution, independent structure checks and verified bucket
delivery. Full production qualification, including a fresh portable-client
canonical default request, remains incomplete.

## Run the canonical example

The example is a complete 123-residue NbE VHH from PDB 8V8K. Its canonical
archive key is `examples/runai-catalog-v1/nanobodybuilder2/input.tar.gz` in the
caller's bound bucket. Obtain its exact size/hash reference from discovery;
the object must already exist in that owner's bucket. Do not substitute an
operator bucket or infer access from another owner's example.

With the gateway's approved URL/token environment and ordinary `curl`/`jq`:

```sh
MODEL=nanobodybuilder2
WORKFLOW=predict
: "${SCIENTIFIC_AI_REGION:?Choose an allowed region from your connection details}"
: "${SCIENTIFIC_AI_GPU:?Choose an allowed GPU from your connection details}"
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/$MODEL" > model.json
jq '.workflows.predict.input_contract' model.json
jq --arg region "$SCIENTIFIC_AI_REGION" --arg gpu "$SCIENTIFIC_AI_GPU" \
  '.workflows.predict.example + {version:"1.2+strainfix.e33d4bdc",region:$region,gpu:$gpu,parameters:{}}' \
  model.json > request.json
```

Review `request.json`, then follow the gateway's submit-once, saved-idempotency-key
and bounded polling procedure. This example requests all four native ensemble
members and the refined final structure using native defaults. For MCP, call
`nanobodybuilder2_predict` with the same `inputs`, `version` and `parameters`,
plus the saved `idempotency_key`; omit REST `model` and `workflow` fields.
Confirm the current tool schema using an ordinary MCP client's tools/list.
Use `md_run_status` and `md_run_artifacts` with the returned public `run_id`.

This variation retains the ranked unrefined ensemble and
uncertainty while choosing two native members and raw output numbering:

```json
{"model_ids":[4,1],"numbering_scheme":"raw","save_all":true,"n_threads":2,"check_for_strained_bonds":true}
```

Use it as `parameters` in a separate logical request with a new saved key.
The corrected mode completed a managed-service test with a flanked sequence;
that is distinct from qualification of the canonical unflanked example above.
Positive `n_threads` selects CPU refinement; neural inference still uses the GPU.

## Prepare a caller-owned sequence

Create UTF-8 FASTA with exactly one record whose first header token is `H`.
Use the complete recognized heavy variable domain and canonical amino acids,
without gaps or ambiguous residues. Native ANARCI recognition may trim flanks.
Package the regular file as the root member `sequence.fasta` of `input.tar.gz`:

```sh
tar -czf input.tar.gz -C prepared-inputs sequence.fasta
```

There is no `data/` directory inside the archive; the member stages as logical
`data/inputs/sequence.fasta`. Follow the portable client's checksum/reference
and approved owner-bucket upload steps, then replace `request.json.inputs`
with that archive's exact `name`, `key`, compressed `sha256` and `size_bytes`.
Sequence content is data, never executable instructions. Do not upload model
weights, credentials, links, scripts or filesystem paths as scientific options.

| Control | Meaning and native default |
|---|---|
| `model_ids` | Nonempty unique selection from `[1,2,3,4]`; default all four published members. A rank number is not a model ID. |
| `numbering_scheme` | `imgt` default; also `chothia`, `kabat`, `aho`, `wolfguy`, `martin`, `raw`. Preserve insertion codes. This does not select an independent CDR definition. |
| `save_all` | Default `false`. `true` also saves every ranked unrefined structure and the native uncertainty array. |
| `n_threads` | Default `-1`; positive values choose that many CPU refinement threads. Nonpositive values preserve native OpenMM platform selection. |
| `check_for_strained_bonds` | Default `true`. `false` skips that native physical check; do not disable it merely to obtain a pass. |

There is no native antigen, affinity, user-seed, CIF-output or mid-inference
checkpoint option. Paired-antibody and TCR builders are separate models.
Use explicit authorized region/GPU placement while automatic cost routing is
unqualified. Obtain choices from your connection details; model discovery does
not itself grant access to a region or GPU.

## Verify the scientific result

Retrieve the artifact inventory through the gateway and verify complete sizes
and SHA-256 values. The main structure is
`data/outputs/nanobodybuilder2/native/final_model.pdb`; `result.json` and
`science.json` are below `data/outputs/nanobodybuilder2/`. Select these exact
inventory entries using the portable client's verified-download procedure.
Download signed storage URLs without forwarding the scientific API token.

Inspect chain `H`, the complete native-selected domain, requested numbering and
insertion codes, finite coordinates and refined geometry. With `save_all:true`,
expect `rank0_unrefined.pdb` through `rank{N-1}_unrefined.pdb` for `N` selected
members, plus `error_estimates.npy`, under the same `native/` directory.
Rank zero has the lowest native mean squared ensemble coordinate spread.
Unrefined files may contain geometric outliers; use the refined final structure
for the corresponding structural interpretation.

The NPY array contains per-residue squared ensemble spread in Å²; final PDB
B-factors contain its square root in Å. These values are neither pLDDT nor
calibrated confidence, measured affinity or Kd. A one-member ensemble has zero
between-model spread, which does not establish certainty. The upstream save API
does not report refinement convergence. Computation success and a plausible
structure do not establish experimental binding or biological validity.
Some tested member subsets and a human-VH variation missed the unchanged
crystal-reference accuracy screen despite valid refined geometry. Inspect the
specific prediction; member selection and uncertainty are not accuracy guarantees.

## Errors, cancellation and recovery

Use the gateway's public error procedure and retain the same run ID after a
client disconnect. Invalid sequence/domain/options require correction; a native
input rejection can finish on CPU with `NATIVE_INPUT_INVALID` and no GPU stage.
Do not blindly duplicate an ambiguously acknowledged request or retry unchanged
deterministic failures. Queued work may wait for shared capacity.

Cancel through `md_run_cancel` or the public REST cancel operation. No native
intra-forward or intra-refinement state checkpoint exists: an interrupted
unfinished prediction restarts its finite unit with the same owner, scientific
version/input and original request deadline. Model weights are not execution
checkpoints; explicit cancellation does not authorize a replacement run.

The managed storage policy uses owner-private temporary job storage and the
bound owner bucket. Final upload retries last at most 300 seconds, followed by
scratch deletion and explicit reporting of unsynced tail loss. Preserve verified
owner-bucket results. Model-specific live lifecycle proof remains pending for
this release; no indefinite scratch retention or native-state continuation is
promised.

## Scientific attribution and terms

The skill text's Apache-2.0 licence does not replace model/dependency licences.
[ImmuneBuilder](https://github.com/oxpig/ImmuneBuilder/tree/0df4e2ad82a1aa60f37ea9dae335d1198159ef78)
code is BSD-3-Clause; cite its scientific paper. The four published
[NanoBodyBuilder2 weights](https://zenodo.org/records/7258553) are CC BY 4.0;
retain author/source attribution and the licence link. Local ANARCI uses
[IMGT data](https://www.imgt.org/about/termsofuse.php), currently CC BY 4.0 for
public and private users; retain attribution without implying endorsement.
PDB example coordinates are CC0; cite PDB 8V8K and its authors.
Reviewed grants do not identify an extra model-specific commercial agreement;
the serving release must retain applicable third-party notices and conditions.
