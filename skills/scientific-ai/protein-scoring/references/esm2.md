# ESM-2 sequence and variant scoring

Discover `esm2-650m` or `esm2-3b`; confirm the current schema before submission.
These are distinct pinned checkpoints, not a model-size parameter of ESMFold.
Default to the requested model. The 3B checkpoint is more expensive; its larger
size alone does not establish better ranking for a particular assay.

The workload bundle contains FASTA sequences and, for mutation scoring, a CSV
linking each variant to its reference sequence. Use the schema/example's exact
column names and one-based reference-sequence positions. PDB residue numbers are
not automatically FASTA positions: retain an explicit mapping when needed.

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
