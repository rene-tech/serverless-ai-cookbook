# Inline report visibility after retained-client patches

## Finding and correction

The reported conversation contained valid owned-workspace HTML links and intact
report files. A fresh browser rendered the report, plots and all four interactive
3D site views. The reporting user confirmed their existing browser displayed
only links, with no inline report.

The running LibreChat API had cached its initial HTML shell. Earlier no-restart
patches replaced that shell's old JavaScript entry with a bridge to the new build,
but the old entry URL still carried a two-day browser cache lifetime. Clients
that had already cached the original JavaScript could retain the renderer with
no inline-report support. A fresh browser alone did not exercise that boundary.

`scientific-client-assets.cjs` now refreshes the operator-built asset references
in HTML responses using the current on-disk release. Normal navigation/reload
requests the actual new content-hashed bundle, never the old mutable bridge.
Language, base URL, per-response CSP nonce, deployment bootstrap, authentication,
API responses and static asset bytes are preserved. Partially copied releases
retain the last complete asset set. No API or study-worker restart is required.

An already open page still needs one ordinary reload to replace its executing
JavaScript. No cache clearing, special query parameter, new chat or new precheck
is required. The saved conversation is not rewritten.

## Exact release

- Runtime source: `45c4d4e7ee6ede82256613877266c8ebfa5c8584`.
- Image: `lc:client-assets-20261017-r1` in the shared registry.
- Digest: `sha256:eda632a87822dd9f87a43fb0de6cc3f6e617fcbeb72d13403f4049ad423ab838`.
- Base: qualified `gromacs-workflow-20261016-r8`, digest `36de5582…6d8`.
- Viewer bundle remains `index.BxXzWA0S.js`; asset-set revision
  `56d4c3a2922008d0`. No scientific runtime, report generator, agent model or
  skill changes are part of this release.

The default release pointer and maintained build recipes include the fix.
Retained QA and reporting-user clients received the identical module, an
idempotent on-disk server patch, and the scoped live middleware installation.
Other customer instances were not modified.

## Qualification and limits

- Seven tests pass in the exact image, including the actual installed Express
  server. Tests cover retained-shell updates without restart, unchanged API/static
  data, partial-release fallback, request-local nonces/base/language, unsupported
  HTML, and idempotent installation preserving existing route objects.
- Two consecutive QA browser reloads rendered an existing verified report while
  the obsolete entry URL was deliberately blocked. Neither requested it.
- The reporting user's exact conversation passed the same normal-reload check.
  The original report rendered inline; all four site-specific 3D canvases and
  their Reset view controls worked. The overview also rendered before the fix;
  its scientific content was not the defect.
- The browser-downloaded HTML was byte-identical to the retained verified
  delivery manifest. No precheck, GPU simulation, customer-key inference,
  new conversation or replacement endpoint was created by this work.
- API, study-worker and supervisor PID/start identities remained unchanged.
  Maintenance inspectors were closed. Existing jobs/history/data remain intact.

The old retained API lacks `/workspace/preview`; the unchanged renderer makes
one bounded authenticated `/workspace/file` fallback after 404. Those observed
404s are retained evidence, not failed report delivery. WebGL screenshot capture
also emits browser-driver ReadPixels performance warnings; no report script or
3D initialization error was observed. This release qualifies asset delivery and
the affected saved-report path, not every scientific workflow or GPU recovery.

Private receipts, screenshots, original report and hashes:
`/home/tux/secure-handoff/precheck-render-20261017.tZb0VM`.
Task: `fs2-precheck-report-rendering-r20261017`.

## Rollback and future patches

Retained-client backups are under each exact instance's
`/data/workbench-hotfixes/{qa,rene}-assets-*`, with private local receipts naming
the exact directories. Restore the previous two helper files and server index,
and remove only the `scientificFreshClientAssets` layer from that API's router.
Leave all other middleware, old hashed assets, messages, reports and jobs alone.
The previous default is the pinned r8 image; do not replace a running customer
instance merely to revert this middleware.

For future static patches, install the new assets before atomically replacing
`index.html`; leave old hashes available to open tabs. Do not rewrite a hashed
entry or rely on a hard-refresh instruction as the release mechanism. Verify
the actually served HTML names the current bundle and that a normal cached
browser reload renders the exact reported artifact.
