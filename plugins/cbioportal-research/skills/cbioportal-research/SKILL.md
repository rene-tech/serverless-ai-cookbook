---
name: cbioportal-research
description: Explore published cancer-genomics cohorts in cBioPortal, resolve studies and molecular profiles, build study/OncoPrint/comparison links, and query mutation, expression or clinical data after connecting the database MCP. Use for cohort evidence and reproducible cancer research, including CAR-T target hypotheses.
license: Apache-2.0
---

# cBioPortal research

Use the official cBioPortal MCP services for published cancer-genomics data.
The navigator creates validated links and returns study metadata; the database
performs data queries. A generated link is not an executed statistical analysis.

## Select the appropriate connection

- **cbioportal-navigator** is public. Discover `resolve_and_route` once, then
  resolve the requested cancer/study before selecting a navigation tool. Use
  returned study/profile/attribute IDs and values rather than inventing them.
- **cbioportal-database** requires the user's Google sign-in through MCP Settings.
  If disconnected, explain this and continue useful public navigation when that
  answers part of the request. Never repeatedly retry authentication, ask for a
  Google password, substitute another user's token, or fabricate query results.
  After connecting, select this server in the chat tools menu when needed.
- Once a tool is discovered, use it rather than repeating discovery. Read the
  live input schema; server interfaces are under active development.

For actual database questions, discover its current tools and topic guides.
Read only the relevant cBioPortal guide (mutation frequency, clinical data,
sample filtering, or gene expression) through the available guide/resource tool.
Do not assume a fixed ClickHouse table schema. Prefer supported bounded tools;
any SQL must be read-only and retain its exact filters and query with the result.

## Scientific interpretation

1. Preserve an explicitly chosen cohort/version. For discovery, present the
   selected study and alternatives; a navigator's default ranking does not make
   cohorts independent or interchangeable. TCGA releases can overlap. Never sum
   their sample counts as unique patients without verified deduplication.
2. Distinguish patients, samples and events. An alteration denominator is the
   eligible profiled population for that gene/assay/question, not every sample
   in a study. Unprofiled or missing data are not mutation-negative. Report the
   counted unit, denominator, missingness and assay coverage alongside rates.
3. Distinguish mutations, copy-number changes, structural variants, RNA and
   protein measurements. Use the requested clinical marker if available, not a
   subtype or expression proxy. Preserve literal variants and query intent.
4. For expression filters, verify whether the actual profile is raw/normalized
   expression or z-scores, and document the reference population and threshold.
   Do not silently treat a cohort median as a biological cutoff.
5. Survival/group comparisons require explicit endpoint, event coding,
   follow-up, overlapping groups and confounder checks. Describe exploratory
   associations and uncertainty; do not infer treatment efficacy or causality.
6. For CAR-T questions, tumor RNA, copy number or a mutation is hypothesis-level
   evidence. It does not establish surface antigen density/accessibility,
   normal-tissue safety, binder function or patient response. Use the existing
   cancer/immunology/CAR-T skills only as needed for the question.

## Integrate with the workbench

Keep study IDs/version, retrieval date, source links/citations, profile IDs,
filters, query text and result units in a small provenance record. Use Tavily
and primary papers for interpretation. For further computation, discover the
authorized Scientific AI Apps and exact input requirements; aggregate portal
data are not single-cell counts, FASTA sequences or ready simulation inputs.
Never invent a model chain or submit computation just to answer a cohort lookup.

Return a short answer plus verified cBioPortal links for navigation requests.
For requested analysis, save query/results/provenance in a new owned workspace
directory and render a report inline using the standard workbench viewers;
downloads are secondary. Keep absent measurements explicitly unknown.

## External data boundary

The hosted database service records account identity, tool arguments and query
text. Send public research queries only. Do not include protected patient data,
private identifiers, credentials, or private Dropbox/bucket document contents.
Private-cohort analysis needs a separately authorized private data service; a
skill or public MCP connection does not establish clinical validation.

Official references: [MCP services and privacy](https://docs.cbioportal.org/ai-integrations/mcp/),
[database guides](https://github.com/cBioPortal/cbioportal-mcp),
[navigator tools](https://github.com/cBioPortal/cbioportal-navigator).
