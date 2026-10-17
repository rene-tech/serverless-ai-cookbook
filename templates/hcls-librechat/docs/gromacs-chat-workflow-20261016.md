# GROMACS chat workflow: precheck, repair, measured run and inline results

## Customer contract

A new simulation still offers the optional precheck and waits for the answer.
An explicit request to precheck already supplies that consent. The installed
runner binds the check to the exact input bytes, selected files and requested
duration; historical `reused:false` is not evidence of a fresh check today.
The original HTML report renders inside the authenticated chat with downloads.

Repairs require available source files and unambiguous scientific intent. The
agent preserves originals, applies only the justified correction, validates
with installed CPU GROMACS and rechecks the changed input. It does not change
force-field settings, cutoffs, temperature or output frequency merely to make
advisories disappear. Static flags are not proof that a simulation will crash.
English requests remain English unless the user requests a language change.

For simulation plus results, the client uses the existing saved-study executor:
`batch` -> the installed timing/coordinate reporter through `python-script`.
For one already specified new TPR run, `prepare_gromacs_study.py` composes this
plan deterministically, using the existing archive helper, verified publisher
and immutable draft composer. It checks the encoded duration, preserves all
scientific parameters and leaves checkpoint/device flags to the native runtime.
It does not submit inference; the agent invokes the existing workflow tool once
with its returned arguments. This avoids repeated schema discovery, guessed CLI
flags and hand-written result phases consuming the conversation's tool budget.
Advanced protocols and checkpoint continuation retain their existing workflows.
The latter writes verified native timing reports and, when requested, a final
coordinate preview. It uses the compatible Python phase already understood by
retained study workers; existing frozen plans keep their original implementation.
The script's exact bytes are frozen by the existing executor. No new scheduler,
agent loop or scientific model is introduced. Existing worker implementations
and frozen studies are not replaced to add the renderer.

The admission message contains a read-only live study card. It observes the same
study, shows measured scientific work and ns/day, and displays verified final
timing and structure artifacts automatically. Mechanical waiting does not need
a "continue" prompt or another LLM request. Admission is not completion;
unknown rates are not zero, and failed work is not shown as successful.
GPU type/count, placement and image details are not part of this status card.

Final-coordinate previews reuse the installed 3Dmol viewer, with GROMACS editconf
as a coordinate-format conversion only. They are interactive structures, **not
trajectory animations or evidence of equilibration**. The exact final coordinate
is resolved from the successful native command and verified file manifest.
Large previews explicitly select protein atoms; unmodified full native outputs
remain available. HTML is bounded and rendered in the existing opaque sandbox.

## Defects corrected

- Native operation summaries use `operation_id`, while older client code assumed
  nested `id`. The service now accepts either exact identity and rejects conflicts,
  preserving outer scientific progress and model fields.
- GROMACS uses `-noappend`. The skill no longer asks for nonexistent unsuffixed
  trajectory/energy/log files. Final coordinates and checkpoints retain their
  actual names; explicitly joined trajectories use `trjcat` and a separate name.
  The client also rejects these impossible output promises before study admission,
  without silently removing a promised artifact or changing scientific settings.
- Precheck uploads and MD uploads can contain identical gzip bytes with different
  transport descriptions. Private scientific-ai2 fixes artifact identity to include
  those immutable metadata fields; old artifact IDs remain usable. This is a
  platform fix, not a relaxation of upload checksum or ownership validation.
- The default image explicitly installs the workflow schema matching the bundled
  skills, including `native-files.json` as a batch output. Retained clients
  refresh the idle execution MCP connection so the composer sees it.
- No-restart static deployments must bridge the entry point in the HTML actually
  served by the running API, not merely the previous on-disk `index.html`.
  Otherwise a cached older bundle hides the new live progress/results card.
- Skills name the installed bundler and exact execution-status identifier,
  avoid POSIX permission operations on Object Storage mounts, and preserve
  scientific settings when repairing an unambiguous file inconsistency.
- Native reports are rendered in private analysis scratch before the existing
  study publisher issues workspace links. The standalone workspace writer must
  not try to issue a download URL for `/tmp` output. The exact saved Python phase
  is tested with actual completed native results, not only a direct helper call.
- The existing media tool now accepts bounded local HTML reports by returning
  exact authenticated workspace links. It does not send report scripts through
  model context or open arbitrary URLs; the existing isolated inline renderer
  displays them. Image/audio/video behavior remains unchanged.

## Release and evidence

Runtime source: `a9fc982bcfd2db82ec55b32e912b6da82428d3e3`.
Published default image: `lc:gromacs-workflow-20261016-r8` in the configured shared registry,
digest `sha256:36de5582315302a8f203cbf6ea1bdd28fecb65667063f30117378da5912236d8`.
Skills version: `2026.10.16.11`. Build: `Dockerfile.gromacs-workflow`.

Final targeted checks: 66 Python tests for composition, source packaging,
pre-admission validation, HTML/media handling and agent instructions; another 72
for native reports/previews, exact workflow discovery, immutable drafts and text
transport; 27 operation/service tests; 23 admission
tests; 16 preview UI tests; nine installed precheck-runner tests; actual installed
loader verifies 85 skills and all 88 hashed resources.
The real installed composer also validates an actual completed native TPR,
preserves the same draft on replay, and passes the backend's request schema and
native normalization. Its two incorrect development parameter drafts were caught
before inference; they were not promoted. HTML handling passed actual installed
MCP calls on both original and repaired precheck reports.
An actual installed MCP replay of the completed study returned the same completed
ID with `reused_existing_study: true` and `new_study_admitted: false`.

Live qualification is recorded in the task card and private evidence directory
`/home/tux/secure-handoff/gromacs-chat-e2e-20261016.lnPajd`.
Final chat cohorts `2e0a03c2…` and `91f57305…` use the composer and completed
both saved phases without operator recovery. Studies
`d17a3e9b-2426-5c3f-8983-ca771cf924c5` and
`3ec707e9-1f6c-567e-9d8d-6e7197875baa` each published eight nonempty, hash-verified
artifacts. Native rates: **1334.778** and **1330.602 ns/day**, respectively;
both reached and durably checkpointed 1 ns (500,000 steps). Exact repairs changed
only `ref-t = 300 300` to `ref-t = 300`; all other original protocol settings
and source files were preserved. Three checker advisories remain explicitly
explained, not falsely reported as a fully clean scientific validation.
The explicit-precheck chat rendered its report inline, followed by automatic
live status, measured timing and final interactive structure. The reuse variant
recovered draft/path mistakes before admission and reached the same complete
result; those attempts are retained rather than hidden. No operator continue
message or manual result recovery was required. Actual API identity was
`system/qa`, role `user`, with authorized GROMACS/mdprecheck access.
Earlier complete agent runs `00e43dff…` and `c6d7258f…` produced 1 ns trajectories,
verified native reports and inline structures at 1341.538 and 1324.647 ns/day.
The input is an 18,916-atom public 1UBQ example with a deliberately inconsistent
thermostat cardinality. These rates are not performance predictions for a
different system. Original files and non-repair scientific settings are retained.

Failed earlier cohorts remain in the private record: stale schema/assets,
scratch-path reporting, impossible output filenames and tool-budget exhaustion.
Operator-recovered reports are not counted as full-chat acceptance. Final-agent
path retries and their automatic recovery remain visible; no limits/model were
raised or changed. Qualification concerns this requested repair/run/report path,
not every GROMACS protocol, model, tenant, fresh-node or capacity configuration.

The original membrane demo has a compiled TPR but lacks its original coordinates,
topology/includes and MDP. Duration edits are possible; reconstructing its flagged
geometry safely is not established. The public-protein QA repair is not a claim
that those unrelated membrane findings were fixed.

## Deployment and rollback

**17 October update:** the old SPA-entry bridge mechanism below is superseded by
[current asset delivery](client-assets-20261017.md). The API now references the
current immutable bundle directly on an ordinary reload; do not patch a
cacheable hashed entry again. The following paragraphs retain the original r8
rollout evidence.

Patch only the exact affected files, seeded instructions and deployment-skill
registry in the intended instance. Preserve customer-edited instructions.
Reload the demo-service exports in existing API/MCP processes; do not restart
the API, supervisor or study worker. New static entry points require the existing
reversible SPA entry bridge and one browser hard refresh. Preserve old hashed
assets for open tabs. New installs use the published shared default only after
qualification, not a mutable unverified tag.

Retain previous file bytes and seeded instructions under the instance's
`/data/workbench-hotfixes/` and record exact process identities before/after.
Rollback restores those files and refreshes the same registries; it never deletes
messages, buckets, receipts, studies or customer operations. The prior default is
`lc:workspace-links-20261016-r2` at digest `ac7e91de...` with the documented defects.

Rene's retained endpoint `aiendpoint-e00bzsemg1p6mnbdd9` was patched in place on
16 October. API, supervisor and study-worker identities/start times were unchanged.
Both idle MCP connections were refreshed; maintenance inspectors were closed.
His existing study `c93fa6ae…` completed without a restart or QA resubmission.
The refreshed authenticated browser loaded the new entry bundle and rendered
the previously linked precheck report. Existing chat history was not rewritten.
Rollback receipts: `rene-instructions-s61e_38k` under the private evidence root,
and `/home/tux/secure-handoff/scientific-progress-20261016.QBSv1C/rene-static-6e0lgfxq`.
The staged static files were verified byte-identical to the published r8 image;
no customer credentials, buckets, routes, model limits or reasoning limits changed.
