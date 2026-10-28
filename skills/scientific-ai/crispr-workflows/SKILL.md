---
name: crispr-workflows
description: "Plan and run reproducible CRISPR research in the Scientific AI workbench: nuclease guide candidates, CRISPRa/i target-region selection, base and prime editing, reference-site search, validation primers, amplicon QC and screen interpretation. Use for CRISPR, CRISPR-GPT-like assistance, guide RNAs, sgRNAs or pegRNAs; distinguish computed designs from experimental results."
license: CC-BY-4.0
---

# CRISPR research workbench

Use the existing Scientific AI agent and environment-execution tools, not a new
bot or an assumed CRISPR-GPT server. This is an original workflow inspired by
CRISPR-GPT's paper; its private implementation/benchmark are not installed.
Load only the references needed for the user's current phase.

## Start with the goal, not a questionnaire

Infer what is already explicit in the user's files/request. Ask only missing
decisions that change the design: organism/build and locus or sequence; knockout,
activation/repression, or an exact desired edit; relevant cell system; known
editor/delivery constraints. Do not silently choose a human assembly, transcript,
strand, cell type, experimental success criterion or laboratory protocol.

Offer a short plan: **evidence → candidates → specificity/validation → report**.
Run authorized computational steps without repeatedly asking permission. If the
user only wants advice, answer without launching a full workflow. For an easy
demonstration, use the installed synthetic examples and clearly label them synthetic.

## Execute computations, don't invent sequences or scores

The release image provides isolated CPU runtimes. Check the actual paths once:

```sh
test -x /opt/crispr-core/bin/python
test -x /opt/crispr-pegg/bin/python
command -v bowtie
```

If absent, explain the missing runtime. Downloading this skill alone does not
install libraries; do not pretend a model or tool ran. Do not reinstall Python,
add a GPU model or change shared platform settings inside a user workflow.

Write a request JSON using [the request reference](references/requests.md).
Execute the installed adapter through environment-execution:

```sh
/opt/crispr-core/bin/python /app/skill/crispr-workflows/scripts/workflow.py \
  --spec /workspace/my-crispr/request.json \
  --output /workspace/my-crispr/run-001
```

Use actual paths. A new output directory preserves earlier results. The adapter
uses local scratch, keeps original inputs unchanged, and exports the report,
CSV tables, checksums, software versions and elapsed computation time. There is
no hosted CRISPR GPU App or native `op-...` ID for these local CPU calculations.
Use the environment tool's execution ID if waiting/cancellation is needed.
Read the returned exit status/error before proceeding; do not blindly rerun.

- **Knockout:** compute both-strand PAM-compatible candidates. SpCas9 supports
  Rule Set 3 sequence scores; these are not percentages. Cas12a candidates are
  unscored, not assigned a fabricated Cas9 score. Confirm exon/isoform relevance
  separately; a guide in arbitrary DNA does not demonstrate gene knockout.
- **CRISPRa/i:** establish the relevant TSS/isoform and explicit target interval,
  with literature/context rationale. The tool computes candidates in that
  interval but does not predict activation/repression strength. A cleavage
  activity score must not be presented as CRISPRa/i efficacy.
- **Base editing:** specify ABE/CBE and the actual editor's editing window. PEGG
  generates candidate designs. Examine bystanders and all important alleles;
  the initial tool output is not a comprehensive allele prediction. Reject
  incompatible edit types instead of silently changing the requested edit.
- **Prime editing:** use the exact REF/ALT change and flanks. PEGG generates
  spacer/PBS/RTT designs and native scores. Preserve its added 5-prime G and
  sequence orientation labels. Never call an Azimuth/PEGG prediction measured
  editing efficiency. PE3 secondary nicking-guide selection is not automated.
- **Specificity:** Bowtie searches only the explicitly supplied reference, at
  0–3 mismatches, with canonical PAMs, no bulges or unprovided variants. Counts
  include intended targets. Missing search is **unknown**, never “no off-targets”.
  A small FASTA is not a whole-genome screen. Always report assembly and search
  scope. High-confidence experimental specificity needs additional validation.
- **Validation:** Primer3 computes primer candidates, not reference-wide PCR
  specificity. Amplicon QC supports explicitly trimmed full-length single/merged
  reads only; it reports alignment counts, not validated editing efficiency.
  Raw paired-end processing, UMI correction and full CRISPResso2 analysis are
  not installed. Explain the exact gap rather than silently substituting QC.
- **Existing libraries:** use `select` for explicit equality/interval/order/top
  queries against a user's guide CSV. Preserve source scores and missing values.

## Evidence and the rest of the workbench

Use existing Tavily/literature tools for current primary-source evidence. Search
generic organism/cell/editor terms, not private sequences or patient identifiers.
Keep DOI/URL, relevant finding and limitations with the study. Public sequence
retrieval must record accession, version, assembly, strand and coordinate system;
do not silently move between hg19/hg38 or transcript/genome coordinates.

Use [workflow integration](references/integration.md) to connect screen hits,
expression and phenotype data. The installed ClawBio screen-triage, RNA-seq and
local single-cell tools are useful downstream; hosted scVI/scANVI, Cellpose and
structure tools are optional only when scientifically relevant and authorized.
Do not run folding/MD simply because available or equate a predicted structure
with editing efficacy. Discover live schemas and preserve real operation IDs
when a hosted App is used.

Planning/delivery/troubleshooting advice must cite appropriate sources and list
assumptions; do not invent a protocol's concentrations, timings or validation.
The scientist owns experimental decisions. This is computational research
assistance, not clinical advice or a claim of laboratory automation.

## Deliver the result inline

Read `report.json` and the actual CSVs. Report the number of computed candidates,
what was measured/predicted/not assessed, and the next useful decision. Keep the
chat concise; detailed evidence belongs in files.
`guides` counts nominated guides; `reference-alignments` counts reference matches,
including multiple sites for one guide. Never infer rejected guides by subtracting
these counts. Multiple guides targeting a gene are not biological replicates;
do not claim replication unless the supplied experimental design establishes it.
`primer-pairs` counts pairs, not individual primers. `report.html` and its
`report.json` sidecar are the paired files used by the existing inline viewer.

**Copy the runner's returned `inline_markdown` unchanged into the assistant
response.** It is a `/demos?tab=workspace&path=...&file=report.html` link that
activates the existing inline HTML viewer. Do not provide download-only HTML,
invent a UI marker or say it rendered without checking. Downloads are secondary.
If the viewer fails, preserve the computation and report the display error;
never rerun scientific work just to display it.

The report marks predictions and limitations explicitly. Published CRISPR-GPT
scores are not our scores. No claim of outperforming its full system, expert
panel or wet-lab results follows from passing synthetic/unit tests.
