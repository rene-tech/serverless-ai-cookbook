# Guided scientific Apps

MONAI, Holoscan and Isaac forms discover the caller's current MCP submission
schema. They preserve explicit parameters (including null), retain advanced
fields and use the existing dedicated-user study supervisor and batch client.
Opening a form, checking inputs or inspecting an artifact never submits compute.

Preflight records source SHA256, exact parameters and contract hash. Submission
uses a saved request ID and immutable study identity. Reconnect reads that
request; Resume saved request replays only that identity after an interrupted
admission. Changed source/contract or a different owner key is rejected. The
existing Runs page remains authoritative for admission, measured progress,
failures, cancellation and retrieval. Existing API/MCP clients remain supported.

Forms support the published single entry and entries-list policies. Policies
requiring source selectors or multiple required artifacts fail with guidance to
use the live chat/file client. They never substitute a demo workload or infer
scientific defaults. Header/archive preflight is not runtime qualification.

## Artifacts and viewers

Results retain their original API fields and add a readable scientific summary
when a verified JSON result is published. Manifest-listed originals up to 32 MiB
can be retrieved with size/SHA256 verification; larger outputs remain available
through saved workflows and the batch file client. Retrieval failure does not
change operation status. JSON is expanded only on demand.

Workspace previews load only after an explicit click:

- MONAI: original voxel-plane CT slices, HU window/level and binary spleen-mask
  opacity. Shape, affine and units must agree for overlay. No resampling occurs.
  Limits: 32 million voxels, 2048 per axis, 4 MiB PNG. This is research inspection,
  without clinical validation or an assumption that an arbitrary NIfTI contains HU.
- Holoscan: optional annotated MP4 up to 32 MiB, using native browser playback.
  Annotations are already encoded; playback time is not an exact source-frame
  index. Missing annotation is a valid result. The browser never loads masks.npy.
- Isaac: an explicitly selected extracted HDF5 recording, with episode/camera
  selection, one sample at a time, recorded actions/joints and task outcome.
  Cameras and vector widths come from the recording. External/soft links,
  virtual datasets and oversized chunks are refused. TAR/USD remain downloads.
  RGB recordings do not provide a portable 3D scene or validate physics.

Closing a preview releases video URLs and discards late responses. No viewer
allocates a GPU. A true 3D scene requires a provenance-linked portable geometry
export; interactive Holoscan masks require bounded frame data and exact source
mapping. Both remain separate qualification gates rather than fabricated views.

## Inspection and validation, 28 October 2026

Safari inspection of the supplied authenticated deployment found a successful
MONAI result and mask, and an Isaac/Holoscan study rejected before upload because
the batch client did not recognize the deployed entries-list artifact policy.
The saved Isaac contract was `isaac-healthcare-candidate-r11`: simulate with
scenarios JSON and scissor_pick_and_place. It did not establish availability of
the newer generic project contract. No Holoscan/Isaac outputs were retained by
that study. Fresh caller schemas for all three Apps and the running image digest
remain deployment qualification checks; retained contracts are dated evidence.

The downloaded MONAI mask was 51,920 bytes, shape 512 × 512 × 38, SHA256
`e1f86be72bdabd0a90560f3048f7a2319e0d4cdfca07cd0f859f4c7a3b9de9ae`.
Its 512 × 512 slice encoded as 782 bytes. Local Python slice access took 9.65 ms;
Safari 27 local fetch/decode/animation-frame observation over 30 reads measured
16 ms median, 35 ms p95 and 134 ms maximum. This is a small mask probe, excluding
CT processing and deployed network latency, not full viewer qualification.
Whole-volume browser decoding was rejected: even a 512 × 512 × 33 float32 CT
plus uint8 mask needs 41.25 MiB; the recorded Holoscan mask shape needs 117 MiB.

Tests cover invalid-input rejection without submission, changed input/contracts,
owner/key isolation, lost acknowledgement, interruption between binding and
receipt, same-identity resume, geometry mismatch, HDF5 external-link refusal,
manifest integrity, zero/false scientific values, lazy preview and cleanup.
Run Python tests with the pinned scientific-client dependencies, and `npm test`
in `theme-tests`; `TEST_BROWSER=webkit node --test scientific-app.test.mjs`
adds WebKit coverage. No live inference, merge or deployment was performed.
The local Docker daemon was unavailable, so a complete release-image build and
live end-to-end/performance qualification remain required before deployment.

Local validation: 142 Python tests passed, with three retained/private-fixture
checks skipped; 39 targeted Node tests and 16 UI/theme tests passed, plus four
WebKit flow tests. A broad demos-suite attempt was not green on this macOS
checkout (missing optional MCP packages, Linux `/proc` assumptions and older
study-test fixtures); it is not reported as full-suite validation.
