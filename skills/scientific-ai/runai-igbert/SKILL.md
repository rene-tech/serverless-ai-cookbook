---
name: runai-igbert
description: Compute paired-antibody IgBert embeddings, pseudo-log-likelihood, hidden representations, logits, masked predictions and attention through the managed REST and typed MCP interfaces.
---

# IgBert paired antibody inference

Discover `GET /v1/models/igbert` or MCP `md_models` with
`{"model":"igbert","detail":true}`. Select the qualified scientific version
`igbert-paired-81a4abb8` and an account-permitted placement. The live release
controls availability; this guide does not establish production or hosting clearance.

Use the shared [portable client](../runai-scientific-gateway/references/client.md)
for environment-based credentials, caller-bucket uploads, one-time submission,
polling and checksum-verified result retrieval. No private helper or Run:ai admin
access is needed. Use a fresh request directory and idempotency key for each
workflow. Do not send a scientific bearer token to public fixture websites.

Download [fixture.py](fixture.py) alongside this guide from the same cookbook commit,
and save it in your working directory. Public skill downloads need no API token;
never attach your scientific bearer token to them. The helper uses only Python's
standard library. Prepare one example per workflow:

```sh
WORKFLOW=embed
export INPUT_KEY=work/your-campaign/igbert-input.tar.gz
python3 fixture.py --workflow "$WORKFLOW" --key "$INPUT_KEY" --output prepared
```

The helper writes `prepared/input.tar.gz`, `parameters.json` and
`input-reference.json`. Upload that exact archive to your existing bound bucket
using the shared client, discover the workflow example into `request.json`, then:

```sh
jq --slurpfile input prepared/input-reference.json \
   --slurpfile parameters prepared/parameters.json \
   '.inputs=[$input[0]] | .parameters=$parameters[0] |
    .version="igbert-paired-81a4abb8" | .region="eu-north1" | .gpu="h100"' \
   request.json > request-with-input.json
mv request-with-input.json request.json
```

Use only placements granted to your account. Submit through the shared REST
flow or the typed MCP tool below with `parameters`, `inputs`, `version`, `region`,
`gpu` and the saved `idempotency_key`; omit REST's `model` and `workflow` in MCP.
Poll `md_run_status`, retrieve `md_run_artifacts`, verify complete hashes/sizes,
and inspect the scientific files. A submitted job is not a scientific result.

## Inputs and scientific controls

Every workflow takes one gzip tar named `input.tar.gz`, containing UTF-8
`sequences.csv` with columns `id,heavy,light`, relative to the archive root.
`sequences_file` may select another relative CSV member. IDs must be unique and
nonempty; they are data, not paths. Heavy chains are required; light chains may
be empty. The native parser removes sequence whitespace and uppercases residues.
Its alphabet is `ACDEFGHIKLMNPQRSTVWYXBZUO`; gaps and raw special-token text fail
validation. Never silently truncate a chain.

Chains are tokenized as heavy, SEP, light, with CLS/terminal SEP. All segment IDs
remain zero, matching the official paired example. Residue outputs/means exclude
every special token, including the internal SEP. Positions are one-based within
the supplied chain, not IMGT numbering. The checkpoint's 40,000 total positional
tokens include markers; this is not a tested memory or biological accuracy limit.

Defaults are `precision:"float32"`, `batch_size:8`, `cpu_threads:4`.
Logits, hidden representations and attention also accept optional
`masked_positions` in the same chain-relative format as masked completion.
Unlisted records stay unmasked; returned source token IDs and the recorded mask
positions make the actual masked context explicit.
`batch_size` bounds masked contexts inside one sequence's PLL calculation;
it does not batch CSV records. The native FP16/BF16 controls exist, but their
scientific equivalence requires separate qualification; use the live release's
qualified precision. Keep precision and explicit settings fixed in comparisons.

## Embed

MCP: `igbert_embed`. Outputs below `data/outputs/igbert/native/` are `index.csv`
and `embeddings.tar`. Each record has a float32 `(heavy+light,1024)` residue
matrix and a `(1024,)` residue mean; index paths refer to tar members.

## Score sequences

MCP: `igbert_score_sequences`. `native/scores.csv` contains IDs, chain/residue
counts, `score` and `mean_score`. Every residue is masked in its own context;
the score is the sum of natural-log target probabilities and the mean divides
by all heavy/light residues. This is pseudo-log-likelihood, not affinity or Kd.

## Extract representations

MCP: `igbert_extract_representations`. `layers` selects indices 0–30; 0 is the
input embedding state and 30 the final hidden state. The example selects 0,1,30.
Each indexed NPZ has `layer_N` and `mean_N` arrays. `include_special_tokens:true`
keeps special tokens in the returned matrix; means always use residues only.

## Logits

MCP: `igbert_logits`. Each record's NPZ contains `logits` and normalized natural
`log_probabilities`, both `(residues,30)`. The result publishes the exact native
vocabulary; do not discard or relabel the five special-token columns.

## Masked completion

MCP: `igbert_masked_completion`. Supply `masked_positions` for every record:
`[{"sequence_id":"official-pair-1","heavy":[31],"light":[44]}]`.
Positions are masked simultaneously. `top_k` ranges 1–25 over native residue
token IDs 5–29. Probabilities retain the full 30-token softmax denominator and
are not renormalized over returned candidates. These independent marginals
are not autoregressive generation or a joint sequence probability.

## Attention maps

MCP: `igbert_attention_maps`. `layers` selects blocks 1–30 and `heads` selects
0–15. The example requests layers 1,30 and heads 0,7,15. NPZ `attention` is
`(selected_layers,selected_heads,tokens,tokens)`. Special tokens are included by
default; residue-only submatrices are not renormalized. The eager engine computes
all layers/heads before selecting outputs, so smaller output selections do not
guarantee a memory fit. Attention weights are not contact or binding probabilities.

## Storage, recovery and limits

These are finite GPU jobs; idle scientific compute returns to zero. Inputs,
temporary data, checkpoints and results stay in the authenticated owner's bucket
and temporary private job volume. A different bucket requires an approved binding;
parameters cannot grant access. Shutdown retries final upload for at most 300
seconds, then deletes scratch even if unsynced data is lost.

The implementation checkpoints complete internal 32-row native units, preserving
original record order and masked-context batches. This is not a 32-record input
cap. An unfinished unit is recomputed; complete verified units may resume into
a fresh authorized-region volume with the original owner/settings/deadline.
There is no mid-forward or partial-row continuation and no fixed five-minute RPO.
Larger rows/units may take longer; use the live workload envelope and budget.
The final merged files retain the native scientific format.

Inspect structured field/rule errors and terminal failures before retrying.
Preserve the original run/key after an uncertain transport response. A `403`
requires an access correction, not a different identity. Native deployment/image
identifiers and operator credentials are not customer-facing model versions.

The example sequences and checkpoint provenance are from the pinned
[IgBert model card](https://huggingface.co/Exscientia/IgBert/tree/81a4abb8a4dac5cdcbefc28e5b331a82224c485d).
Retain its MIT notices and the documented
[ProtTrans pretrained-model AFL-3.0 terms](https://github.com/agemagician/ProtTrans#license)
and source attribution. Managed checkpoint selection does not permit arbitrary
customer code or checkpoint imports. Training/fine-tuning, unpaired checkpoints,
newly initialized classification heads and native labelled-loss recipes are
separate unqualified capabilities; raw logits alone do not qualify those APIs.
