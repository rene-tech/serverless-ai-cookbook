# Current App catalog contract — 17 October 2026

Candidate source: `b66b3266bdc6545152a0a9be44d5c09ceef8df62`.
Production deployment remains pending until the release owner records the
published image digest, retained-client readback and actual QA chat acceptance.

## Cause and correction

The reported catalog tool failed because `appContract` spread `capabilities`
as an array. The current API supplies a structured object, producing
`TypeError: (item.capabilities || []) is not iterable`. Both upstream catalog
requests succeeded. The generic workbench error led the assistant to call this
transient; it was a deterministic client contract mismatch.

`workbench_list_apps` now reads the complete, caller-authorized `/v1/models`
catalog once. It uses current `execution_mode`, `protocol`, `operations` and
`tool_name` fields. Scientific batches are no longer classified twice by
merging the complete catalog with its scientific subset. Compact chat output
omits raw capability objects, input schemas and runtime/device metadata.
Malformed catalog records fail explicitly with `CATALOG_CONTRACT_INVALID` and
`retryable: false`; they never become an empty or partial success. No cached
catalog, old-field parser, grant changes or model-specific eligibility was added.

## Candidate evidence

- All 26 catalog/service tests passed locally and at the installed paths in the
  exact base image. Cases cover current object capabilities, typed tool names,
  scoped/empty catalogs, malformed records and previously unseen App IDs.
- Isolated Node processes against the live API returned exactly 9/9 System QA
  Apps and 37/37 Apps for Rene's read-only scope, each from one successful
  catalog request. These checks changed no deployed file or process and ran
  no customer inference or scientific workload. They are not chat acceptance.
- The broader exact-base suite reported **103 passed, two failed**. Both failures
  reproduce on unchanged source `f64748e`: `studies.test.cjs:24` reports
  `STUDY_OBSERVER_EXIT` while testing whole-study authorization, and
  `studies.test.cjs:44` throws an undefined `.map` in the Runs rendering test.
  This release does not claim that the whole suite passed or repair those tests.

Private receipts: `catalog-failure-20261017.sc7CKw/checks.json`,
`qa-catalog-probe.json`, `qa-candidate.json`, `rene-candidate.json`,
`focused-base-tests.log`, `demos-base-tests.log` and `studies-base-unchanged.log`.

## Rollout handoff

`Dockerfile.catalog-contract` overlays the qualified client-update base
`sha256:eaf15340996e3507a40ae0dd377351c6ea35b609ff6e90c36fe52fe009818618`
and runs the installed catalog/service tests. The only changed service export
is `listApps`; its new private helpers remain in its closure. The release owner
must preserve existing processes while updating that export in the API and
each scientific-demos MCP process, then verify the actual QA chat path.
The image digest, default pointers and applied fleet receipts belong to that
separate release closeout; this candidate report does not assert deployment.
