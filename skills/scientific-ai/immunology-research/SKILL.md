---
name: immunology-research
description: Explain and critically analyze innate and adaptive immunity, antigen presentation, T-cell states, tumor immunity and immune profiling. Use for mechanistic reasoning and research interpretation, including flow cytometry and TCR/single-cell studies.
license: MIT
---

# Immunology research

Locate the question in a species, tissue, disease and time course. Explain basic
concepts when asked; otherwise distinguish phenotype, specificity, function,
kinetics and causal mechanism. Use `scientific-evidence-review` when synthesizing
papers and `car-t-research` for CAR-specific work.

## Mechanistic distinctions that change the answer

- Innate sensing, antigen presentation, adaptive clonal selection, co-stimulation,
  tolerance and memory interact; avoid treating the immune system as a single
  activation score. Include B cells/antibodies/complement, NK cells, myeloid cells
  and stromal context where relevant, rather than assuming every effect is T-cell driven.
- Conventional TCR recognition depends on peptide–MHC and the restricting allele.
  Conventional CARs recognize accessible cell-surface antigen directly and do
  **not generally require peptide–MHC**. TCR-mimic CARs are an explicit exception.
  HLA/B2M loss can affect TCR responses and NK context; it is not a universal
  explanation for loss of direct CAR antigen recognition.
- Binding, receptor occupancy, signaling, cytokine production, proliferation,
  serial killing and durable tumor control are different measurements.
- PD-1 or another single marker does not establish exhaustion. Compare acute
  activation, chronic dysfunction, progenitor/terminal exhausted states, memory,
  senescence and tissue residency using functional and multimodal evidence.
- Cytokine effects depend on producing/responding cells, receptor state, timing
  and tissue. Do not turn IFNγ or a Th1/Th2 signature into a universal benefit/harm rule.
- Human and mouse immune systems, blood and tumor, fresh and frozen samples,
  stimulation and resting conditions are not interchangeable.

## Analysis choices

For cytometry, inspect compensation/unmixing, viability and doublet exclusion,
gating hierarchy, appropriate FMO controls, instrument/batch effects and both
absolute counts and denominators. Distinguish staining controls from biological
negative controls. Preserve FCS files and gating/analysis provenance; use MIFlowCyt
and MIATA as reporting references, without claiming formal compliance from a checklist.

For single-cell/TCR data, inspect donor/timepoint/product, raw counts, QC,
doublets/ambient RNA, sample demultiplexing and pairing of expression with V(D)J.
Keep clonotypes and longitudinal samples from the same patient together in
validation splits. Cells are not independent patients. Confirm receptor
specificity experimentally or label it predicted; shared sequence does not
establish identical function. Route computation to `single-cell-analysis` and
the current authorized schema, not an assumed preinstalled package.

Report the supported immune mechanism, alternative explanation, evidence type,
uncertainty and what observation would distinguish them. Sources/attribution:
[references/sources.md](references/sources.md).
