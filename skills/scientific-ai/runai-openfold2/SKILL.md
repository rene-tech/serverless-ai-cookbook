---
name: runai-openfold2
description: Predict independent monomer structures with managed OpenFold2, supply precomputed A3M or Stockholm alignments, choose supported seeds and recycling, and retrieve complete owner-bucket PDB/ModelCIF and confidence artifacts through Scientific AI REST or typed MCP.
license: Apache-2.0
---

# OpenFold2 on Scientific AI Run:ai

Evaluation documentation. Native structure checks and owner delivery have passed
on H100, L40S, H200 and B200. Full public-client, feature, recovery, security and
commercial release acceptance remains incomplete. Use only the live authorized
qualification grant; catalog presence does not establish production readiness.

Use the [managed scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable REST/MCP client](../runai-scientific-gateway/references/client.md).
Discover `GET /v1/models/openfold2?workflow=predict-structure`.
Model `openfold2`, workflow `predict-structure`, MCP tool
`openfold2_predict_structure`. The scientific version is
`OpenFold2-be2ec184-no-templ-ptm1`: OpenFold model_3_ptm, no-template pTM parameter
set1. This is a finite managed job, not an NVIDIA NIM or a design/binding-affinity model.

## predict-structure

### Prepare scientific inputs

Read the live workflow's `input_contract` and top-level `settings_input_schema`.
Create an owner-controlled `input.tar.gz` containing root member `request.json`
and every referenced optional alignment. Do not put a `data/` prefix, symlink,
script, weights or credential in the archive. Member paths resolve relative to
the archive root; `bfd_uniclust_hits.a3m` refers to that exact member, not a server path.

For a single monomer, `request.json` can contain:

```json
{"input_id":"known-1UBQ","sequence":"MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG","msa_file":"bfd_uniclust_hits.a3m","output_formats":["pdb","modelcif"]}
```

The sequence uses canonical uppercase amino acids. Native length domain is1–1024;
consult live readiness before assuming every boundary is qualified. Without
`msa_file`, the model uses a query-only dummy MSA; that can substantially reduce
accuracy. Supplied alignments must have an aligned first query exactly equal to
the requested sequence. Native parsers handle lowercase A3M insertions and
Stockholm syntax. Every aligned row must match query length and native alphabet.
Each file is limited to16MiB UTF-8,8192 input rows and8,388,608 aligned cells.
Oversized/malformed files fail CPU admission; they are never silently trimmed.

For independent proteins, replace single `input_id`/`sequence`/`msa_file` with
`targets:[{"input_id":"first","sequence":"..."}, ...]`; identifiers must be
unique and every target can reference its own MSA. This does not model a multimer
complex. Do not use ellipses as actual sequence input. Complete targets become
separately durable units; an interrupted unfinished target recomputes.

| Control | Meaning and native default |
|---|---|
| `selected_models` | Exactly `[1]`; only this weight variant is present. |
| `relax_prediction` | Exactly `false`; this runtime has no relaxation dependencies. |
| `model_seed` | Torch RNG seed, default1. |
| `data_seed` | NumPy RNG seed, default0. |
| `recycling_steps` | Integer0–32 native recycling iterations, default3. Keep3 until another value is live-qualified. |
| `output_formats` | Nonempty unique selection from `pdb`,`modelcif`; default `pdb`. Complete confidence JSON is always written. |

Native FeaturePipeline keeps512 clustered and5120 extra MSA row capacities,
seeded sampling/masking and per-recycle resampling. Input/unique row counts are
not necessarily the active clustered model rows; inspect actual per-recycle
counts in the result. The adapter does not change native precision or MSA caps.
Do not infer bitwise reproducibility across GPU architectures from RNG seeds.

Templates, other checkpoints/ensembles, multimer/SoloSeq, external MSA generation
and structural relaxation are not supplied by this exact runtime. Unsupported
controls are rejected; do not guess hidden options or send executable config.

## Submit through REST or MCP

Upload the archive with standard S3 tooling and your scoped owner-bucket
credentials, or use an already provisioned example in that same bound bucket.
Use the complete compressed archive SHA256 and byte count in
`inputs:[{"name":"input.tar.gz","key":"<owner key>","sha256":"<64 hex>","size_bytes":123}]`.
Those placeholders describe the fields; obtain real values from your file.
No legacy scientific manifest or container-local upload helper is required.

The canonical supplied example is ubiquitin,76 residues with a provided MSA.
Its archive contains root `request.json`, `bfd_uniclust_hits.a3m`, `ATTRIBUTION.txt`
and `LICENSE`. Its referenced object must exist in your bound bucket; another
owner's example does not grant access. With ordinary `curl`/`jq` and the gateway's
approved URL/token environment, prepare the complete default request:

```sh
: "${SCIENTIFIC_AI_URL:?Set the scientific API base URL}"
: "${SCIENTIFIC_AI_TOKEN:?Load your access token securely}"
: "${SCIENTIFIC_AI_REGION:?Choose an allowed region}"
: "${SCIENTIFIC_AI_GPU:?Choose an allowed GPU}"
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/openfold2?workflow=predict-structure" > model.json
jq --arg region "$SCIENTIFIC_AI_REGION" --arg gpu "$SCIENTIFIC_AI_GPU" \
  '.workflows["predict-structure"].example + {version:.default_version,region:$region,gpu:$gpu}' \
  model.json > request.json
```

Review that request, then follow the gateway's submit-once, saved-key, bounded
polling and checksum-verified artifact-download procedure. Native inference of
this known positive control has passed independent1UBQ structure checks; public
REST/MCP qualification of the matching deployment must be stated separately.
Choose explicit allowed region/GPU from your grant while automatic cost routing
is unqualified. Read tokens from environment or an approved secret store, never
an operator credential or inline chat. Submit once using the gateway's saved
idempotency-key procedure, with `model`, `workflow`, qualified `version`,
`inputs`, `region`, `gpu` and optional `parameters`. Explicit API parameters
override file controls; replacing `targets` removes file single-sequence fields.

For MCP, use the same typed `inputs`, `parameters`, `version`, `region`, `gpu`
and `idempotency_key`; omit REST `model`/`workflow`. Confirm tools/list first.
Use `md_run_status` and `md_run_artifacts`, or the public REST run operations,
with the returned public run ID. This works with ordinary clients; LibreChat is
optional. Queued work can outlive a client connection. Recover the original
accepted ID after a timeout; do not issue a fresh duplicate scientific request.

## Verify results and errors

On verified success, retrieve the artifact inventory and verify byte counts and
SHA256s before interpreting results. Download signed artifact URLs with a client
that does not forward the Scientific API bearer token. Standard authorized S3
access to the owner's bucket is also supported; never guess another run's prefix.

Each `data/outputs/target-NNNNNN/prediction.json` contains the original target
label, scientific version, full PDB, per-residue pLDDT0–100, fullN×N PAE in
angstrom, pTM0–1, settings, MSA source/input/unique/native feature counts and
measured timings. Selected `structure.pdb` and/or `structure.cif` appear beside
it. PDB B-factors encode pLDDT, not crystallographic displacement. Confidence,
valid geometry or successful computation do not demonstrate experimental
accuracy or binding. Review uncertainty and task-relevant independent references.

Read structured errors, including `field`, `rule`, `expected`, `retryable` and
`next_action`; fix deterministic inputs instead of blindly retrying. CPU admission
can fail with `NATIVE_INPUT_INVALID` without starting a GPU. Cancellation uses
the public run cancel operation; acknowledgement is not proof that GPU work and
scratch deletion are already complete. Confirm terminal state and delivery.

Private per-job scratch is synced to the authorized owner bucket. On completion,
failure or stop, final-upload retries last at most300s, then the temporary PVC,
PV and backing disk are deleted. Unsynced tail loss is reported; recovery uses
only verified owner-bucket data. Recovery is implemented at completed target
boundaries; cross-region qualification is pending. An unfinished target
recomputes with the original settings and deadline. No in-flight neural-state
restoration is promised. Other users cannot
read/control your runs, artifacts, checkpoints or storage. Administrators do not
gain customer-data access merely by seeing operational metadata.

## Scientific attribution

OpenFold code is Apache2; no-template pTM weights are CC BY4.0. Retain source,
weight and scientific-paper attribution. The stereo-chemical reference table is
from OpenStructure under LGPL3; service component notices remain applicable.
The supplied1UBQ example uses CC0 PDB reference attribution and an unchanged
OpenProteinSet alignment under CC BY4.0. Its coordinates are not inference input.
Do not infer commercial, clinical or security clearance from catalog presence;
the deployed release must close its whole-runtime rights and acceptance gates.
