# Small public MD preview, after replacement only

The release-owner-approved publisher completed: **82 files / 32,244,862 bytes**
were uploaded and fully hash-verified without overwrite, deletion or quota
change. Actual browser downloads of all five MP4s and four analysis PNGs also
matched. The new endpoint is running and the old one is stopped/retained.
The [real-agent acceptance gate remains blocked](MD_REPLACEMENT_RESULT_20260923.md)
by the unchanged provider's selected-model 404; publication is not a chat or
inline-viewer readiness verdict.

Frozen source: `/home/tux/fs2-alanine-comparison-20260923/preview-01`.
It contains 82 regular files / 32,244,862 bytes, including all five videos,
`PLATFORM-DELIVERY.md`, reports, plots, scripts and inputs. The source's canonical
inventory SHA256 is
`c55bf30d07aba024ccb538fcb96e1883819c6e5339a2ef48419401f5c0fc7b72`.
Full raw trajectories remain in the qualification bucket and local delivery
bundle; they are not copied into Rene's nearly full 5 GB workspace.

`scripts/qualification/workspace_preview.py` has a fixed destination prefix:
`/workspace/demo-assets/four-engine-alanine-20260923`. It validates the frozen
inventory and <=100,000,000-byte limit, refuses symlinks, checks the actual new
endpoint's immutable image and unchanged account/key/bucket selectors, and
compares `/v1/storage` with the actual workspace mount. Immediately before any
upload it reads provider quota/usage, including noncurrent versions and inflight
multipart parts. It never changes a quota, endpoint or bucket configuration.

Every destination is read and hash-checked before the first write. Different
existing bytes abort publication. Missing files use the already-installed
exclusive-create workspace API; raced HTTP 409 is accepted only after identical
full-byte readback. Re-running verifies completed identical files without
overwriting them. All POSTs are explicit new preview file publication, not
simulation requests. No blind mutation retries or existing-data deletion occur.

Eleven tests cover dry-run behavior, fresh headroom, quota mismatch, pre-existing
conflicts, exclusive-create races, resumed identical content, source size/links,
and replacement image/account/bucket binding. Actual publication/downloads
passed. Inline browser playback remains unqualified because the real agent
failed before any media-viewer call.

## Prepared commands

Use the original refreshed predecessor archive `client-preflight-account-09`,
attachment archive `client-preflight-assets-05`, and approved dry-run
`client-replacement-dryrun-08`. At 19:33 UTC the current endpoint spec matched the
backup, only it was non-stopped on the same bucket, all five attachment hashes
were unchanged, and the account had 12 chats/44 messages, 306 runs, eight full
agent records and no active study. Proof:
`/home/tux/secure-handoff/fs2-md-engines-20260923/client-ready-to-switch-02.json`.

After the explicit go, replacement and account restore, set `MD_NEW_ENDPOINT`
to the actual new ID from the creation receipt; do not substitute the old ID.
Use the restored browser session to avoid another password login:

The following is the original prepared form. A refresh cookie can be rotated
by another consumer (for example the browser). A stale cookie must not trigger
file-write retries: preserve the failed receipt and use a fresh normal login by
omitting `--session-state`. That was the successful live publication path.

```bash
MD_PRIVATE=/home/tux/secure-handoff/fs2-md-engines-20260923
MD_SDK_PY=/home/tux/worktrees/fs2-gromacs-20260923/k8s-inference/components/control-plane/.venv/bin/python
"$MD_SDK_PY" templates/hcls-librechat/scripts/qualification/workspace_preview.py \
  --backup "$MD_PRIVATE/client-preflight-account-09" \
  --endpoint "$MD_NEW_ENDPOINT" \
  --image cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d \
  --preview /home/tux/fs2-alanine-comparison-20260923/preview-01 \
  --manifest-sha256 c55bf30d07aba024ccb538fcb96e1883819c6e5339a2ef48419401f5c0fc7b72 \
  --output "$MD_PRIVATE/client-preview-plan-01.json" \
  --session-state "$MD_PRIVATE/client-replacement-restore-01/browser-state-private.json" \
  --browser-user-agent "$MD_UA"
```

The default command is a read-only plan. For the authorized publication, run
with `--publish` and a **new** `--output` path. All fresh binding/headroom checks
run again. The receipt records exact files, hashes, usage and verified uploads.
The workbench link is `/demos?tab=workspace&path=demo-assets%2Ffour-engine-alanine-20260923`.
No exact-image rebuild is needed for this operator-side qualification helper.

The LibreChat and Serverless skills informed use of the existing authenticated
workspace API and preserved endpoint bindings. The publication receipt is
`client-preview-publication-01.json` under the private MD evidence root, SHA256
`1ade9fbe1f1617abedfce6eabbdec9e395c78954263d5979f48090e177579c95`.
Post-publication provider headroom was 188,401,000 bytes under the unchanged
5,000,000,000-byte quota. Release qualification remains scoped to the evidence
actually collected; the preview is not the complete raw-regeneration bundle.
