# Original CRISPR workbench · 22 October 2026

An original, local computational workflow inspired by the CRISPR-GPT paper,
not its unlicensed code or private agent. Rene approved independent testing
because the complete Gene-editing bench is unavailable. This release does
**not** establish superiority over CRISPR-GPT or experimentally validated editing.

## Using it

In a new Scientific AI chat, ask:

> Run the synthetic CRISPR example. Compare nuclease, base-editing and
> prime-editing candidates, check the supplied reference, design validation
> primers, and show the reports inline. Explain what still needs validation.

For real data, supply your FASTA/guide table or exact desired edit, organism and
assembly, and cell/editor context. The agent asks for missing scientific choices,
loads `crispr-workflows`, and executes the installed tools. Outputs live in your
existing owned workspace, with CSV, JSON, HTML, input hashes and software versions.
Local CPU calculations are not Serverless GPU operations and have no `op-...` ID.

Implemented operations: SpCas9/Cas12a candidate enumeration, SpCas9 RS3 scoring,
explicit-reference Bowtie mismatch search, PEGG base/prime design, Primer3 primer
design, exact guide-table filtering, and trimmed single-amplicon read QC. Existing
ClawBio screen-hit triage can follow the workflow. Expression, single-cell and
imaging tools remain separate scientifically appropriate follow-ups, not automatic
substitutes for experimental validation.

## Independent evaluation

The numerical suite includes 73 tests, including 60 independently enumerated
both-strand/PAM cases, published RS3 values, Bowtie versus a brute-force reference
search, six actual computation paths, reference-allele and PEGG sequence checks,
50 table-filter cases, artifact hashes, empty designs, input errors and HTML escaping. The existing ClawBio
screen-triage executable also completed its synthetic example. Exact final-image
and browser cohort counts are recorded in the release receipt.

The agent experiment uses 50 independently authored table-query requests, three
repetitions, and the same `Qwen/Qwen3-235B-A22B-Instruct-2507`, temperature 0.2,
700-token completion limit and four workers in both arms. Both receive the
same explicit request schema; the treatment additionally receives the installed
skill. Expected answers are retained only in the scorer, not the model prompt.

| Exact JSON request | Baseline | With skill |
| --- | ---: | ---: |
| Correct / attempts | 150 / 150 | 150 / 150 |
| Median response time | 1.82 s | 1.73 s |
| Total tokens | 43,434 | 272,034 |

That instruction revision tied; it did not demonstrate a meaningful latency
advantage. A subsequent repetition with clarified guide-count instructions
scored **150/150 baseline versus 145/150 with the skill**: five skill-arm responses
invented `where` or `filters` wrappers which the runner correctly rejected.
Median times were 1.38/1.29 seconds and tokens 43,434/280,774. This prompt-only
experiment supplies the skill body but no reference-file reader; the real
workbench reads `references/requests.md` and executes validated requests. The
last output-format-only revision was not rerun through this benchmark. Neither
revision supports a superiority claim; loading more instructions can make a
simple task worse. These are
repeated simple cases, not independent biological experiments or a population
capacity estimate. Reproduce with `crispr/benchmark_agent.py`; the API credential
comes from the environment and is never recorded.

An earlier diagnostic run used an ambiguous schema shorthand: baseline 76/150,
skill 115/150. Those failures prompted a common-schema correction in **both**
arms. They are retained as evidence, not reported as a skill superiority result.

## Boundaries

- No wet-lab experiments, blinded expert assessment, delivery ranking or full
  published 288-case benchmark replication was performed.
- A supplied small reference is not a whole-genome specificity screen. Bowtie
  searches 0–3 mismatches and canonical PAMs, not bulges or absent variants.
  Whole-genome throughput and large-library memory limits are unqualified.
- CRISPRa/i needs an explicit TSS interval; no activation efficacy is predicted.
  Base-editor bystanders, PE3 nicking guides and assay specificity need further
  review. Scores are predictions, never measured editing efficiency.
- Amplicon QC is **not** full paired-end/UMI CRISPResso2 analysis or a validated
  allele/editing-efficiency estimate. Screen triage is not a statistical screen
  caller. Neither replaces controls, replicates or experimental interpretation.
- Provider VM replacement must use the new pinned default; additive patches do
  not change old provider image metadata. No endpoint, bucket, key, agent model,
  study supervisor or customer conversation is replaced by this rollout.

## Sources and implementation

- [CRISPR-GPT paper](https://www.nature.com/articles/s41551-025-01463-z)
  and [figure-label correction](https://www.nature.com/articles/s41551-025-01589-0).
- The local [runtime README](../crispr/README.md) describes architecture and
  upstream methods. [NOTICE](../crispr/NOTICE.md) records independent licenses.
- `Dockerfile.crispr` builds isolated Python environments over the exact existing
  AF3/BioEmu2 image. Lockfiles pin all packages and hashes. No new backend,
  scheduler, bot, credential or GPU service is introduced.

The machine-readable release receipt records the exact image, browser evidence,
retained-client activation and measured scope. It must not imply every historical
Scientific AI workflow has been requalified.
