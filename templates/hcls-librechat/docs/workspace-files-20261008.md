# Shared Workspace file UI — 8 October 2026

## Cause and scope

WhiteLab reported `.cif` rejection in ordinary chat uploads and no files in the
native attachment library after a successful S3 upload. The mounted files were
present; this was a client integration failure, not missing customer data.

The speech branch had already implemented arbitrary-file upload and audio
history in commit `2750c8f8b7a2c3602a5523f49926e10a6957f2c6`. That branch was
not merged into `rene-tech/serverless-ai-cookbook/main`; the deployed
`catalog-20261007-r2` image did not contain the bridge. This release reuses that
implementation, without importing unrelated speech runtimes or MD changes.

General uploads and drag/drop now use the authenticated bucket-backed
`/api/scientific-demos/workspace` route with no MIME/extension allowlist. Client
and server verify uploaded size and SHA-256. Hashing uses bounded chunks rather
than a second whole-file buffer. Unknown types, extensionless, empty and Unicode
files are covered. Browser limits remain 512 MiB per file and ten attachments
per message, not ten over the lifetime of a conversation.

Paperclip **Choose from Workspace**, the **Attach Files** sidebar and **My
Files** use one picker. It lists mounted S3 data, supports folder navigation,
refresh and pagination, and attaches existing files by reference without
reupload. Earlier native attachments remain accessible. Existing bucket paths
are mutable references, not immutable artifacts; scientific submission still
uses the platform's normal finalized-artifact helper when required.

File-only Send saves a user message and performs no inference. Downloads and
audio playback are authenticated, preserve bytes, and survive chat reload.
Provider-native image/PDF upload remains a separate, explicitly labeled action.
Accepting any file does not make all downstream Apps accept every input format.

## Exact candidate

- Runtime source: `36b9fa9c2ac64102f22efc01eb6ed635fad3ac71`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:workspace-20261008-r3`.
- Index: `sha256:752a860b307e85e69b8ad3b5983ac158f78ad5121bb8dbf4f5ec6e89a30e0c1b`.
- amd64 manifest: `sha256:453ef5186d93cde0d3b458b30a57c7de6f49012acf4da6e3722f4ace712ef6b3`.
- 127 layers; 3,732,503,603 compressed bytes. Do not add another image layer.
- Retains the catalog-R2 agent configuration, installed skills `2026.10.07.5`,
  OpenFF and the single-cell runtime. Dense/CSR/CSC backed-H5AD checks pass with
  SciPy 1.16.3; no customer model grants, keys or GPU deployments are changed.

Build with `Dockerfile.workspace`. Its `workspace-patch` target exports only
client source/assets, the file route/service, and the installed-feature check.
The canonical `Dockerfile` and `Dockerfile.default-release` include the bridge
too. `uploads/verify-installed.mjs` inspects the actual image's source **and
compiled JavaScript**, including all three file-picker entry points. A label or
a source-only test is insufficient. Run this check before future promotions.

## Qualification procedure

The image build runs 55 upload, speech-compatibility, history, UI-patch compilation
and service tests, then the production Vite build, branding check, installed
feature check, `pip check` and single-cell runtime check. An existing Tailwind
`ease-[…]` ambiguity warning remains; it is not a new upload failure.

Use internal `system/qa`, not a customer inference key. Generate the synthetic
fixtures with `uploads/make-browser-fixtures.py`, authenticate privately with
`uploads/browser-session.py`, and run the real browser via Playwright CLI.
`scripts/qualification/workspace_browser.js` exercises seven formats, six actual
downloads, WAV playback, file-only submission without an inference request and
history reload. Repeat for two unchanged-release cohorts. Verify downloaded
hashes against the fixture manifest, not just successful download events.

Separately exercise the native file chooser, drag/drop, failed-upload recovery,
existing S3 selection in both the sidebar and dialog, and prompt-driven file
access. Capture a screenshot of the bucket picker with Nebius/NVIDIA branding.
Keep raw traces, authentication state and payloads outside Git. This file UI
qualification is not a new all-model/scientific-correctness acceptance claim.

## In-place deployment and rollback

The owner requested patching WhiteLab's running UI rather than replacing its
Serverless endpoint. `scripts/apply-workspace-hotfix.py` validates the qualified
archive digest and path scope, retains previous files and the patch under
`/data/workbench-hotfixes/<release>/`, and atomically replaces individual files.
Old hashed assets remain for open browser tabs. It does not touch environment,
credentials, MongoDB, user files, skills, Python packages or agent instructions.

Check that customer chats are idle first. Retain message hashes and account,
App-grant, bucket and filesystem identities. Apply, run
`node /opt/hcls-librechat/verify-workspace-installed.mjs`, then restart only the
existing Docker application container. The application caches `index.html`, so
an application restart is necessary. Do **not** stop the Serverless endpoint.
Check public login, endpoint/VM/URL identity and retained message hashes afterward.

Rollback restores `before.tar.gz` inside the same container and restarts that
container, retaining the same data. Never restore an old database for a code-only
rollback. The patch survives application/container restart; a **Serverless
stop/start or VM replacement reconstructs its old pinned image**. Use the newly
qualified default image for a later managed replacement, or explicitly reapply
the retained patch. The immutable endpoint image is not falsely reported as
upgraded by this operation.

## Live outcome

WhiteLab was patched at **the existing** endpoint
`aiendpoint-e00axdvs33j7ycdqt1`, VM `computeinstance-e00emwj2pep044hdgp` and URL
<https://port3080-qxnvfnk6ancxhd3.tunnel.applications.eu-north1.nebius.cloud>.
The application container was restarted; the Serverless endpoint was not
stopped, replaced or redeployed. Its cloud specification still truthfully pins
catalog-R2, with the retained R3 runtime-patch receipt documenting the difference.
All three chats / 12 messages retained their compared-field hashes. Account,
16 App grants, agent model, bucket and starter-data manifest are unchanged.
The customer's reported CIF was browsed and selected into the composer, then
removed from the draft: zero customer messages, inference requests or bucket
mutations were submitted. Nebius/NVIDIA branding remains visible.

The patch archive digest is
`sha256:e1ade399b485b361470425b2f84db373c066c4ec70e174a9e75c8ff4db8f5963`.
Its 384 overlapping files, including all required changed UI/file-route surfaces,
match the immutable R3 image's final layer byte-for-byte. The patch includes
2,303 source/assets files; unchanged and older assets are retained, not removed.

Two unchanged R3 browser cohorts passed on internal QA:

| Check | Result |
| --- | --- |
| Seven uploads per cohort, largest 10 MiB | 14 accepted |
| Six downloaded files per cohort | 12 SHA-256 and filename matches |
| WAV history playback, 1-second synthetic recording | Both played |
| Saved history after reload | All attachments retained, no draft duplication |
| File-only inference calls / unexpected HTTP 5xx | 0 / 0 |
| Existing externally S3-uploaded CIF, dialog and sidebar | Visible, selected without reupload |
| Injected HTTP 503 during upload | No message admitted; removal and retry recovered |
| Drag/drop with unknown MIME/extension | Uploaded and saved |
| WhiteLab reported CIF in real client | Selected without customer data mutation |

Cohort conversations: `357c3de8-4559-4d1a-b14e-cd9542c39f57` and
`635abea1-21d7-4898-b5ef-86c30823c07e`. Final browser evidence follows a successful
in-place QA restart. Source deployment/link/history tests also pass: **25 tests**.
Evidence without payloads is in `evidence/workspace-files-20261008.json`; private
traces remain under `/home/tux/secure-handoff/fs2-workspace-files-20261008/`.

The early browser check found the old empty sidebar was still separate from My
Files; R3 fixes both. One transfer validation rejected an incompletely copied
QA patch archive before changing anything; the completed transfer was verified
before retry. Browser-runner native chooser handling required a separate chooser
step; the final cohorts use the actual, already-tested HTML input. The negative
test initially expected Send to be disabled for a failed upload; the actual
contract rejects submission with a visible error. That rejection and recovery
were then verified rather than claiming the original assertion passed.

### Separate unresolved agent check

Two prompt-driven QA checks asking the default agent to inspect the uploaded CIF
stopped at its existing 90-second model response-time budget, before any tool
execution. These are **failed checks**, not successful file-analysis evidence:
conversations `6a50ceb5-4240-4706-9238-10bc802138b1` and
`d83110e8-e598-59c1-94e3-30c4668ee7d9`. The internal QA provider's `/models` returned
200 with Kimi-K3 listed in 194 ms; an isolated, low-reasoning `OK` request returned
200 in 1,365 ms. Thus a provider-wide outage is **not established**. The full
high-reasoning agent request needs separate investigation. No customer provider,
model or reasoning budget was changed to mask this failure.

This release qualifies file storage, selection, history, download and playback;
it does **not** claim that the default agent's full file-analysis workflow passed.
That remaining check is tracked in Task Deck
`fs2-workbench-file-agent-timeout-r20261008`.

The operator release menu includes `workspace-20261008-r3` with its immutable
digest. Its rolling update completed with three ready API replicas, retaining
the backend image and all other configuration. The shared deployment script and
console button select R3; the full-source build recipes enforce the file bridge.
Existing unrelated customer endpoints were not upgraded.
