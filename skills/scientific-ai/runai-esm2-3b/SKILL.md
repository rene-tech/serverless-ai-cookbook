---
name: runai-esm2-3b
description: Use ESM-2 3B protein scoring, representations, contacts, logits, masked completion, attention maps and masked-token loss through the Scientific AI REST API or typed MCP tools.
version: 0.3.0
license: Apache-2.0
---

# ESM-2 3B

All eight workflows are qualified for commercial nonclinical research on L40S, H100, H200, B200 and RTX PRO 6000. Discover `GET /v1/models/esm2-3b?workflow=score-variants` before submitting; the deployed contract governs availability. This is not clinical clearance or HIPAA/SOC certification.

Scientific version: `esm2-3b-476b6399`. Checkpoint: [`facebook/esm2_t36_3B_UR50D`](https://huggingface.co/facebook/esm2_t36_3B_UR50D/tree/476b639933c8baad5ad09a60ac1a87f987b656fc), revision `476b639933c8baad5ad09a60ac1a87f987b656fc`. It has 36 layers, width 2560 and 33 vocabulary tokens. Use advertised versions; the client pins this version.

## Portable example and owner storage

Use the bundle's [shared ESM client](../runai-esm2-650m/example.py), with `boto3` installed for upload. From this skill directory:

```sh
python ../runai-esm2-650m/example.py --model esm2-3b \
  --workflow score-variants --prepare-only --output ./new-esm3b-input
```

This creates a deterministic `input.tar.gz` offline: root-level `sequences.fasta` (ID `synthetic`, sequence `ACDEFGHIKLMNPQRSTVWY`) and `variants.csv`, including an identity variant. All eight workflows use this fixture. `--negative` supplies a wrong WT residue for validation.

Set approved `SCIENTIFIC_AI_BASE_URL`, `SCIENTIFIC_AI_API_KEY`, `SCIENTIFIC_AI_REGION`, `SCIENTIFIC_AI_GPU`, plus `OWNER_S3_ENDPOINT`, `OWNER_BUCKET`, `OWNER_INPUT_PREFIX` and standard AWS credentials for your existing bound bucket. Run without `--prepare-only`, using a fresh output directory. Supply authorized region/GPU constraints, or add `--auto-place` to fill missing placement fields; unset both constraints to choose across authorized regions. Routing uses measured full-VM on-demand estimates for default float32/512-residue reference requests and available capacity. Estimates exclude CPU preflight, image pull, Pod startup, API queues and delivery; they are neither invoices nor a cheapest-GPU guarantee for every input or precision.

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

## attention-maps

Choose transformer `layers` 1–36 (default 36) and zero-based `heads` 0–39 (default 0). Float32 NPZ shape is `[selected_heads,residues+2,residues+2]`, including BOS/EOS. These eager attention probabilities are not contact probabilities or calibrated biological interactions. Select matrices within discovered memory/output budgets.

## masked-token-loss

Supply masks for every sequence. Requested sites are masked simultaneously; original FASTA residues at exactly those sites are supervised labels, excluding BOS/EOS and all other positions. The native mean cross entropy per sequence uses natural-log units; it is distinct from complete PLL or biochemical free energy.

## Typed MCP and durable jobs

Tools: `esm2-3b_score_variants`, `esm2-3b_score_sequences`, `esm2-3b_extract_representations`, `esm2-3b_predict_contacts`, `esm2-3b_logits`, `esm2-3b_masked_completion`, `esm2-3b_attention_maps`, `esm2-3b_masked_token_loss`. Read their schemas. Pass REST `version`, `parameters`, `inputs`, `region`, `gpu` and a saved `idempotency_key`; omit `model`/`workflow`. Poll with `md_run_status`, retrieve with `md_run_artifacts`, cancel with `md_run_cancel`. REST: `GET /v1/runs/{id}`, `GET /v1/runs/{id}/artifacts`, `POST /v1/runs/{id}/cancel`. Never submit an existing run again.

Inspect structured error stage/field/retryability/correlation ID. Fix deterministic failures before a new request. Closed scoring batches/PLL terms and inference rows checkpoint to the owner bucket at the five-minute quantum or interruption. The unfinished batch/row recomputes; individual forwards have no partial neural checkpoint or fixed five-minute recovery-point guarantee. Resumption preserves owner, selected version, scientific settings and original deadline. For verified scheduler or infrastructure preemption, the service attempts same-GPU recovery, preserving precision. Float32 H100-to-H200 continuation is also qualified; other cross-GPU/precision pairs are rejected. Resume with typed MCP `md_run_resume`, the same `run_id`, an authorized `region` and compatible `gpu`. The demonstrated cross-region test used public cancellation after genuine unfinished progress, rather than injected cloud failure. Completed verified owner-bucket results remain durable.

ESM code and this pinned checkpoint declare MIT. Reviewed dependency terms permit commercial nonclinical hosted inference and private regional Linux copies, retaining applicable notices. This guide grants no production or clinical clearance.
