---
name: runai-esm-if1
description: Design protein sequences from backbones, score sequence compatibility and obtain structural encoder representations using the managed ESM-IF1 REST and MCP workflows.
---

# ESM-IF1 inverse folding

Discover `esm-if1` with `GET /v1/models/esm-if1` or MCP `md_models`
`{"model":"esm-if1","detail":true}`. Select a version from that response and use a placement permitted by your account. This contract describes named checkpoint
**esm_if1_gvp4_t16_142M_UR50**, with native FP32 inference and the managed
AntiFold **0.4.0+managed.cif1** runtime dependency. The checkpoint name is
unchanged. A skill is usage documentation; the live release determines access
and qualified availability.

Use the shared [portable client](../runai-scientific-gateway/references/client.md)
for environment-based authentication, bucket uploads, one-time REST submission,
polling, cancellation and checksum-verified downloads. Do not send a Scientific
AI bearer header when downloading public fixtures. Native Run:ai administration
and LibreChat-specific helpers are unnecessary.

The reference requests below use **EU-North1 / H100**. Replace `region` and
`gpu` only with a placement permitted by your account; a forbidden placement
returns a permission error. Omit placement fields only when the live model
has qualified automatic routing. Checkpoint and data-copy regions remain
subject to your grant.

## Prepare an owner archive

In a fresh client directory, prepare this pinned public example:

```sh
mkdir -p prepared-inputs
curl --fail-with-body --silent --show-error \
  https://raw.githubusercontent.com/oxpig/AntiFold/9918344067f34a6b026f2634fdba212fc3e6e986/data/pdbs/6y1l_imgt.pdb \
  --output prepared-inputs/target.pdb
printf '%s  prepared-inputs/target.pdb\n' \
  19513b0fee557e501229c4acd13d462a4ddf38212bc1e83fa6f1696f1c97f282 | sha256sum --check
cat > prepared-inputs/sequences.fasta <<'FASTA'
>native_H
VQLQESGPGLVKPSETLSLTCAVSGYSISSGYYWGWIRQPPGKGLEWIGSIYHSGSTYYNPSLKSRVTISVDTSKNQFSLKLSSVTAADTAVYYCAGLTQSSHNDANWGQGTLVTVSS
FASTA
tar -czf input.tar.gz -C prepared-inputs target.pdb sequences.fasta
```

The example has H and L chains; H contains 118 parsed residues. It is an
engineering example, not evidence of folding stability or experimental binding.
Attribution: Oxford Protein Informatics Group AntiFold, SAbDab IMGT annotation
of PDB 6Y1L (Dunbar et al., 2014; Schneider et al., 2022). PDB archive data are
[CC0](https://www.wwpdb.org/about/usage-policies); SAbDab annotations are
[CC-BY-4.0](https://opig.stats.ox.ac.uk/webapps/sabdab). Preserve applicable
BSD-3-Clause source notices and SAbDab attribution.

Follow the shared client's upload instructions to put **one** `input.tar.gz`
into your existing authorized bucket and write `input-reference.json` containing
`name`, `key`, `sha256` and compressed `size_bytes`. Archive members are relative
names such as `target.pdb`, not `data/inputs/target.pdb`. Runtime staging is
automatic. Another bucket requires an approved owner binding; request parameters
cannot change that authorization.

## Sample sequences

This is genuine native **autoregressive** inverse folding. Create a request:

```sh
jq -n --slurpfile input input-reference.json '{
  model:"esm-if1",workflow:"sample-sequences",
  version:"esm_if1_gvp4_t16_142M_UR50",inputs:[$input[0]],
  region:"eu-north1",gpu:"h100",
  parameters:{structure_file:"target.pdb",target_chain:"H",chains:["H","L"],
    num_sequences:2,temperature:0.2,seed:42,cpu_threads:4,
    fixed_positions:[{position:1,amino_acid:"A"},{position:2,amino_acid:"C"}]}
}' > request.json
```

Use the shared client's `POST /v1/runs`. For typed MCP call
**`esm-if1_sample_sequences`** with `parameters`, `inputs`, `version`, `region`, `gpu` and a
saved `idempotency_key`; omit REST's `model` and `workflow`. Poll `md_run_status`
and retrieve the verified inventory with `md_run_artifacts`.

`target_chain` is required. Empty `chains` selects all structure chains; an
explicit list limits and orders context. Positions are **one-based within the
parsed target chain**, not PDB residue numbers. Optional `masked_positions`
contains `{chain,positions:[...]}` entries that remove backbone coordinates with
native missing-coordinate semantics. At least one complete unmasked target
backbone residue must remain. `confidence` is null, one scalar in [0,1], or one
value per target residue. `fixed_positions` preserves the specified residues.
Design index i uses `seed+i`; resumed requests preserve the original index.
For these native APIs, mmCIF uses `label_asym_id` chain names and parsed residue
order, which can differ from author/PDB identifiers; no author-name alias is
applied.

Expect `sequences.fasta` and `result.json` per requested design. Verify target length,
residue alphabet and every fixed residue. Native recovery fraction is the
fraction matching the supplied structure's sequence; it is not binding affinity.

## Score sequences

Starting from the prepared request, change the workflow and parameters:

```sh
jq '.workflow="score-sequences" | .parameters={structure_file:"target.pdb",
  sequences_file:"sequences.fasta",target_chain:"H",chains:["H","L"],
  cpu_threads:4}' request.json > score-request.json
```

Scoring is a new operation: keep a separate request record and generate a new
idempotency key; do not reuse the sampling request's saved key.

For MCP use **`esm-if1_score_sequences`**. Each FASTA record needs a unique ID
and a sequence matching the target's parsed length. Expect `scores.json` with
per-residue negative log-likelihoods and two mean log-likelihoods, in **natural
logarithms**. The full
sequence and complete-coordinate means use different denominators when backbone
coordinates are masked or missing. Higher mean log-likelihood is better; this
is a conditional sequence-compatibility score, not a measured free energy.

## Extract encoder representations

Build the encoder request from the prepared request:

```sh
jq '.workflow="extract-encoder-representations" | .parameters={structure_file:"target.pdb",
  target_chain:"H",chains:["H","L"],cpu_threads:4}' request.json > encoder-request.json
```
The typed MCP tool is **`esm-if1_extract_encoder_representations`**. Expect
`encoder.npy`, a finite float32 matrix with one row per target residue and 512
columns. It is a structural encoder representation, not a language-model layer
or affinity. For these three native API workflows, artifact directories are
`data/outputs/esm-if1/{workflow}-{original_global_unit_index:08d}/`; each unit
also has `result.json`.

## Inverse fold

The preserved legacy `inverse-fold` workflow uses native teacher-forced
per-residue marginals and independent marginal sampling. It is **different from
the autoregressive workflow** above. Build a separate legacy request, clearing the autoregressive parameters:

```sh
jq '.workflow="inverse-fold" | .parameters={pdb_file:"target.pdb",
  heavy_chain:"H",light_chain:"L",custom_chain_mode:true,
  skip_anarcii_numbering:true,regions:"allH allL",num_seq_per_target:2,
  sampling_temp:"0.20",extract_embeddings:true,num_threads:2,seed:42}' \
  request.json > legacy-request.json
```
The typed MCP tool is **`esm-if1_inverse_fold`**.

For directory/CSV batches and native chain/region controls, use the published
schema and [shared legacy guide](../runai-antifold/SKILL.md#inputs-and-native-controls).
Choose the managed ESM-IF1 version rather than uploading checkpoint files.
ESM-IF1 always uses legacy custom-chain mode: `custom_chain_mode` must be true.
For mmCIF, numbering-enabled legacy input selects **author** chain identifiers
and then uses native IMGT output numbering. With numbering skipped, legacy
input selects **label** chain identifiers and label residue positions; those
positions must already encode the intended region numbering. PDB behavior is
unchanged, and legacy chain identifiers must be single characters. Preserve
the returned chain, residue and insertion-code mapping.

Legacy artifacts are target-stem CSV, optional FASTA and encoder NPY files plus
`result.json` under `data/outputs/antifold/`. Numbering-enabled runs also retain
their IMGT-numbered structures. Per-residue amino-acid CSV values are normalized
natural-log probabilities;
FASTA `score`/`global_score` are **positive mean NLL**, lower is better;
`perplexity` is `exp(entropy)`, an effective alphabet size. Preserve the native
original prediction-batch, target, temperature and sample RNG order. Preserve
the explicit batch size and original input ordering. Encoder arrays have 512
columns; rounded CSV values cannot reconstruct resumable native logits.

## Storage, recovery and errors

These are finite GPU jobs; idle model compute returns to zero. Customer inputs,
scratch, checkpoints and outputs stay in the authorized owner store and its
temporary private job volume. Shutdown retries final upload for at most five
minutes, then deletes scratch even during an outage. Recovery uses only a
verified owner-bucket checkpoint.

The autoregressive and scoring workflows checkpoint **closed whole designs or
FASTA records**. An interrupted in-progress unit is recomputed with its original
index; completed units are retained. Encoder inference remains one atomic
forward. Managed legacy inference checkpoints closed **original prediction
batches** and sampling chunks of at most **32 records within one target and
temperature**. A generated chunk commits all records and RNG state before
honoring a stop; only unfinished or not-yet-uploaded work may repeat. Native
model construction precedes restoration of the saved sampling RNG.

Owner-bucket exports occur between execution quanta. An atomic forward/batch
can exceed five minutes, so five minutes is not a guaranteed recovery-point
bound. Resume the **same run ID** through the shared client or `md_run_resume`,
using a target allowed by the live compatibility contract. Preserve the original
version, parameters, ordering and expiry; the original execution budget remains
cumulative across continuations, with a default of fourteen days. Cross-GPU
floating-point differences can change unconstrained samples; bitwise identity
across GPU types is not promised. With legacy numbering enabled, CPU validation
runs auxiliary ANARCII numbering, but no main ESM-IF1 forward or delivered
scientific unit.

Historical runs retain their original runtime and recovery contract; this
guide does not upgrade an old checkpoint. Check the deployed model contract
for enabled workflows, versions and compatible continuation targets.

Correct structured field/rule errors before retrying. Treat a `403` as an access
failure, not permission to switch identities or regions. Preserve the original
run and idempotency key after an uncertain response; never replay an ambiguous
submission. Report terminal scientific or infrastructure failures with the
public run ID and sanitized error. Training and fine-tuning are not enabled by these inference workflows. Untrusted caller
code and arbitrary checkpoint import are not accepted.
