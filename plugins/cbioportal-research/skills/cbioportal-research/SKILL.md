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

- **cbioportal-navigator** is public. Call the available `resolve_and_route`
  tool; discover it once only if its schema is not already available. Resolve
  the requested cancer/study before selecting a navigation tool. Use
  returned study/profile/attribute IDs and values rather than inventing them.
- **cbioportal-database** requires the user's Google sign-in through MCP Settings.
  If disconnected, explain this and continue useful public navigation when that
  answers part of the request. Never repeatedly retry authentication, ask for a
  Google password, substitute another user's token, or fabricate query results.
  After connecting, select this server in the chat tools menu or the saved
  agent's tools configuration when needed. Connection authorization and agent
  tool selection are separate. A "No MCP server matched" discovery result
  does not prove missing authorization: check that the connected server is
  selected for the current agent, and check already-loaded tools before
  repeating discovery. Do not ask the user to revoke a working connection.
- Once a tool is discovered, use it rather than repeating discovery. Read the
  live input schema; server interfaces are under active development.
- Loading this skill or reading tool documentation is preparation, not the
  requested lookup. Execute the tool and report its observed result; do not
  return its instructions or schema as the answer.

For actual database questions, discover its current tools and topic guides.
Read only the relevant cBioPortal guide (mutation frequency, clinical data,
sample filtering, or gene expression) through the available guide/resource tool.
Do not assume a fixed ClickHouse table schema. Prefer supported bounded tools;
any SQL must be read-only and retain its exact filters and query with the result.

## Large results and export

Inspect the actual tool result before declaring a response-size limit. The
database's `truncated`, `returned_rows` and `note` fields describe its row cap;
the live `clickhouse_run_select_query` schema defines `max_rows`. A client marker
such as `truncated: ... chars exceeded ... limit` is a separate character limit.
A shortened UI/log preview or difficulty copying a result is not evidence that
the database truncated it. Complete small results can exceed a preview's size.

Prefer a bounded server-side aggregate for aggregate questions. For row exports,
select only needed columns and use deterministic SQL pages: a stable unique
`ORDER BY` with `LIMIT` and `OFFSET`, or a keyset predicate when supported.
Keep each page within both row and client character limits; inspect it before
requesting the next. The absence of a cursor field in the MCP schema does not
mean SQL pagination is unavailable. Record filters, ordering, expected count,
page counts and duplicate checks; never call a capped export complete.

Reuse complete saved results when available. For programmatic handoff, use only
tools and output-reference features actually exposed by the current client;
do not invent an export tool, transcribe a large matrix by hand, or manufacture
placeholder data. If a file handoff is unavailable, state that exact boundary
and use a supported bounded query or clearly labelled official public download.
An authenticated database MCP does not grant direct shell access to its backing
ClickHouse service. Do not probe guessed credentials or search local secret
files after a shell 401; continue through the authorized MCP connection.

## Copy-number analysis

Read the live study guide and CNA guidance before querying. Verify the profile
and its observed values: an AMP/deep-deletion event table may omit gains, shallow
deletions and diploid measurements. A zero result in that table does not establish
absence of the omitted categories; inspect the full discrete profile instead.
Preserve nonstandard numerical values literally unless a source defines their
meaning; never turn them into gain/deletion categories by guessed thresholds.
Use authoritative profile membership or coverage to identify profiled samples,
not the presence of records for a single convenient gene.

For "top genes", aggregate across all measured genes in the requested cohort,
with bounded returned rows and an explicit ranking rule. Do not substitute a
hand-picked driver list or interpret truncated output as a complete ranking.
Combine related genes and groups in one bounded server-side query where
supported, then inspect its result before issuing more calls. Avoid parallel
one-call-per-gene fan-out or generating many speculative queries at once.
Retain the full aggregate result when it fits the service's response limits.
Use gene-specific eligible coverage and nonmissing measurements for denominators,
and report missing/off-panel data separately from unaltered calls. Include each
requested alteration category even when its observed count is zero, explaining
when the source profile does not resolve that category.

Keep the exact clinical sample-type values, count unique samples and patients
separately, and check overlap between groups. A primary/metastasis split is not
automatically a paired comparison. Save the executed queries and responses;
label any explicitly permitted REST or bulk-data fallback by its actual source,
never as a successful database MCP query.

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
