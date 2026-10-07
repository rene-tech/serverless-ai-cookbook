# Large-data single-cell workspace release — 7 October 2026

R5 is qualified for the specific client workflow below. Final shared-backend
concurrency acceptance and customer handover are tracked in the backend fork's
`k8s-inference/acceptance/whitelab-handover-20261007/README.md`. This is not an
all-App scientific-validity claim or a claim that the customer's login is ready.

## Immutable release

- Fork/source: `rene-tech/serverless-ai-cookbook`,
  `83c3ce9250526eb579c54f75adb1ed16d9238c2e`.
- Image tag: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:single-cell-20261007-r5`.
- OCI index: `sha256:92b18aa638f222d1b5b53c61e3c4cad9e11e5e5abc032e856a6a8d69388086fc`.
- amd64 manifest: `sha256:4e937c4178c02413d8554722e596faa443f224e17fa03ec81e161603063381f7`.
- Skills: `2026.10.07.4` (36 skills / 78 checksum-verified files).
- Canonical single-cell client: backend fork commit
  `b2aa0c2b24e3c3e9d258f9980468d4d1945a38ea`.
- Preserves the October 7 Nebius-branded persistent-state base image. Other
  customers' running endpoints were not replaced during this qualification.

## Changes

Build from the repository root using `Dockerfile.single-cell` and the pinned
branding base in that file. Keep the final overlay at one layer; the retained
base has a long layer history. R5's recorded build used the complete source
archive. The Dockerfile-specific ignore list also includes the runtime verifier
for ordinary directory-context builds, with a regression test for that path.
Do not stack another overlay on R5 or silently substitute a newer base image.

The directory-context build completed all build stages and real H5AD runtime
checks. Loading its export into the operator host's legacy Docker image store
failed with `max depth exceeded`; that failure is retained, not called a passed
local-container test. Use the registry/OCI build path for this inherited image.
The exact R5 image was separately pulled, created and fully exercised on the
target Serverless runtime. Consolidating the long base-image layer history is
future image-maintenance work, not a reason to replace the qualified customer
image with an untested rebuild.

The large-file helper uses the published durable batch schema, not the small
native demo interface. It keeps the input, request, idempotency key, operation ID
and collection receipts in the mounted study. A pending exit (75) requires
explicit collection later; it does not promise an unattended local download.

Recovery keeps a separate log per attempt: S3-mounted files cannot safely be
reopened with append semantics. No scratch-directory workaround is required.
The pinned transport retries transient 502/503/504/disconnects only for safe reads
and explicitly idempotent calls. It waits for explicit non-admission capacity
responses with the same request/key, without resubmitting an accepted operation.

The isolated scientific-client Python environment pins SciPy 1.16.3 with AnnData
0.12.3. Actual dense, CSR and CSC backed H5AD reads pass at build and runtime;
the earlier SciPy 1.17.1 combination failed sparse slicing. This does not alter
the separate scientific preparation environments. All 33 wrapper/receipt tests
and 29 canonical client/transport tests pass; `pip check` passes.

## Actual hosted acceptance, not a mock agent

The normal managed agent (`moonshotai/Kimi-K3`, Token Factory) used the public
LibreChat chat API, current skill, typed MCP schema and environment tools. Tests
used only existing `system/qa` identity and public HLCA data, not a customer key.

1. Existing QA login, conversations and study receipts survived replacement on
   the same dedicated state filesystem; the same bucket was remounted.
2. A real Tavily query returned the official scANVI documentation.
3. The agent recovered operation `9aa9398c-59fe-4884-8fc9-f597dbf651f1` directly
   in the mounted study: 584,944 cells; 18 files / 424,932,923 bytes verified;
   no new model job and no move to scratch.
4. In conversation `dac68c3d-792d-5d0c-ba10-7f5b63ea4989`, the agent submitted
   fresh scVI operation `d291df6a-d8a5-48ab-9227-73aa82c4d80a` through MCP,
   preserving all 584,944 cells and 2,000 previously selected raw-count genes.
   Parameters: `X`, batch `dataset`, `gene_selection=all`, seed 44, 20 epochs,
   batch size 512, routine profile, no UMAP. Accepted 08:52:22.434947 UTC;
   completed 08:57:11.808454 UTC, **289.37 seconds** including platform overhead.
5. A later turn collected that exact operation. All 18 files / 425,195,793 bytes
   passed hash and full-cell output validation. The integrated H5AD, embeddings,
   reusable reference and validation receipt were delivered as workspace links.
   Independent authenticated HTTP readback checked every byte of those links,
   including the 318.6 MB H5AD and 79.1 MB CSV. No replacement operation.
6. Actual reference reuse: operation `24467cb6-2001-453e-a7ab-1a2d61252e81`
   mapped an explicitly selected 4,096-cell / 2,000-gene query against that
   reference, ten query epochs, seed 45. First admitted operation succeeded in
   37.72 seconds (13.57 seconds worker execution); all 18 files / 22,058,276 bytes
   and every embedding validated. The query overlaps the reference: no held-out
   accuracy claim. Local preparation required two recoveries (AnnData nullable
   string write opt-in and local HDF5 staging before S3 copy). This was not a
   zero-error preprocessing flow; preserve that evidence and stage new HDF5
   files locally, close/validate, then publish and verify the complete copy.

Raw evidence and private endpoint bindings are retained at
`/home/tux/secure-handoff/fs2-whitelab-final-20261007/`; never publish that directory.
The earlier R3 recovery conversation misstated the receipt's path in prose;
the helper and the final R5 collection use `<study>/output-validation.json`.

## Scope and user expectations

These are engineering, preservation and artifact-integrity checks. Twenty epochs
do not establish biological convergence or annotation accuracy. scANVI training,
reference mapping, interrupted-worker recovery and large upload evidence belong
to the backend qualification; they are not inferred from a scVI-only chat.
Training recovery uses full Lightning checkpoints, not GPU-process snapshots.

The browser workspace upload control is limited to 512 MiB. Larger datasets
should be uploaded directly to the tenant's S3 bucket, then referenced under
`/workspace`; the durable batch artifact limit is separately 25 GiB, subject to
expanded-memory preflight. API keys are not chat attachments. Saved operations
outlive a chat turn; collect their recorded ID instead of submitting replacements.

The default-image pointer is promoted only after the linked final acceptance.
Existing customer endpoints remain deliberate, state-preserving managed upgrades.
