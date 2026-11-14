---
name: runai-esmc-600m
description: Compute ESM Cambrian 600M protein embeddings, sequence or variant scores, hidden representations, logits, masked-position predictions and explicit eager attention maps through the authenticated Scientific AI REST API or typed MCP.
---

# ESM Cambrian 600M

Use the authenticated Scientific AI service with your own bucket credentials.
Discover the current schema before preparing input:
`GET /v1/models/esmc-600m?workflow=embed`.
Use `GET /v1/models?model=esmc-600m&limit=1` for bounded discovery.
The scientific version is `esmc-600m-5e366569`, checkpoint
`biohub/ESMC-600M` revision `5e366569e675ad5ae3512f66bf0b53ffe80ee83e`,
Transformers 5.16.0. Select only placements available to your authenticated account.

Status: SYSTEM evaluation. The authorized API schema determines availability.
Native CPU and H100/L40S/H200/B200 float32 feature screens have passed.
Public-client, other precision, recovery and full production/security acceptance
remain pending; these screens are not complete production qualification.
Do not advertise availability before the exact released contract is qualified.

Use the existing [portable gateway client](../runai-scientific-gateway/references/client.md)
for authentication, owner-bucket upload, submit/poll/cancel and full artifact
retrieval/verification. Its environment names are `SCIENTIFIC_AI_URL`,
`SCIENTIFIC_AI_TOKEN`, `SCIENTIFIC_DATA_ENDPOINT`, `SCIENTIFIC_DATA_REGION` and
`SCIENTIFIC_DATA_BUCKET`; read AWS credentials from your approved secret source.
No workbench or private operator helper is required.

For every workflow below, discover its schema using that client, then prepare the
small self-contained fixture and typed parameters with [fixture.py](fixture.py):

```sh
MODEL=esmc-600m
WORKFLOW=embed
export INPUT_KEY=work/your-campaign/esmc-input.tar.gz
PREPARED="prepared-$WORKFLOW"
python fixture.py --workflow "$WORKFLOW" --key "$INPUT_KEY" --output "$PREPARED"
```

Choose a fresh `PREPARED` directory for each workflow/run; existing directories
are refused to preserve prior inputs. This creates `$PREPARED/input.tar.gz`,
`parameters.json` and `input-reference.json`.
Upload that archive using the gateway instructions and your own bound bucket.
Merge the generated references into the discovered example before submitting:

```sh
jq --slurpfile input "$PREPARED/input-reference.json" \
   --slurpfile parameters "$PREPARED/parameters.json" \
   '.inputs=[$input[0]] | .parameters=$parameters[0] | .version="esmc-600m-5e366569" | .pvc_gib=32' \
   request.json > request-with-input.json
mv request-with-input.json request.json
```

Use the updated `request.json` in the shared submit-once flow. Persist the returned
run ID and poll the same run after a disconnect. Retrieve the result inventory
through the shared client, verify full hashes and sizes, then preserve relative
artifact paths under a `results` directory. Run the scientific check with
`python check_result.py --workflow "$WORKFLOW" --result-dir results`; it needs
NumPy and does not access the network or credentials. Repeat these steps with
each of the seven workflow names below; fixture parameters adapt automatically.

All workflows accept one gzip-compressed tar input named `input.tar.gz`, with
relative archive-root paths and no symlinks. Include `sequences.fasta` with unique
first-token identifiers and amino-acid residues. Variant scoring also needs
`variants.csv` with columns `id,sequence_id,mutations`. Use one-based substitutions
such as `A1G`, separating multiple changes with colons: `A1G:C2A`.
`fasta_file` and `variants_file` select alternate relative member paths.
Invalid identities, wild-type residues, positions and feature combinations fail
before GPU execution. Never silently truncate a sequence to fit memory.

## Embed

Anchor: <a id="embed"></a>
Prepare `--workflow embed`. Native final-layer residue arrays have shape `(L,1152)`;
mean arrays have shape `(1152,)`. `data/outputs/score/index.csv` preserves FASTA
identifiers/order and names both arrays inside `embeddings.tar`.
`result.json` records counts, exact checkpoint/input identity and hashes.
Mean pooling excludes BOS/EOS. Embeddings always use the full sequence;
`strategy` and non-null `context_window` are invalid for embedding.

Typed MCP: `esmc-600m_embed` with the same `inputs`, `parameters`, `version`,
`region` and `gpu` fields as REST. Its accepted run ID uses the common polling
and artifact tools discovered from your MCP client.

## Score variants

Anchor: <a id="score-variants"></a>
Prepare `--workflow score-variants`. The example includes an identity control,
a substitution and a multi-substitution. `strategy` selects `masked-marginals`
(default), `wt-marginals` or `pseudo-log-likelihood`. Output
`data/outputs/score/scores.csv` preserves `id,sequence_id,mutations` and reports
`score,residues_scored,mean_score`. Identity variants score zero.
Marginals sum mutant-minus-reference log probabilities in the reference context;
PLL compares complete mutant/reference sequence PLL. Marginal sums omit epistasis.
Typed MCP: `esmc-600m_score_variants`.

## Score sequences

Anchor: <a id="score-sequences"></a>
Prepare `--workflow score-sequences`. Every residue contributes a masked log
probability, yielding a sequence sum and per-residue mean in `scores.csv`.
Only null/default or `pseudo-log-likelihood` strategy applies. The score is
length-dependent and is not a calibrated biochemical or clinical effect.
Typed MCP: `esmc-600m_score_sequences`.

For both scoring workflows, `batch_size` and padding-aware `batch_tokens` bound
masked-context batches. An explicit `context_window` uses centered residue windows
and changes the scientific context; null preserves the full sequence. Results
record the selected policy. Choose `float32`, `float16` or `bfloat16` explicitly
when comparing scores; retain matched precision and context settings.

## Extract representations

Anchor: <a id="extract-representations"></a>
Prepare `--workflow extract-representations`. `layers` selects native hidden-state
indices 0–36; layer 36 is the final representation. `representations` selects
`per-token`, `mean` and/or `bos`. The example requests layers 0,18,36 and all three.
`data/outputs/infer/result.json` indexes compressed NumPy `.npz` files in FASTA
order, including array names, dimensions and full hashes. Residue matrices omit
special tokens; mean pooling uses residues only. BOS is an optional native vector.
Typed MCP: `esmc-600m_extract_representations`.

## Logits

Anchor: <a id="logits"></a>
Prepare `--workflow logits`. Each indexed `.npz` holds `logits` of shape `(L,64)`.
Optional `masked_positions` names each selected sequence once and gives one-based
residue positions; all listed positions are masked simultaneously. The 64 output
indices preserve the native model vocabulary. Tokenizer entries 33–63 have no
mapped token text and appear as null; do not relabel or discard these logits.
Typed MCP: `esmc-600m_logits`.

## Masked completion

Anchor: <a id="masked-completion"></a>
Prepare `--workflow masked-completion`. Supply nonempty `masked_positions` for every
input sequence and optional `top_k` (1–64, default 5). Results include full logits
and requested-position token IDs, token text/null and softmax probabilities.
Probabilities include all 64 native logits. These are independent marginal
predictions under simultaneous masking, not joint sequence generation.
Typed MCP: `esmc-600m_masked_completion`.

## Attention maps

Anchor: <a id="attention-maps"></a>
Prepare `--workflow attention-maps`. `layers` selects one-based transformer blocks
1–36, and `heads` selects zero-based heads 0–17; both preserve requested order.
Defaults return all layers and heads. The fixture selects layers 1,18,36 and
heads 0,8,17. Each `.npz` contains `layer_N_attention` with shape
`(selected_heads,L+2,L+2)`. Within each of the two token axes, index 0 is BOS,
indices 1–L are input residues, and index L+1 is EOS. Maps keep all tokens and
are never cropped or renormalized.
Optional `masked_positions` masks the specified residues simultaneously.
Use `output_budget_bytes` to declare an adequate existing request budget;
the fixture example uses 67,108,864 bytes. Raw selected float32 matrices must
fit that budget. Output selection does not reduce all native eager maps in memory.
Before model loading, known actual accelerator total memory and container RAM
limits reject provably impossible lower bounds. Passing these bounds does not
guarantee a fit: model weights, intermediate tensors and allocation overhead also
consume memory. No sequence, head or layer is silently truncated.
This workflow explicitly uses the native eager attention implementation;
`attention_provenance` records it. The other workflows retain SDPA. Attention
weights are not contact probabilities or calibrated biological interactions.
Memory/output size grows quadratically with token count; preserve explicit
precision and check your available execution resources. Typed MCP:
`esmc-600m_attention_maps`. Use the same shared submit-once and artifact flow.

Long sequence and variant scoring implement closed-native-batch continuation;
ESMC-600M interruption and cross-region recovery remain under qualification.
No verified ESMC-600M resume guarantee is claimed yet. The implementation
preserves owner, inputs, weights, precision,
context, explicit batch settings and the original deadline; unfinished forwards
recompute. Short scoring and the other inference workflows currently restart
their unfinished whole-file unit. No in-flight neural-state restoration is
promised. The cumulative native execution budget is 86,400 seconds within the
original outer job deadline; continuation resets neither budget. Completed
results remain in your bucket.
Errors identify the failing stage/field, retryability and next action; inspect
terminal status before treating a transport success as scientific success.

The official [model card](https://huggingface.co/biohub/ESMC-600M/tree/5e366569e675ad5ae3512f66bf0b53ffe80ee83e)
and [upstream implementation](https://github.com/huggingface/transformers/tree/v5.16.0/src/transformers/models/esmc)
describe checkpoint provenance. Preserve applicable notices. The model card specifies a 2048-token trained context window; computation beyond
that context is not an accuracy guarantee. Model scores and
embeddings do not establish affinity, stability ddG or experimental efficacy.
