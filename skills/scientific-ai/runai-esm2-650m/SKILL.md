---
name: runai-esm2-650m
description: Score protein variants/sequences, extract ESM-2 650M layer representations, predict contacts, inspect logits and attention, complete masked positions or measure masked-token loss through the Scientific AI REST/MCP service.
version: 0.2.1
license: Apache-2.0
---

# ESM-2 650M

The portable [example client](example.py) accompanies this skill; download both from the same published revision.

Check model availability and its deployed contract before submitting. This guide describes the scientific interface; check the deployed model contract for enabled workflows and versions. This model uses `facebook/esm2_t33_650M_UR50D` revision `08e4846e537177426273712802403f7ba8261b6c`; ESM2-3B is a separate model.

Set `SCIENTIFIC_AI_BASE_URL` and `SCIENTIFIC_AI_API_KEY` from your approved scientific API connection. Owner upload uses your existing `OWNER_S3_ENDPOINT`, `OWNER_BUCKET`, `OWNER_INPUT_PREFIX` and standard AWS credential environment/profile. Never put credentials in input archives. The API token goes only to its configured scientific API origin.

Choose an allowed region and GPU from your platform connection details. For an authorized H100 in EU-North1, run `SCIENTIFIC_AI_REGION=eu-north1 SCIENTIFIC_AI_GPU=h100 python example.py --workflow score-variants --output ./new-result-directory`. Alternatively, add `--auto-place` to let the service fill missing placement fields. Supplied `SCIENTIFIC_AI_REGION` and `SCIENTIFIC_AI_GPU` constraints remain binding; unset both to choose across all authorized regions. Routing uses measured full-VM on-demand cost estimates for default float32/512-residue reference requests and available capacity; this is neither an invoice nor a cheapest-hardware guarantee for every input or precision. Install `boto3` in your client environment for bucket upload. `--prepare-only` creates the deterministic synthetic fixture without network access. The example discovers the selected schema, uploads into your bucket, submits with an idempotency key, polls, downloads authorized results and verifies hashes and sizes. Before submission it saves `submission.json`; if the reply is lost, reuse that exact request and `Idempotency-Key` rather than creating another run.

Inputs are one gzip-compressed tar referenced by exact owner-bucket key/SHA256/size. FASTA IDs are unique first header tokens. Paths are archive-relative; default `sequences.fasta` can be changed with `fasta_file`. Whitespace/case normalize; gaps and special token strings are rejected. Large record sets are accepted subject to the discovered transport/resource budgets; individual full sequences must fit model memory. No sequence is silently truncated.

## score-variants

Include CSV `variants.csv` with `id,sequence_id,mutations`. Positions are one-based, for example `A1G` or `C2S:W19F`; WT residues must match FASTA. Default `masked-marginals` masks each changed site in the unchanged reference. `wt-marginals` uses unmasked reference log odds. `pseudo-log-likelihood` compares complete mutant and reference PLL. Identity variants must score zero. Additive marginal scores do not model epistasis.

## score-sequences

Mask every residue once and return complete PLL and mean PLL/residue. `strategy` must be `pseudo-log-likelihood` or omitted. Both scoring workflows expose the unchanged `batch_size`, padding-aware `batch_tokens`, explicit `context_window` and `precision` controls. Default precision is float32/full sequence; finite centered windows are an explicit scientific approximation. Output is `scores.csv` plus `result.json`; units are natural logs, without a calibrated ddG, affinity, pathogenicity or clinical interpretation.

## extract-representations

Choose native `layers` from 0–33 and `representations` from `per-token`, `mean`, `bos`. Defaults are final layer 33/per-token and mean. Per-token shape is `[residues,1280]`; mean excludes BOS/EOS/padding. BOS is a native vector and carries no promised prediction accuracy. Arrays materialize as float32 NPZ without pickle.

## predict-contacts

Return the pretrained native attention contact head's symmetric `[residues,residues]` probability matrix. This is an unsupervised contact estimate, not a 3D structure prediction or an experimental measurement.

## logits

Return all 33 native-token logits per residue, with the vocabulary and dimensions in `result.json`. Optionally provide `masked_positions: [{"sequence_id":"synthetic","positions":[2,5]}]`. Positions count residues from 1, excluding BOS. Every requested mask is applied simultaneously.

## masked-completion

Supply mask positions for every input sequence and choose `top_k` from 1–33. Return native-token IDs/text/probabilities plus full logits. Predictions are marginal at each site given all specified sites masked; they are not joint sequence decoding. The native vocabulary includes special tokens, so preserve returned token labels.

## attention-maps

Use `python example.py --workflow attention-maps --output ./new-attention-results` with your existing connection and storage environment. The example selects transformer `layers: [1,33]` and zero-based `heads: [0,19]`. Attention layers are one-based (1–33); heads are zero-based (0–19). Each selected layer returns `[selected_heads,L+2,L+2]` native attention probabilities, including BOS, all residues and EOS in that order. Full-token rows normalize to one; these are attention weights, not calibrated contacts or interaction probabilities. Optional `masked_positions` applies the same simultaneous input masking as logits. Native attention materializes every layer and head before selection, so selecting fewer outputs does not remove that working-memory cost.

## masked-token-loss

Use `python example.py --workflow masked-token-loss --output ./new-loss-results`. The example masks residues 2 and 5 of `synthetic`. Original FASTA residues supply the target token IDs at exactly those positions; all unselected and special-token labels are ignored (`-100`). Each sequence returns a scalar `loss` in its NPZ: native natural-log mean cross entropy over its selected positions. This is a simultaneous-mask supervised loss, distinct from the sequential masked pseudo-likelihood in `score-sequences`; it neither updates weights nor fine-tunes the model.

Use a bounded batch whose single native forward fits the discovered memory, output and two-week execution deadline. The managed path checkpoints completed native scoring batches and completed inference rows to your bucket, preserving global record order and settings. It reuses one loaded model within each five-minute execution quantum; restoring a later quantum can load the model again. An individual native forward remains atomic, so five-minute quantums do not guarantee a five-minute recovery-point objective when a forward takes longer. Recovery uses the last verified bucket checkpoint; an abrupt interruption can lose newer, unsynced work. For verified scheduler or infrastructure preemption, the service attempts same-GPU recovery automatically. Continuation preserves the original precision; float32 H100 to H200 is also supported across regions. Other GPU/precision pairs are rejected until qualified. Recovery uses a fresh private PVC under the original owner, version and deadline. Poll `GET /v1/runs/{id}`; cancel with `POST /v1/runs/{id}/cancel` and resume with typed MCP `md_run_resume` using the same `run_id`, an allowed `region` and compatible `gpu`. Final export retries are bounded to 300 seconds before exact scratch deletion; failed unsynced tail loss must be reported. Keep `run.json` if the client disconnects and poll that ID before considering another submission.

Typed MCP uses `esm2-650m_score_variants`, `esm2-650m_score_sequences`, `esm2-650m_extract_representations`, `esm2-650m_predict_contacts`, `esm2-650m_logits`, `esm2-650m_masked_completion`, `esm2-650m_attention_maps` and `esm2-650m_masked_token_loss`. Request its schema on demand; reuse the same parameters and owner input reference as REST. On error inspect the structured cause/stage/field/retryability/correlation ID. Correct deterministic input failures; do not blindly retry or duplicate an ambiguously accepted submission.

ESM code and this pinned checkpoint declare MIT. The reviewed dependency grants permit commercial hosted inference and private regional Linux copies under their standard terms. Applicable runtime notices must be retained. This usage guide does not establish production or clinical clearance.
