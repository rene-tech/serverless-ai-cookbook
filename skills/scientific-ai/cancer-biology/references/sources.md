# Sources and adaptation

Reviewed 2026-10-24. This concise skill adapts the MIT-licensed K-Dense
`cancer-biologist` profile at
https://github.com/K-Dense-AI/scientific-agents/tree/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/cancer-biologist
(copyright K-Dense, Inc. 2026; license in `../LICENSE-K-DENSE-MIT`). It omits
unavailable tools and automatic clinical claims, and routes work to current Apps.

Authoritative starting points (verify the actual release/access for each project):
- GDC data and documentation: https://portal.gdc.cancer.gov/ and https://docs.gdc.cancer.gov/
- Cancer dependencies: https://depmap.org/portal/ — CRISPR dependency in a model
  is not automatically a druggable or tumor-selective clinical target.
- Tissue expression: https://www.proteinatlas.org/ — inspect assay and validation;
  do not infer surface accessibility from RNA alone.
- Public expression data: https://www.ncbi.nlm.nih.gov/geo/
- CELLxGENE Census: https://chanzuckerberg.github.io/cellxgene-census/
- Donor-aware single-cell analysis: https://www.nature.com/articles/s41467-021-25960-2
- Rigor: https://grants.nih.gov/policy-and-compliance/policy-topics/reproducibility/guidance

These are discovery routes, not claims of installed packages or completed data
validation. The CAR-T skill's research map contains primary examples and datasets.
