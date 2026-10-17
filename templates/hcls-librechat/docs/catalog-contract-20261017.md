# Current App catalog contract — 17 October 2026

## Current follow-up: OpenAI-compatible Apps

Source `4fa1c8802e49dbc14a89f1fd6a0cd0a599e12154`, image
`catalog-contract-20261017-r2`, digest
`sha256:17d77ad5676d98f719f42f26c1b57188bdd647643e087ff5715e06dfdbf1d00d`.
The initial correction below covered native and scientific-batch Apps but
omitted the current `openai-chat` protocol. Granting an owner the full catalog
exposed that gap: two valid chat/image Apps caused whole-list rejection.
The parser now accepts that explicit current protocol, retaining operations and
typed tool names. This is not a fallback parser or a model-name allowlist.

The exact image passed 27 catalog/service tests. All five retained clients were
patched without restarting API/MCP or scientific workers. Two fresh internal QA
chat questions each performed one successful catalog read, with no scientific
submissions. The complete owner catalog and all 53 schemas were read separately;
metadata access does not qualify every model's execution. Existing credentials,
owner mappings and other customers' grants were not changed by this client fix.
The earlier full-suite limitations below remain explicitly outside this fix.

Private receipt packet: `rene-all-models-20261017.6UhGX2`.
The [r2 receipt](evidence/catalog-contract-r2-20261017.json), release selector and
README launch button select the same bytes. Original r1 evidence is retained.

## Historical initial correction (r1)

Runtime source: `b66b3266bdc6545152a0a9be44d5c09ceef8df62`.
Published and deployed image `catalog-contract-20261017-r1`, digest
`sha256:6ee584d9b02c6b60cc4c2f7cf6d961185a2afb470d2e4ad878d9990d9c9a4580`.
All five retained clients are patched; the shared default selects this image.

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

## Applied rollout and real chat

`Dockerfile.catalog-contract` overlays the qualified client-update base
`sha256:eaf15340996e3507a40ae0dd377351c6ea35b609ff6e90c36fe52fe009818618`
and runs the installed catalog/service tests. The only changed service export
is `listApps`; its new private helpers remain in its closure. It was replaced
in the existing API and scientific-demos MCP service objects on all five
retained clients. Process identities, chat/worker state, credentials and the
inline report assets were unchanged by the patch. Future MCP processes read
the same updated installed file; no reconnect is required for existing ones.

Two actual QA chat questions (full catalog and molecular-dynamics access) each
made one successful `workbench_list_apps` call, with complete current results
and the expected Apps in the assistant's answer. They completed in 7.1 and
4.9 seconds without scientific submissions. This is observed chat latency,
not a serving-capacity measurement.

Readback through seven existing cached API/MCP service objects across the five
clients matched their exact authorized catalog, including 37/37 for Rene.
Every diagnostic inspector was closed. No account, access grant or model was
changed. The image retains the separately qualified open-tab update notice,
admission recovery and inline report UI; it is not all-workflow qualification.

Private rollout/build/chat/readback evidence: `precheck-inline-20261017.Lsa7Dt`.
The [sanitized release receipt](evidence/catalog-contract-20261017.json), shared
selector and README launch button pin the same immutable image. Provider base
image metadata remains unchanged after in-place patching: future recreation
must select this default and preserve existing state/storage bindings.
