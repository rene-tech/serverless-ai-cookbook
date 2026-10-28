---
name: cancer-biology
description: Explain cancer mechanisms, evaluate cancer targets and resistance hypotheses, and plan reproducible public-data analyses. Use for tumor biology, evolution, microenvironment, genomics and preclinical evidence; use car-t-research for engineered T-cell therapy.
license: MIT
---

# Cancer biology research

Frame the question by cancer type, molecular subtype, anatomical compartment,
treatment history and the claim being tested. If the user is learning, explain
the mechanism with a concrete example; do not turn a simple explanation into
a research project. For research, distinguish association, mechanism, preclinical
efficacy and clinical evidence. Load `scientific-evidence-review` for a literature
comparison or a consequential mechanistic claim.

## Reason from competing explanations

- Treat a tumor as evolving, heterogeneous populations. Separate clonal selection,
  reversible state changes, lineage switching and technical detection failure.
- Map the relevant hallmark: growth signaling, cell-cycle control, death resistance,
  replication/repair, metabolism, angiogenesis, invasion, immune evasion or plasticity.
  A pathway-enrichment result is a hypothesis, not a demonstrated mechanism.
- Separate tumor-intrinsic effects from fibroblast, myeloid, vascular, lymphocyte
  and extracellular-matrix effects. Blood, primary tumor and metastases differ.
- A recurrent alteration is not automatically a driver or therapeutic dependency.
  Check lineage, copy number, allele, expression, perturbation specificity and
  orthogonal evidence. Distinguish predictive from prognostic biomarkers.
- Select evidence appropriate to the claim: cell lines, organoids, xenografts,
  immunocompetent models and patient material each omit parts of human disease.
  Do not infer an intact human immune response from an immunodeficient xenograft.

## Work with data and platform tools

Discover a current source and its release before downloading: GDC/TCGA for tumor
genomics, DepMap for cancer dependency hypotheses, Human Protein Atlas for tissue
expression, GEO/CELLxGENE for single-cell data. Distinguish controlled raw patient
data from openly released processed matrices. Check sample identities, assay,
license, access conditions and biological replication. RNA abundance does not
establish accessible surface protein or absence of healthy-tissue toxicity.

Use the existing `single-cell-analysis` skill for scVI/scANVI, and the live Apps
catalog for other supported models. Structural prediction, docking, binder design
and molecular dynamics address molecular hypotheses; none proves tumor killing,
selectivity, CAR signaling, clinical response or safety. Keep the scientific
question and validation criterion explicit before spending compute.

Return a concise conclusion, evidence table, competing explanations and the next
discriminating analysis. Save actual inputs, identifiers, releases, code, seeds,
outputs and limitations under a new owned `/workspace/my-studies/` directory.
Use [sources and attribution](references/sources.md) for starting sources and the
reviewed upstream material; refresh literature for any current-state claim.
