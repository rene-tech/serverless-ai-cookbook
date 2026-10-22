# Scientific AI CRISPR workbench

Original research workflow inspired by Qu et al., CRISPR-GPT, not a fork,
reimplementation of its private prompts, or claimed reproduction of its results.
Portable guidance lives in `skills/scientific-ai/crispr-workflows`.

## Architecture

Use the existing scientific agent, environment-execution MCP, authenticated
workspace and inline report viewer. No new bot, GPU App, database, API key,
scheduler or public sequence-upload service. Computation stays on the user's
CPU workbench. A run reads a JSON specification, uses independently licensed
scientific libraries, and writes input hashes, software versions, tabular results
and an HTML report in a fresh workspace directory.

- Rule Set 3: SpCas9 sequence activity predictions (not probabilities).
- PEGG 2.1.0: base/prime editing candidate designs and native prediction scores.
- Bowtie 1: mismatch-only candidate-site search against an explicitly supplied
  reference. No bulges, no implicit complete-genome claim, no zero-risk verdict.
- Primer3: validation primers; specificity requires a separate reference check.
- Edlib: read-to-reference alignment for bounded single-amplicon exploratory QC.
- Installed ClawBio screen-triage, RNA-seq and single-cell workflows: downstream
  analysis, without claiming that guide design establishes biological outcome.

The two pinned Python environments isolate incompatible upstream model
dependencies. The workbench's normal Python, agent and hosted-model tools remain
unchanged. Runtime data are never sent to external design services. Literature
lookup uses the existing Tavily tool with non-sensitive search terms.

## Evaluation boundary

The CRISPR-GPT article describes 288 cases (50 planning, 50 guide-query, 50
delivery, 138 Q&A). Its Supplementary Note C gives methods/rubrics but not the
complete expert-labelled dataset. The guide test evaluates table-query function
selection, not de novo guide efficacy. Main text and supplement also differ in
the number of Q&A questions and expert interaction requests; do not conflate
them. The December 2025 correction fixes figure colour labels.

Use independent synthetic computational ground truth and matched agent runs;
report these separately from the published benchmark. Expert-blinded evaluation
and wet-lab validation remain necessary before asserting scientific superiority.

Primary references:

- https://www.nature.com/articles/s41551-025-01463-z
- https://www.nature.com/articles/s41551-025-01589-0
- https://github.com/gpp-rnd/rs3
- https://github.com/samgould2/PEGG2.0/tree/5e3d6003717e156cbb5abc4cdefd3f1a32362c05
- https://bowtie-bio.sourceforge.net/manual.shtml
- https://libnano.github.io/primer3-py/
- https://github.com/Martinsos/edlib

Do not package CRISPR-GPT's unlicensed code or guide tables. PrimeDesign,
CRISPR-HAWK, CRISPRware and CRISPResso2 have additional commercial/redistribution
restrictions and are not installed by this workflow.
