---
name: car-t-research
description: Research CAR-T and related engineered immune-cell therapies, antigen escape, tumor resistance, resilient cell states and binder-design hypotheses. Connect literature, public single-cell data and authorized Scientific AI models; distinguish computational, preclinical and clinical evidence.
license: MIT
---

# CAR-T research workbench

Help the user understand, compare and investigate engineered T-cell therapies.
This is a research workflow, not an automated treatment-selection or clinical
validation system. Use `immunology-research` or `cancer-biology` only for the
relevant mechanistic background, and `scientific-evidence-review` for synthesis.
Do not load every skill/reference before answering a bounded question.

## Scope and working questions

Andrea Schmidts's public TUM/TranslaTUM research emphasizes tumor resistance,
functional characterization of antigen variants using CRISPR, resilient engineered
T cells and, on the current lab page, generative protein binders. The workbench is
inspired by this scientific scope; it is not affiliated with or endorsed by the lab.
Read [research map](references/research-map.md) for verified starting literature,
public data and tractable computational projects.

For a project, establish the indication, target/product, antigen-positive versus
antigen-negative relapse, timepoint/compartment and desired output. Ask only for
missing facts that change the analysis. Follow the user's actual scope, including
broad education or a short paper comparison.

Separate the potential bottlenecks:

1. Target presence, accessible epitope, density/heterogeneity, splice/sequence
   variants, shedding and normal-tissue expression.
2. Recognition and signaling: binding geometry/avidity, receptor context, tonic
   signaling, co-stimulation and antigen-density response.
3. Cell state: expansion, persistence, metabolic fitness, activation versus
   dysfunction, manufacturing/starting-cell variability and donor effects.
4. Tissue access and tumor context: trafficking, exclusion, stromal/myeloid
   suppression, tumor-intrinsic susceptibility and heterogeneous escape.
5. Translation: strength of model evidence, endpoint/follow-up, adverse events,
   feasibility and unresolved off-tumor/cross-reactivity risk.

Compare single/dual targeting, logic-gated or armored approaches, TCR-T, TILs,
bispecifics and other relevant modalities by the mechanism they address. Do not
declare a universally best construct from unrelated studies. Distinguish autologous
and allogeneic assumptions. Avoid treating a healthy-donor in-vitro result as
patient-derived or clinical evidence.

## Use the rest of the workbench

| Question | Existing tools/skills | What they do not establish |
| --- | --- | --- |
| What is known now? | Tavily, primary papers/registries, `scientific-evidence-review`, Dropbox papers | An exhaustive review from a few searches |
| Which cell states correlate with response? | `single-cell-analysis`, live scVI/scANVI, public GEO data | Causality, independent patient validation or cell-surface accessibility |
| How could a target variant change recognition? | Actual sequence/isoform, structure skills, Boltz/OpenFold/AF3 if authorized, visualization | Experimental affinity, cytotoxicity or clinical escape |
| Which binder hypotheses merit follow-up? | `binder-design-campaigns`, `protein-binder-design`, `rfd4-proteina`, actual Apps/schemas | Functional CAR performance or safety from confidence scores |
| How to study conformational uncertainty? | `bioemu2`, GROMACS/OpenMM/other MD skills | Converged ensembles from short runs or validated binding free energy by default |
| How to critique perturbation evidence? | `crispr-workflows`, screen statistics and orthogonal evidence | That a screen hit is causal or a clinical-ready edit |

Discover the full authorized catalog once; read the chosen live schema and its
scientific input requirements. Never invent a hosted model, missing parameter,
dataset or measurement. Keep computational candidates clearly labelled and
preserve the existing precheck, submission-once, saved-study and recovery behavior.
Do not auto-run a large binder campaign merely to answer a literature question.

## Evidence and deliverables

Maintain a claim/evidence/limitation table with DOI/PMID or trial ID, study type,
sample unit, controls, endpoints and source date. Clinical response, survival,
CRS/ICANS, infections, cytopenias and long-term risks need current primary clinical
and regulatory sources; these skills do not choose patient treatment or doses.
Keep preprints, abstracts, company announcements and peer-reviewed studies distinct.

Default research output: direct answer; strongest supporting and conflicting
evidence; uncertainty; one discriminating next analysis. For an executed project,
also retain a source ledger, data/code provenance, negative results, measured
model outputs and an inline report with links to the original artifacts. Never
replace absent evidence with confident prose. Example prompts are in the research map.
