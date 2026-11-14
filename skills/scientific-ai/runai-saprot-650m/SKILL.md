---
name: runai-saprot-650m
description: Use managed SaProt 650M AF2 for structure-aware protein embeddings, mutation scoring, amino-acid marginals, hidden representations, logits, masked predictions and attention through REST and typed MCP.
---

# SaProt 650M AF2

Discover `GET /v1/models/saprot-650m` or MCP `md_models` with
`{"model":"saprot-650m","detail":true}`. Select scientific version
`saprot650m-af2-d9b9ad00` and an account-permitted region/GPU. The live catalog
controls actual availability and qualification; this guide is not commercial
hosting or clinical clearance. This checkpoint is distinct from SaProt 1.3B
and its inverse-folding variant.

Use the shared [portable client](../runai-scientific-gateway/references/client.md)
for environment-based authentication, upload to your bound bucket, submission,
polling and checksum-verified result retrieval. Download [fixture.py](fixture.py)
from the **same cookbook commit** as this guide and save it locally. Public
skill downloads are unauthenticated; never send a scientific bearer token to
GitHub or a fixture site. The helper needs only Python's standard library.

```sh
WORKFLOW=embed
export INPUT_KEY=work/your-campaign/saprot-input.tar.gz
python3 fixture.py --workflow "$WORKFLOW" --key "$INPUT_KEY" --output prepared
```

Upload `prepared/input.tar.gz` unchanged using the shared client. Discover the
selected workflow's example into `request.json`, then set the exact uploaded
reference and parameters:

```sh
jq --slurpfile input prepared/input-reference.json \
   --slurpfile parameters prepared/parameters.json \
   '.inputs=[$input[0]] | .parameters=$parameters[0] |
    .version="saprot650m-af2-d9b9ad00" | .region="eu-north1" | .gpu="h100"' \
   request.json > request-with-input.json
mv request-with-input.json request.json
```

Use a new request directory and saved idempotency key for **each new operation**.
For typed MCP pass `parameters`, `inputs`, `version`, `region`, `gpu` and
`idempotency_key`; omit REST's `model` and `workflow`. Poll `md_run_status`,
then retrieve `md_run_artifacts` and verify complete file hashes and sizes.
Preserve the original run/key after an uncertain response; do not submit twice.

## Input contract

All eight workflows accept one gzip tar named `input.tar.gz`, with flat UTF-8
`sequences.fasta`. `fasta_file` may select a different archive-relative member.
FASTA IDs must be unique. Structure-aware tokens alternate uppercase standard
amino acid and lowercase Foldseek 3Di symbol, for example `M#EvVp` represents
three residues; `#` is unknown structure. The 3Di alphabet is
`acdefghiklmnpqrstvwy`; do not substitute secondary-structure labels.
`input_kind:"amino-acid"` accepts standard amino-acid sequences and explicitly
supplies unknown 3Di symbols. Never silently truncate sequences or treat that
mode as equivalent to a real structure-aware input.

Alternatively include a PDB/mmCIF and set `structure_file` to its relative path.
Foldseek derives tokens; FASTA is then ignored. `chains:["A"]` selects exact
**author chain IDs**, including multi-character IDs. Whitespace-containing
protein chain IDs are currently rejected before GPU execution. Output record
IDs are the selected chains. Defaults are `plddt_mask:"auto"` and threshold70:
auto recognizes AlphaFold metadata; it does not interpret experimental B factors
as pLDDT. Use explicit `true`/`false` when appropriate. Below-threshold structure
tokens become `#`; amino acids remain unchanged. Derived positions are one-based
sequence positions, not original PDB residue numbers or insertion codes.

Defaults: `precision:"float32"`, `cpu_threads:4`. Native FP16/BF16 options have
execution screens only; do not infer scientific equivalence from those screens.
The model has33 blocks,20 attention heads,1280 hidden features and446 vocabulary
tokens. Published positional configuration is not a tested memory/accuracy limit.

## Workflows and outputs

## Embed

MCP `saprot-650m_embed`: `native/index.csv` maps each record to
  `native/embeddings.tar` members. Residue arrays are float32 `(residues,1280)`;
  means are `(1280,)`. Both exclude boundary tokens.
## Score variants

MCP `saprot-650m_score_variants`: include `variants.csv`
  with exact columns `id,sequence_id,mutations`. For example
  `v1,native,M1A:E2D` masks both substituted amino acids simultaneously, preserving
  their structure tokens. IDs reference FASTA/derived chains. `native/scores.csv`
  reports sum/mean natural-log mutant-to-wild-type probability ratios; positive
  favors mutant likelihood. Identity substitutions score0. This is not affinity,
  Kd, ddG or a clinical pathogenicity score. Insertions/deletions are unsupported.
## Score positions

MCP `saprot-650m_score_positions`: optional `positions`
  selects one-based sites; omitted means every residue. Each site is masked in
  its own full context and scores the native amino acid. Sum/mean log likelihood
  is distinct from mutation-effect scoring and unmasked sequence likelihood.
## Position probabilities

MCP `saprot-650m_position_probabilities`: the same
  optional position selection returns20 amino-acid marginals in indexed CSVs.
  Each marginal sums that amino acid's21 structure-token probabilities from the
  full446-token softmax. The20 values are **not renormalized** to sum1.
## Extract representations

MCP `saprot-650m_extract_representations`:
  `layers` selects0–33. Layer0 is input state;33 is final hidden state.
  Indexed NPZs contain `layer_N` and `mean_N`. `include_special_tokens:true`
  retains boundaries in matrices; means always use residues only.
## Logits

MCP `saprot-650m_logits`: indexed NPZs return446-column `logits`
  and normalized natural `log_probabilities`, with the exact vocabulary in
  result metadata. Do not relabel or discard its special-token columns.
## Masked completion

MCP `saprot-650m_masked_completion`: provide
  `masked_positions:[{"sequence_id":"native","positions":[1,2]}]`; each record
  requires a selection. Masks are simultaneous on the amino-acid component;
  structure remains. `top_k`1–20 ranks amino-acid marginals with the original
 446-token denominator. These are independent marginals, not autoregressive
  generation or a joint probability.
## Attention maps

MCP `saprot-650m_attention_maps`: `layers` selects1–33,
  `heads`0–19. NPZ `attention` has axes
  `(selected_layers,selected_heads,tokens,tokens)`. Boundaries are included by
  default; residue-only submatrices are not renormalized. The supported eager
  engine computes all heads before output selection, so small selections do
  not guarantee a memory fit. Attention is not a contact/binding probability.

Logits, representations and attention also accept `masked_positions` with the
same record/position fields; unlisted records remain unmasked. Outputs sit under
`data/outputs/saprot-650m/`, with `result.json` recording the scientific settings,
indexed files and runtime measurements. The two fixture records have9/8 residues.
A completed operation alone does not establish a biologically useful prediction.

## Storage, recovery and scientific boundaries

These are finite jobs; idle model compute returns to zero. Inputs, temporary
data, checkpoints and outputs remain in your bound bucket and a private temporary
job volume. Parameters cannot grant another bucket's access. Shutdown retries
final upload for at most300seconds, then removes scratch even if unsynced data
is lost. Resume uses only a verified checkpoint already in your bucket.

The implementation checkpoints completed internal32-context units, preserving
original record IDs/order and native masked contexts. This is not a32-record
input cap. Unfinished units recompute. A supported cross-region resume creates a
fresh volume with the same owner/settings/deadline, then restores verified closed
units. Qualified continuation is EU-North1 H100 to EU-North2 H200 at
`precision:"float32"` (the default); unsupported precision returns a structured
conflict before queueing. There is no mid-forward continuation or unmeasured
fixed five-minute RPO.
Large contexts/attention remain subject to the live resource/output budget.

Use structured field/rule errors to correct invalid input. A forbidden region
or foreign run returns an authorization error; changing scientific parameters
cannot grant access. Only qualified versions/placements are advertised by the
live catalog; internal registry and deployment identifiers are private.

The native upstream ProteinGym evaluation class has additional optional MSA
prior/structure-ablation controls not yet qualified here. Its legacy tokenizer
call is incompatible with the current dependency; insertion handling is not a
validated insertion fitness algorithm. Do not infer those features from the
core substitution API. Training, LoRA and newly initialized task heads are
separate unqualified capabilities.

The short native fixture and code come from the pinned
[SaProt MIT source](https://github.com/westlake-repl/SaProt/tree/e91e4858b55944523f1f8d385f7b96a0d3d34c1d).
Weights use the pinned
[650M AF2 model card](https://huggingface.co/westlake-repl/SaProt_650M_AF2/tree/d9b9ad00ef61c0990e611b2b43f2231c7de24b38).
Structure conversion also uses GPLv3 Foldseek; retain the accompanying notices.
Only managed named checkpoints are allowed; arbitrary customer code/checkpoints
are outside this inference interface.
