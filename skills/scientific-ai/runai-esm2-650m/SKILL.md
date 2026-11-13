---
name: runai-esm2-650m
description: Score protein variants/sequences, extract ESM-2 650M layer representations, predict contacts, inspect logits or complete typed masked positions through the Scientific AI REST/MCP service.
version: 0.1.0
license: Apache-2.0
---

# ESM-2 650M

Check model availability and its deployed contract before submitting. This guide describes the scientific interface; production qualification remains incomplete. This model uses `facebook/esm2_t33_650M_UR50D` revision `08e4846e537177426273712802403f7ba8261b6c`; ESM2-3B is a separate model.

Set `SCIENTIFIC_AI_BASE_URL` and `SCIENTIFIC_AI_API_KEY` from your approved scientific API connection. Owner upload uses your existing `OWNER_S3_ENDPOINT`, `OWNER_BUCKET`, `OWNER_INPUT_PREFIX` and standard AWS credential environment/profile. Never put credentials in input archives. The API token goes only to its configured scientific API origin.

Choose an allowed region and GPU from your platform connection details. For an authorized H100 in EU-North1, run `SCIENTIFIC_AI_REGION=eu-north1 SCIENTIFIC_AI_GPU=h100 python example.py --workflow score-variants --output ./new-result-directory`. The client requires explicit placement before uploading while automatic cost routing is unqualified. Install `boto3` in your client environment for bucket upload. `--prepare-only` creates the deterministic synthetic fixture without network access. The example discovers the selected schema, uploads into your bucket, submits with an idempotency key, polls, downloads authorized results and verifies hashes and sizes. Before submission it saves `submission.json`; if the reply is lost, reuse that exact request and `Idempotency-Key` rather than creating another run.

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

Use a bounded batch whose complete native execution fits the discovered memory, output and deadline envelope. The whole batch is one execution unit: interruption restarts the unfinished batch under its original owner/version/deadline. A five-minute checkpoint setting does not create partial-row or in-flight neural checkpoints. Only completed, verified owner-bucket results are durable; long-campaign positive-progress continuation is not qualified. Poll `GET /v1/runs/{id}`; cancel with `POST /v1/runs/{id}/cancel`. Final export retries are bounded to 300 seconds before exact scratch deletion; failed unsynced tail loss must be reported. Keep `run.json` if the client disconnects and poll that ID before considering another submission.

Typed MCP uses `esm2-650m_score_variants`, `esm2-650m_score_sequences`, `esm2-650m_extract_representations`, `esm2-650m_predict_contacts`, `esm2-650m_logits` and `esm2-650m_masked_completion`. Request its schema on demand; reuse the same parameters and owner input reference as REST. On error inspect the structured cause/stage/field/retryability/correlation ID. Correct deterministic input failures; do not blindly retry or duplicate an ambiguously accepted submission.

ESM code and this pinned checkpoint declare MIT. The reviewed dependency grants permit commercial hosted inference and private regional Linux copies under their standard terms. Applicable runtime notices must be retained. This usage guide does not establish production or clinical clearance.
