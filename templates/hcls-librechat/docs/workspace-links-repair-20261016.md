# Saved report links, upload recovery and deployed skill refresh

## Incident and causes

The actual user conversation exposed two empty links and no inline report,
despite nonempty, checksum-verified HTML/JSON files. Earlier acceptance exercised
canonical `/demos?tab=workspace...` links only. The model instead wrote
`sandbox:/workspace/...`; react-markdown stripped that unsupported scheme before
the anchor preview component could see it. That gap invalidated the broader
"visualizations fixed" claim. The original conversation was not rewritten.

Two further issues were confirmed:

- LibreChat caches deployment skills in its running process. Replacing `SKILL.md`
  on disk did not update what the actual `skill` tool returned.
- Re-uploading the same 8,996,492-byte input under another receipt targeted the
  same immutable object. The storage service disconnected the conditional PUT
  before httpx exposed a 412 response; the helper repeatedly raised `ReadError`.

## Repair

`WorkspaceMarkdownLinks.ts` normalizes only validated workspace references in
the Markdown tree **before** URL sanitization. Existing canonical links and the
upstream sanitizer remain intact. Unsupported external schemes and traversal
are not granted access. HTML/media previews continue using the authenticated
workspace reader; raw JSON opens the correct selected workspace file.

The upload helper treats ambiguous transport failures as unconfirmed transfers,
then asks the platform to finalize and verify the exact stored size/hash. Missing
or mismatched objects fail. Explicit HTTP errors and cancellation are not turned
into success; conditional writes are never weakened or overwritten.

The precheck helper now accepts `--rerun` when the user explicitly requests a
fresh check. Use a new receipt directory/key once; retrying that identical command
resumes its operation. Default exact-result reuse remains unchanged and must not
be described as a fresh execution.

## Exact release and live patch

- Source: `b27bc4a44672a0219e240e24af1cfdc181ffb6ea`.
- Image: `lc:workspace-links-20261016-r2`, digest
  `sha256:ac7e91debb7b4d666068bbb61567295bcbaac6292f998f79e9a0bdcac7513b4a`.
- Registry prefix: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/`.
- Skills: `2026.10.16.7`; 85 installed skills, 88 verified resources.
- Maintained build: `Dockerfile.workspace-links`. The final build used r1 parent
  digest `344b3c3d29ea8be502262d207d09d996c3eb8658608c8afb442721ed0ff6341d`;
  its original base is qualified preparation release `86025c27…`.

Rene and System QA retain their existing endpoints, identities, storage, original
messages and jobs. Exact affected static/helper/instruction files match the final
image. No API, supervisor or study-worker process was restarted. Other customer
clients were not changed. The shared default selects this digest for new installs.

The SPA shell is cached by the running API. A reversible entry bridge activates
the new hashed assets. Existing browsers need **one hard refresh**; subsequent
ordinary refreshes were tested. Old hashed assets remain for already-open tabs.

Deployment-skill refresh must also update the **in-process registry**, preserving
plugin skills, not merely the filesystem or Mongo agent prompt. This incident's
operator refresh invoked LibreChat's own `initializeDeploymentSkills` in the
existing process, preserved all 85 skills and verified tool-body hashes. Its
temporary container-loopback inspector was closed immediately. There is no new
public debug/reload endpoint. Never restart an API just to refresh skills while
the study supervisor has work; never leave an inspector listener enabled.

## Evidence and limits

- Nine pinned-image renderer tests, including the exact legacy link format,
  unsafe path negatives, original downloads and report/media summaries.
- 34 Python upload/receipt/core-instruction tests; nine installed precheck-runner
  tests; exact installed skill loader/hash verification.
- Natural duplicate-PUT `ReadError` reproduced in system QA, then recovered with
  independent downloaded hash verification. New objects and missing-object
  failure also tested; explicit permission and checksum failures stay failures.
- Explicit CPU precheck rerun delivered a new operation in 80.9 seconds; retry
  resumed that same operation in 4.3 seconds. A separate actual LibreChat agent
  followed the new skill, performed a fresh check and rendered the report.
- Actual reported user conversation: zero empty links, original HTML report
  rendered inline with 31 SVG elements, interactive 3D canvas opened visibly,
  both downloads matched retained source hashes. The original JSON link also
  navigated to the correct workspace file and downloaded identical bytes.
- Hard refresh followed by ordinary refresh preserved rendering. API and worker
  process identities remained unchanged; no customer inference was submitted.

Retained private evidence: `/home/tux/secure-handoff/librechat-errors-20261016.3z16vj/`
and `/home/tux/secure-handoff/upload-recovery-20261016.YUWuKB/`. Public Git contains
no customer report contents, credentials, signed URLs or private screenshots.

Scientific FAIL/WARN findings are deliberately unchanged. The actual user's
report flags input-structure problems; another QA source bundle without file
selectors reported an atom-count mismatch. These are visible checker findings,
not silently converted passes. This repair does not claim scientific validity,
a new completed GROMACS trajectory, or all-platform production readiness.

Legacy live APIs still return 404 for the newer preview route; the tested UI
falls back only on that status to the existing authenticated bounded file read.
Expected headless WebGL performance warnings do not indicate a missing viewer.

## Rollback

Retained per-client static and helper backups are under
`/data/workbench-hotfixes/` with exact paths in the private receipts. Restore only
those files and the owned seeded instructions; reload deployment skills using
the same process-preserving procedure. Keep additive hashed assets and customer
data. Future-install rollback is the prior `86025c27…` release, with this
incident's limitations explicitly reinstated. No rollback deletes or restarts
customer jobs, endpoints, buckets or messages.
