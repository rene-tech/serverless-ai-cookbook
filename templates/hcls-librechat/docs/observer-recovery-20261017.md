# Known-job observation recovery — 17 October 2026

The workbench must distinguish a disconnected observer from failed science.
An earlier admitted GROMACS job kept running after its client observer raised a
wrapped exception. The saved study became `needs_attention` and the oldest-first
queue then prevented later work from reaching the platform.

## Behavior

- Recognize nested MCP/HTTP and AnyIO stream-closure failures, including session
  teardown. Retain structured error types/codes without credential or payload
  logging. An unavailable observation is not a successful result.
- Reconnect a saved native/batch operation with its existing operation ID,
  ownership, input files and request identity. Recovery is explicitly read-only:
  it cannot upload, submit or cancel a replacement scientific execution.
- Back off repeated observation outages, up to one recovery read per minute.
  This is status polling, not a simulation restart budget. Permanent errors
  remain visible for inspection; invalid inputs, changed ownership, failed
  artifact checks and cancellation do not become retries.
- Give saved studies fair observation turns. An already admitted remote job
  does not monopolize the workbench queue while another request waits. Native
  Serverless remains the sole concurrency/admission/execution authority.
  Unresolved admission or cancellation still requires reconciliation.
- Keep scientific plans, checkpoints, results and the analysis executor
  `scientific_study.py` unchanged. Existing deterministic analyses pin those
  bytes; the patch only changes the worker and transport helpers.

## Release and qualification

Runtime source: `138bfaec44ba7932e424827b9c6ed4337c435aa5`.
Image: `lc:observer-recovery-20261017-r2`, digest
`sha256:8b7a4b6655276bb730b350d53a6b44e827506287ffe45d544381c4d43f6e1386`.
The parent is the current catalog/inline-viewer release
`sha256:17d77ad5676d98f719f42f26c1b57188bdd647643e087ff5715e06dfdbf1d00d`.

Focused tests cover real MCP SDK transports, nested disconnects, saved-study
recovery, cancellation, terminal failures, no duplicate admission, queue
fairness, owner/input/artifact protection, private retry state, native tool
selectors and process death between child and parent acknowledgements.

The two System-QA GPU studies each completed 0.6 ns, collected verified native
outputs, and published all eight requested workflow artifacts. The isolated
observer fault recovered the original operation; the second request was admitted
before the first finished. Two authenticated default-agent chats read their
progress/results without errors, and the final chat invoked the structure viewer
for both results. Browser rendering itself was not requalified by this change.
All five retained clients passed exact payload, healthy worker/API and unchanged
catalog checks. Only their idle observer workers were restarted; no API, state
supervisor, scientific runtime or active analysis was restarted.

Live evidence and exact rollout scope are recorded in
[the release receipt](evidence/observer-recovery-20261017.json). Testing uses
System QA, not a customer key. This is not a new all-model capacity or scientific
quality qualification. Private incident inputs and client inventories are not
part of this public portable client release.
