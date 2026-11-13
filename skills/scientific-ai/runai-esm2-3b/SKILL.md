---
name: runai-esm2-3b
description: Use ESM-2 3B protein scoring, representations, contacts, logits and masked completion through the Scientific AI REST API or typed MCP tools.
license: Apache-2.0
---

# ESM-2 3B

Evaluation candidate: native CPU scientific checks pass; GPU and production qualification remain pending. Discover `GET /v1/models/esm2-3b?workflow=score-variants` before submitting. ESM2-650M measurements are not 3B evidence.

Scientific version: `esm2-3b-476b6399`. Checkpoint: [`facebook/esm2_t36_3B_UR50D`](https://huggingface.co/facebook/esm2_t36_3B_UR50D/tree/476b639933c8baad5ad09a60ac1a87f987b656fc), revision `476b639933c8baad5ad09a60ac1a87f987b656fc`. It has 36 layers, width 2560 and 33 vocabulary tokens. Use advertised versions; the client pins this version.

## Portable example and owner storage

Use the bundle's [shared ESM client](../runai-esm2-650m/example.py), with `boto3` installed for upload. From this skill directory:

```sh
python ../runai-esm2-650m/example.py --model esm2-3b \
  --workflow score-variants --prepare-only --output ./new-esm3b-input
```

This creates a deterministic `input.tar.gz` offline: root-level `sequences.fasta` (ID `synthetic`, sequence `ACDEFGHIKLMNPQRSTVWY`) and `variants.csv`, including an identity variant. All six workflows use this fixture. `--negative` supplies a wrong WT residue for validation.

Set approved `SCIENTIFIC_AI_BASE_URL`, `SCIENTIFIC_AI_API_KEY`, `SCIENTIFIC_AI_REGION`, `SCIENTIFIC_AI_GPU`, plus `OWNER_S3_ENDPOINT`, `OWNER_BUCKET`, `OWNER_INPUT_PREFIX` and standard AWS credentials for your existing bound bucket. Run without `--prepare-only`, using a fresh output directory. Explicit placement is required while cost routing is unqualified.

The client discovers the schema, uploads, saves `submission.json` **before** its single POST, polls, and verifies result sizes/SHA256. The API token stays on the configured HTTPS scientific origin; redirects are refused and downloads use a separate unauthenticated client. Keep credentials out of archives. After lost acknowledgement, preserve the intent and reconcile its original idempotency key; rerunning creates another key. Keep `run.json` for polling after disconnects.

Reference the archive by owner key, SHA256 and size. Paths are archive-relative; `fasta_file` selects the FASTA. IDs must be unique. Inputs, scratch, checkpoints and outputs use owner storage and temporary private job PVCs. Final upload retries end after 300 seconds, followed by scratch deletion; report unsynced loss. Check discovered memory/output limits; sequences are not silently truncated.

## score-variants

CSV `variants.csv`: `id,sequence_id,mutations`. One-based mutations (`A1G`, `C2S:W19F`) must match WT FASTA. Choose default `masked-marginals`, `wt-marginals` or mutant-minus-reference `pseudo-log-likelihood`. Identity scores are zero; additive marginals do not model epistasis.

## score-sequences

Complete PLL and mean PLL/residue; omit `strategy` or choose `pseudo-log-likelihood`. Both scorers expose `batch_size`, `batch_tokens`, `precision` and explicit approximate `context_window`. Scores use natural logs; they are not calibrated affinity, ddG or clinical predictions.

## extract-representations

Layers 0–36; `per-token`, `mean`, `bos`. Default: layer **36**, per-token and mean. Shape `[residues,2560]`; mean excludes BOS/EOS/padding. The example selects `[0,18,36]` and all outputs. Load float32 NPZ with `allow_pickle=False`.

## predict-contacts

Native symmetric `[residues,residues]` contact probabilities, without a 3D structure or experimental claim.

## logits

All 33 native-token logits per residue and vocabulary. Optional `masked_positions: [{"sequence_id":"synthetic","positions":[2,5]}]` masks those one-based positions simultaneously.

## masked-completion

Supply masks for every sequence and `top_k` 1–33. Receive IDs, labels, probabilities and logits. These are conditional marginals, not joint decoding; preserve special-token labels.

## Typed MCP and durable jobs

Tools: `esm2-3b_score_variants`, `esm2-3b_score_sequences`, `esm2-3b_extract_representations`, `esm2-3b_predict_contacts`, `esm2-3b_logits`, `esm2-3b_masked_completion`. Read their schemas. Pass REST `version`, `parameters`, `inputs`, `region`, `gpu` and a saved `idempotency_key`; omit `model`/`workflow`. Poll with `md_run_status`, retrieve with `md_run_artifacts`, cancel with `md_run_cancel`. REST: `GET /v1/runs/{id}`, `GET /v1/runs/{id}/artifacts`, `POST /v1/runs/{id}/cancel`. Never submit an existing run again.

Inspect structured error stage/field/retryability/correlation ID. Fix deterministic failures before a new request. Interruption restarts the whole unfinished batch under its original owner/version/deadline. Partial-row and positive-progress cross-region recovery are unqualified; completed verified owner-bucket results remain durable.

ESM code and this checkpoint declare MIT; applicable dependency/runtime notices still apply. This guide grants no production or clinical clearance.
