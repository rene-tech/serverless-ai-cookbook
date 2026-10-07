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
tests pass (55 total). Three additional hosted-runner identity tests pass (58
total). Wire tests cover legacy filters, explicit searches,
scoped/empty grants, credential separation, malformed/partial catalogs, and
upstream failures. The skills bundle verifies successfully.

Live acceptance uses `scripts/qualification/catalog_live.py`, the actual
authenticated hosted LibreChat agent/chat routes, normal Kimi K3 configuration,
and the existing internal system/QA key. It replays the reported all-models
question, both getting-started prompts, a follow-up catalog question, molecular
dynamics, and single-cell discovery. It verifies the agent's final answer as
well as tool output. No model execution is authorized by these fixtures.

Two consecutive final cohorts passed: five conversations / six turns each,
three concurrent conversations at a time, 12 turns total. All returned the exact
authorized set. There were 11 full-catalog tool calls and no keyword probes;
one follow-up reused the immediately preceding complete catalog and still named
every App. Plain catalog requests completed in 4.891–5.001 seconds; molecular
dynamics and single-cell questions in 4.850–4.897 seconds. Planning prompts took
11.550–15.868 seconds. These are client-observed turn times, not model startup
benchmarks or a latency SLO.

QA has eight Apps (AMBER, Boltz2, GROMACS, GROMACS MPI, LAMMPS, NAMD,
OpenFold2 and scVI/scANVI), not WhiteLab's 16-App grant set. The wire fixture
covers the exact 16-App catalog; customer binding verification separately checks
the live 16-App list without running inference on a customer key. No scientific
App jobs were submitted by these conversation tests. The real installed skill
loader also passed: 84 total skills, all 78 canonical file hashes verified. The
standalone source-bundle validator rejects the combined installed directory
because it contains 48 additional pinned ClawBio skills; use the installed-loader
test there, not the source-only inventory validator.

The first live harness used requested message IDs, while LibreChat persists
server-assigned IDs. Those accepted conversations were reconciled without
resubmission; the runner now matches exact prompt/parent and rejects ambiguity.
An initial fresh-call-only assertion also rejected a correct immediate follow-up.
The final test permits reuse only of its directly preceding complete tool result,
never an old prose list or filtered result, and still verifies every authorized
App in the answer. Both final cohorts started new conversations, with no recovery
or runtime/configuration changes. Earlier traces remain retained separately.

Machine-readable, payload-free results are in
[the release evidence](evidence/catalog-discovery-20261007.json). Raw private
receipts are under `/home/tux/secure-handoff/fs2-catalog-discovery-20261007/`;
never publish that directory or customer transcripts.

## Customer deployment and closeout

Managed operation `b765b3d1-692c-4a2f-9184-410b01bec163` succeeded. WhiteLab's
replacement endpoint is `aiendpoint-e00axdvs33j7ycdqt1`:

<https://port3080-qxnvfnk6ancxhd3.tunnel.applications.eu-north1.nebius.cloud>

Public HTTPS sign-in, current agent instructions, the new MCP search tool, all
16 existing App grants, the workspace mount and the full starter manifest were
verified. Account identity and all six messages across both original conversations
were preserved byte-for-byte for the compared message fields. The same dedicated
state filesystem, bucket, API/S3/provider credentials and closed registration
remain. No customer model operation was submitted by the release check.

The predecessor `aiendpoint-e00zzbdhd3hkmaxtnc` remains stopped for rollback;
never run it alongside the replacement on their shared state filesystem. The
managed operator can upgrade back to the registered `single-cell-20261007-r5`
release if necessary. Its configuration and private before/after snapshots are
retained. Both task-only QA endpoints were stopped and deleted; the existing QA
filesystem/bucket and the unrelated original QA instance were not removed.

The operator release map was extended without changing the backend image or
other settings. The three API replicas completed their rolling restart. All nine
read-only public website/API routing checks passed before and after the change.
The emitted Helm values fragment is in the backend handover so a later chart
reconciliation retains the new release.

## Main/source integration is distinct from the released binary

The fork had independent molecular-dynamics changes on `main`. They were merged,
not overwritten. Combined source skills are version `2026.10.07.6`; the tested
deployment default remains the immutable R2 image with skills `2026.10.07.5`.
To reproduce R2, use source `fd9ca0c`, not a newer merged tree. A rebuild from
merged source requires fresh composition and live acceptance; neither these
catalog conversations nor a source merge qualify the independent MD candidate.
Source-integration checks cover catalog/seed behavior, advice boundaries, native
MD recovery/reporting, single-cell helpers and the one-click deployment link.
Merge `95337c9` is published on the fork's `main`; 140 Python and 30 Node
source-integration tests passed. These additional tests used an isolated local
environment with the runtime's pinned HTTP/MCP dependencies. They did not mutate
the deployed image or run customer inference. The deployment default and the
one-click launch link both select the qualified R2 digest.
