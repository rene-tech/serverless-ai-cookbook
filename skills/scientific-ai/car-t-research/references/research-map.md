# Research map and practical starting points

Reviewed 2026-10-24 using Tavily search/extraction, official lab pages, primary
publication pages and dataset records. This is a curated starting map, not a
systematic review or a permanently current treatment catalogue. Refresh the
question-specific evidence before claiming the state of the art.

## Schmidts research context

- [TUM profile](https://www.professoren.tum.de/tum-junior-fellows/schmidts-andrea-1)
  and [current clinical department lab page](https://med3.mri.tum.de/de/forschung/schmidts-lab):
  tumor resistance, antigen variants, CRISPR characterization, resilient CAR-T
  and generative de novo binding domains. These establish the lab's public scope,
  not an endorsement of this workbench.
- Mergen et al., *Engineering de novo binder CAR-T cell therapies with generative
  AI*, [bioRxiv version 1](https://www.biorxiv.org/content/10.1101/2024.11.25.625151v1),
  DOI 10.1101/2024.11.25.625151. The retrieved record is a **preprint**. It connects
  RFdiffusion-derived BCMA binding domains to experimental CAR-T evaluation,
  including a resistant antigen variant. Inspect subsequent versions/publication
  before citing it as current; do not label it clinical efficacy evidence.
- Larson et al., [CAR T cell killing requires the IFNγR pathway in solid but not
  liquid tumours](https://pubmed.ncbi.nlm.nih.gov/35418687/), *Nature* 2022,
  DOI 10.1038/s41586-022-04585-5. A useful tumor-intrinsic resistance/CRISPR-screen
  example. Keep the tested model context; do not universalize the title to every tumor.
- Schmidts et al., [trimeric APRIL-based CAR binding domains](https://pubmed.ncbi.nlm.nih.gov/31698455/),
  *Blood Advances* 2019. A ligand-based recognition example, distinct from an scFv.
- Choi et al., [CAR-T cells secreting BiTEs](https://pubmed.ncbi.nlm.nih.gov/31332324/),
  *Nature Biotechnology* 2019. Preclinical antigen-escape strategy; the title's
  absence of detected toxicity is limited to the tested system.
- Petri et al., [prime editing with RNP complexes](https://pubmed.ncbi.nlm.nih.gov/33927418/),
  *Nature Biotechnology* 2022. Gene-editing method evidence, not proof of a
  deployable therapeutic edit in a specific CAR-T product.

## Broader mechanistic and translational anchors

| Question | Starting primary source | Interpretation boundary |
| --- | --- | --- |
| Dual targeting after BCMA loss | [Larson et al. 2023, anti-TACI/BCMA](https://www.nature.com/articles/s41467-023-43416-7), DOI 10.1038/s41467-023-43416-7 | Preclinical efficacy and tissue-expression evidence; lower RNA in a tissue is not demonstrated human safety |
| Chronic activation and dysfunction | [Lynn et al., c-Jun](https://pmc.ncbi.nlm.nih.gov/articles/PMC6944329/) | Mechanistic intervention in tested systems; context-specific outcome, not a universal exhaustion fix |
| Long persistence | [Melenhorst et al. 2022](https://doi.org/10.1038/s41586-021-04390-6) | Two long-followed CLL patients do not define every product/indication |
| Long-term CAR-T cell states | [Bai et al. 2024](https://www.nature.com/articles/s41586-024-07762-w), DOI 10.1038/s41586-024-07762-w | Atlas associations and follow-up experiments have distinct evidentiary roles |
| Solid-tumor clinical translation | [Choi et al. 2024, CARv3-TEAM-E](https://pmc.ncbi.nlm.nih.gov/articles/PMC11162836/), DOI 10.1056/NEJMoa2314390 | Small early-phase glioblastoma report; assess durability, selection and toxicity before extrapolation |
| Newer in-vivo screen context | [Liu et al. 2026](https://www.nature.com/articles/s41586-026-10906-9), published 12 August 2026, DOI 10.1038/s41586-026-10906-9 | Human T cells in a tumor-bearing mouse system; do not present screen hits as human clinical benefit |

Follow newer work on antigen-density sensing, accessibility/glycosylation,
trafficking, metabolic and epigenetic cell states, allogeneic rejection/GVHD,
manufacturing variability, logic gating and in-vivo engineering. Evaluate actual
data, not novelty labels. Retrieve current trial registries and jurisdiction-specific
regulatory sources for approvals, status or adverse-event claims; no frozen list
of approved products is maintained here.

## Public-data projects that can start without new experiments

1. **Response-associated states, with donor-aware validation.**
   [Haradhvala et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC9509487/)
   links processed data [GSE197268](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE197268)
   and prior infusion-product data [GSE151511](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE151511).
   GSE197268 raw sequencing is separately controlled in dbGaP phs002922.v1.p1.
   The [HCA project](https://explore.data.humancellatlas.org/projects/c0d82ef2-1504-4ef0-9e5e-d8a13e45fdec)
   offers another documented discovery route. Direct GEO extraction failed during
   this review; the paper/HCA linkage was verified, but files were not downloaded.
   Inspect actual metadata and access before selecting a subset. Keep donors,
   longitudinal samples and product types explicit; compare response associations
   with uncertainty rather than predicting individual patient treatment.
2. **Long-persistence atlas critique/reanalysis.** Bai et al. lists
   [GSE262072](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE262072).
   The paper says analysis code is available from authors on reasonable request;
   do not invent a public code repository or claim exact reproduction without it.
3. **Tumor-context CRISPR hit appraisal.** Liu et al. 2026 supplies screen tables
   and [GSE330227](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE330227).
   Compare abundance versus effector-function endpoints, biological replication,
   multiple testing and orthogonal validation. Use the existing CRISPR skill for
   computational planning; this map is not a wet-lab protocol.
4. **Variant-aware binder hypothesis.** Start from verified antigen sequences,
   isoforms, variant notation and structural evidence. Compare wild type/variant
   with the same prediction treatment. Run a bounded authorized design task only
   when requested, retain negatives, and label predicted contacts/confidence.
   A structural score does not qualify a CAR-T product.

## Example prompts

- “Explain how cancer escapes immune detection, then distinguish CAR-T recognition
  from TCR recognition. Use one example and cite the primary evidence.”
- “Compare the Mergen de novo binder CAR-T preprint with the anti-TACI/BCMA study.
  What was demonstrated experimentally, what remains unproven, and what follow-up
  analysis can our platform actually support? Do not run models yet.”
- “Find current primary evidence for antigen-positive versus antigen-negative CAR-T
  relapse. Build a source-linked mechanism/evidence/limitation table and identify
  conflicting results.”
- “Inspect GSE197268 and design a small donor-aware single-cell reanalysis using
  the available platform tools. Show access, input, validation and compute plan
  before downloading the full dataset.”
- “Find papers in my specified Dropbox project, compare their methods and
  conclusions, verify citations, and show the evidence report inline. Preserve
  originals and keep private excerpts out of public searches.”

## Reuse and attribution

Adapted in part from K-Dense's MIT-licensed `immunotherapy-scientist` profile at
`K-Dense-AI/scientific-agents@98c7fae46648724e1a43a1f2b207b0c82fcc462e`.
The adaptation is shorter, research-focused, corrects the general CAR-versus-MHC
distinction, omits treatment instructions, and uses actual Scientific AI tools.
The upstream license is included as `../LICENSE-K-DENSE-MIT`.
Reviewing a third-party skill does not validate its scientific claims or advertise
its optional services as installed platform tools.
