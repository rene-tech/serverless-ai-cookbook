# Complete App discovery — 7 October 2026

## Incident and fix

WhiteLab asked the normal Scientific AI agent to fetch every model available to
its key. The agent made 14 keyword-filtered catalog calls, 13 of which returned
no matches, then enumerated 11 of the 16 authorized Apps. Literal `all` was
treated as a search term. Missing search matches were incorrectly interpreted as
missing capabilities, including single-cell and molecular-dynamics Apps. An
unfiltered catalog call returned all 16 in approximately 462 ms; this was not a
GPU, model-serving, or authorization outage.

The shared workbench now has distinct contracts:

- `workbench_list_apps` has no filters. It always returns the complete catalog
  for the caller's key, even if an old chat/tool cache supplies `query`.
- `workbench_search_apps` is a separate, deferred literal-search tool. Its
  response explicitly distinguishes search matches from authorization.
- Catalog responses carry `catalog_scope`, `total_authorized_count`, and
  `filter_applied`. Both upstream catalogs must be readable and well-formed;
  unavailable or malformed data is an error, not a successful empty list.
- Core and tutorial agent instructions require one full listing, retaining the
  returned groups and every App for an all-models question. Domain questions
  select from those groups instead of probing synonyms.
- Bundled scientific-gateway and tutorial skills follow the same contract;
  stale text saying molecular dynamics is unavailable has been removed.

No model grants, API-key expiry, concurrency limits, agent model, or inference
runtime was changed. This release fixes discovery; it does not establish new
scientific validity or all-App readiness claims.

## Exact release

- Repository: `rene-tech/serverless-ai-cookbook`.
- Runtime source: `fd9ca0c` on `agent/fs2-basel-workbench-20261007`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:catalog-20261007-r2`.
- OCI index: `sha256:243ba1dc462ea8e9dc72d620509cc09add24df325297d591e7cb5e4b62438eff`.
- amd64 manifest: `sha256:12e0015c297a09fbfc2b6e0ff2a604a8f31026a21c971e870c266d62a348e905`.
- Skills: `2026.10.07.5`, 36 skills / 78 checksum-locked files.
- Previous customer release: `single-cell-20261007-r5`, index
  `sha256:92b18aa638f222d1b5b53c61e3c4cad9e11e5e5abc032e856a6a8d69388086fc`.

`Dockerfile.catalog` combines the unchanged R5 single-cell overlay and the
discovery changes on the exact pinned branding/state parent used by R5. It
retains SciPy 1.16.3 and passes dense/CSR/CSC backed-H5AD runtime checks and
`pip check`. It has 127 layers and 3,714,953,758 compressed bytes. Do not add
another overlay to this inherited layer stack.

The first candidate (`catalog-20261007-r1`) had 128 layers, with no writable-layer
headroom on Serverless. It was rejected before customer deployment. Its isolated
QA endpoint was stopped and deleted; the QA filesystem and bucket were retained.
It is not a qualified release or a deployment default.

## Qualification and deployment

Offline checks: 19 service tests, four wire-level MCP catalog tests, three
three-way seed-merge tests, four tool-options tests, and 25 configuration/seed
tests pass (55 total). Wire tests cover legacy filters, explicit searches,
scoped/empty grants, credential separation, malformed/partial catalogs, and
upstream failures. The skills bundle verifies successfully.

Live acceptance uses `scripts/qualification/catalog_live.py`, the actual
authenticated hosted LibreChat agent/chat routes, normal Kimi K3 configuration,
and the existing internal system/QA key. It replays the reported all-models
question, both getting-started prompts, a follow-up catalog question, molecular
dynamics, and single-cell discovery. It verifies the agent's final answer as
well as tool output. No model execution is authorized by these fixtures.

Live gate and customer deployment results are pending. Do not treat the offline
passes or the image publication alone as customer acceptance. Raw private
receipts are under `/home/tux/secure-handoff/fs2-catalog-discovery-20261007/`;
never publish that directory or customer transcripts.
