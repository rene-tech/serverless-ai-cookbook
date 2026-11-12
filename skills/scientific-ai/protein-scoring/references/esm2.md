# ESM-2 sequence and variant scoring

Discover `esm2-650m` or `esm2-3b`; confirm the current schema before submission.
These are distinct pinned checkpoints, not a model-size parameter of ESMFold.
Default to the requested model. The 3B checkpoint is more expensive; its larger
size alone does not establish better ranking for a particular assay.

Both models use one manifest entry named `workload`, semantic type
`protein-sequence-scoring-tar/v1`, MIME `application/x-tar`, compression `none`.
Upload a plain tar with `sequences.fasta` at its root and, for `score-variants`,
`variants.csv`. `parameters.fasta_file` and `parameters.variants_file` can select
other relative archive paths; there is no automatic enclosing-directory removal.

FASTA IDs are the first whitespace-delimited token after `>` and must be unique.
Sequences accept `ACDEFGHIKLMNPQRSTVWYXBZUO`; whitespace is removed and letters
uppercased, with no silent truncation. Gaps and special tokens are invalid.
The variant CSV requires columns **`id,sequence_id,mutations`**. Variant IDs are
unique, `sequence_id` must match a FASTA ID, and mutations use one-based `A1G`
notation with colon-separated substitutions (`A1G:D3N`). The wild-type letter
must match that FASTA position; a variant cannot repeat a position. PDB residue
numbers are not automatically FASTA positions: retain an explicit mapping.

A synthetic format example (not a biological benchmark):

```text
>reference
ACDEFGHIK
```

```csv
id,sequence_id,mutations
single,reference,A1G
double,reference,A1G:D3N
```

Save those as `inputs/sequences.fasta` and `inputs/variants.csv`, then create
`tar -C inputs -cf workload.tar sequences.fasta variants.csv`. A parameter file
for this operation can contain `{"strategy":"masked-marginals"}`. From the
separate portable client directory, using actual local paths:

```bash
.venv/bin/python invoke-scientific-batch.py \
  --model esm2-650m --tool submit_esm2_650m --operation score-variants \
  --source workload.tar --parameters parameters.json \
  --entry-name workload --semantic-type protein-sequence-scoring-tar/v1 \
  --media-type application/x-tar --compression none \
  --output runs/esm2-variants --idempotency-key esm2-variants-001
```

For `score-sequences`, omit the CSV, select that operation and use its declared
strategy. For 3B, discover `submit_esm2_3b` and select `esm2-3b`; do not change the
requested model silently. The helper creates the canonical manifest using the
real finalized artifact pointer. Skills alone do not install that helper.

`score-variants` defaults to masked-marginal mutant-versus-wild-type natural-log
odds. A larger value means the model favours the mutant in that reference context.
For multiple substitutions, adding single-site marginal scores does not model
epistasis. The explicitly selected pseudo-log-likelihood strategy instead scores
the complete mutant and reference sequences; it requires substantially more work.

`score-sequences` uses masked pseudo-log-likelihood. Report both the sum and
per-residue mean: sums depend strongly on length. These quantities are not a
normalised sequence probability, folding/binding ΔΔG, affinity, toxicity or
clinical pathogenicity. Do not label a score in kcal/mol.

The default context keeps the full sequence. A finite `context_window` is an
explicit approximation centred on each scored site; report it and do not mix
windowed/full-context rankings without checking the effect. Never silently
truncate a long sequence. Batch and token controls bound simultaneous work;
they do not justify dropping records. Recover the complete CSV, checkpoint
revision, input hash, requested strategy, precision and completed-work counts.

Primary sources: [Meta ESM repository and variant scoring example](https://github.com/facebookresearch/esm),
[ESM-2 650M](https://huggingface.co/facebook/esm2_t33_650M_UR50D),
[ESM-2 3B](https://huggingface.co/facebook/esm2_t36_3B_UR50D).
