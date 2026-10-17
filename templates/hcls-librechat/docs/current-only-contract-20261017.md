# Current-only workbench contract — 17 October 2026

Source change for the native-operation-identity release; not a live rollout or
customer-readiness claim. Root owns integration, image qualification and rollout.

## Current contracts

- Native job/session IDs remain unchanged (`op-`, `ses-`, `sync-`). Local study,
  execution-process, consultation and artifact UUIDs identify different objects.
- All execution families use `get_operation`, `get_operation_result` and
  `cancel_operation`. Native checkpoint continuation uses `resume_scientific_run`.
- Named MD/scVI/MPI tools take `request` and `idempotency_key`; staged scientific
  tools (including Protenix/LeRobot/Complexa) take the run fields directly plus
  `idempotency_key`. The helper selects from the exact discovered schema before
  uploading/submitting; it never tries an alternate shape after failure. Native
  typed tools retain their published model-specific input. Current MD/staged, native
  endpoint and speech result envelopes remain distinct; they are not old versions.
- Uploads use `upload_id`, never a job ID. Finalization returns
  `{ "state": "finalized", "artifact": { ... } }`. Multipart commands use the
  outer/path upload ID and `action`, optional `multipart_upload_id` and
  `part_numbers`. An upload reservation is never polled or cancelled as a job.
- Manifest entries use `entries` / `name` / `artifact`. MD publication is read
  from `operation.result_available`; progress uses `scientific-ai/progress/v1`
  with generic scientific units and rate units, not device placement.
- Authenticated API catalogs use `data`. The independently maintained public
  website projection uses `models`; the portable bundle checker explicitly
  consumes that website projection, not alternate versions of one API.

## Removed behavior

The workbench no longer falls back from unavailable operation history to local
cached runs, reads old `runs.json` projections, translates public workflow-v1
steps, accepts obsolete manual workflow arguments, falls back from the bounded
preview endpoint to the file-download endpoint, interprets old MD-progress fields,
or converts retired chat attachment receipts. Tutorial agents no longer append
the obsolete gateway manual. Recording helpers expose only their documented
`--operation-wait-seconds` option; the lower-level clients keep their own current
`--wait-seconds` option. Artifact uploads are not presented as cancellable jobs.

Current `receipt.json` readers require their immutable journal. An archived
unjournaled receipt raises an explicit local error without modifying its bytes or
submitting new work. Review those records offline. Existing frozen study workers
and raw chat/study/result records are not rewritten by this cleanup.

The batch helper retains a journaled `admission.json` tying the actual server
response to the exact request hash, caller/endpoint/input identity, model, tool,
operation and idempotency key. This allows recovery if the acknowledgement was
saved but the main receipt update failed. It reads the current top-level
`model_id` / `operation_id` and nested `operation.operation_id`, not fields the
server never echoes. A raw or unmatched saved response remains ambiguous: no
upload or admission is retried automatically. Preserve it for operator review.

`tests/fixtures/current-batch-contracts.json` contains the published GROMACS and
Protenix schemas generated from the current backend's `gateway.Submit` MCP
metadata and staged `compiler.request_schema`. The contract tests compare those
fixtures with backend sources when installed, and exercise both real envelope
shapes, parameter rejection before upload, native status, lost ACK recovery,
and owner/model/request mismatches. These are offline contract tests, not live
scientific model or release qualification.

The unique native-schema selector, standard MCP structured/text transport,
OpenAI-compatible model protocol, byte-integrity checks, bounded transient-read
retries, customer seed customization merge, and legitimate self-service ephemeral
mode remain current features. They are not previous-version adapters.

## Release packaging and rollout gates

`Dockerfile.native-identities` includes all changed helpers, the scVI client
source pins, portable skills **2026.10.17.2**, seeded instructions, current
scientific-demos API router, and a rebuilt UI. The ordinary full Dockerfile
already copies these maintained sources for future instances.

1. Build the exact source and qualify it against the matching current-only
   Scientific AI API. Check catalog, upload/finalize, named submission, status,
   cancellation and verified result retrieval with the internal QA identity.
2. Install the current `/api/scientific-demos/workspace/preview` route **with**
   its UI. The five retained API processes previously lacked this route and
   depended on a removed 404 fallback. Static assets alone are not sufficient.
3. Inventory active frozen study workers before deleting old platform tool
   aliases. Drain existing work without terminating or replaying it. Do not edit
   its frozen source/identity or use customer keys for internal verification.
4. Preserve each retained client's MongoDB/state, bucket, accounts and URL;
   refresh MCP catalogs and merge managed seeds without replacing customer edits.
5. Verify precheck offer, inline report, repair/preparation, simulation,
   scientific progress and inline results through the actual current UI. Also
   verify scVI uploads/recovery and the current native/speech response families.

Read-only provider inspection on 17 October confirmed all five endpoints RUNNING
with `SCIENTIFIC_REQUIRE_PERSISTENT_STATE=true` and configured read-write
`/workspace` and `/data` mounts (configuration inspection, not a filesystem probe):

- Rene: `aiendpoint-e00bzsemg1p6mnbdd9`
- System QA: `aiendpoint-e00sd4pe94arytafzn`
- Arseny: `aiendpoint-e00fhhyv1acnq3g5qw`
- LynxKite: `aiendpoint-e00zmda76gegjpekqd`
- Whitelab: `aiendpoint-e00swgae81t2wfr9t5`

## Source verification

- Post-integration correction: **246 passed, 1 skipped** in 10.84s. The new
  current-batch contract suite compares both captured schemas with installed
  backend sources, checks every current MD/scVI/MPI/staged schema's selected
  shape, and exercises submission/status plus retained ACK versus genuinely
  lost-ACK recovery for GROMACS and Protenix. Current native `timed_out` and
  `export_failed` are terminal failures, not indefinite polling states. The
  skipped test requires retained03 files from the installed qualification gate.
- Current-contract Python regression set: **375 passed, 2 skipped** in 40.19s.
  Covers typed submission/source preflight, native selection, artifact streaming,
  lost-finalize recovery, status reads, result integrity, durable study admission,
  cancellation, receipt publication, and preparation/precheck helper contracts.
- Portable skills: 26 tests passed; five edited skill entrypoints validated;
  88-file bundle lock verified.
- Current JS service/history/progress/preview/upload/seed tests: 73 passed inside
  the existing qualified image, with no network. Installed LibreChat skill-loader
  check passed (85 total installed skills, 88 verified portable files).
- React report and saved-study previews: 16 tests passed inside that image using
  the edited components and current progress projection.
- Full Python collection in the backend venv is not a complete scientific
  runtime: 14 collection errors for absent analysis dependencies/fixtures
  (including anndata, matplotlib and h5py). Do not count that attempt as a pass.
- No live model inference, customer data mutation, client restart, image push or
  deployment was performed by this cleanup worker. Exact-release qualification
  remains the parent task's acceptance gate.
