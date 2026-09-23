# Rene workbench replacement — blocked chat gate

Status at 20:21 UTC on 23 September 2026: **BLOCKED, not customer-ready**.
The approved replacement and supported account recovery succeeded. The real
scientific-agent prompt failed before its first tool call because Token Factory
returned model-not-found for the unchanged selected `zai-org/GLM-5.3-Flash`.
No model substitution, further inference retry or endpoint restart is authorized
while the release owner awaits the owner's explicit model choice.

Live replacement: [Scientific AI workbench](https://port3080-kgjzjs9jp248jsp.tunnel.applications.eu-north1.nebius.cloud).
Endpoint `aiendpoint-e00mwh65yfkkg4t93n` is RUNNING and `/health` returns 200.
Exact image:
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d`.
Runtime source is `88109af67d11726d1e07e14c5d0ff4e83a4837e0`.
The old endpoint `aiendpoint-e00rxhvqkjfny2zkzy` remains STOPPED and retained.
It must not be deleted before the real chat/inline-viewer gate succeeds.
No other endpoint was changed. No quota, resource, network, key, bucket or
default-model setting changed; final spec comparison differs only in image.

The [sanitized receipt](demos/evidence/20260923-md-replacement/receipt.json)
separates the passed recovery/file checks from the failed live-agent check.
Private raw evidence is under
`/home/tux/secure-handoff/fs2-md-engines-20260923/`.

## Preserved account and data

The final pre-stop check matched `client-preflight-account-09` and
`client-preflight-assets-05`: configuration, all chats/messages, five images,
eight agents and terminal study rows were unchanged; no study was active.
Only live study-engine metadata differed. No unnecessary export replaced these
archives. Stop-first prevented two same-owner bucket-writing instances.

Supported native imports verified 12 conversations, 44 messages and five images.
All 306 prior platform operation IDs and the existing terminal failed study
remain discoverable. Profile, projects, presets, favorites, tool favorites and
active-skill settings matched. A restored historical image loaded in the actual
browser at its native 1000×670 dimensions.

All eight original agents were **managed, view-only shipped definitions**
(six workbench agents plus Clinical Report Draft and Conversation Evaluation).
There were zero user-custom agent definitions. The replacement seeded its
current built definitions; the restore helper did **not** import or overwrite
agent definitions. Independent comparison confirmed their instructions, tools,
provider/model, parameters and other supported configuration fields matched the
archive. This policy does not silently replace user-custom definitions.

Conversation import remaps conversation/message and attachment IDs. It preserves
verified visible text/tool payloads, except native import removes transient
inline-UI handles. This is not a full MongoDB or arbitrary execution-state
restore. The private original archives remain authoritative and retained.

`client-replacement-account-validation-01.json` passed. A later full export,
`client-postbrowser-account-01`, preserves the failed qualification chat as well:
13 conversations / 46 messages, still 306 platform operations and no active
study. No new molecular-dynamics simulation was submitted.

## Preview publication and browser evidence

The frozen `preview-01` inventory
`c55bf30d07aba024ccb538fcb96e1883819c6e5339a2ef48419401f5c0fc7b72`
was published through the existing authenticated workspace API to
`/workspace/demo-assets/four-engine-alanine-20260923`.
All **82 files / 32,244,862 bytes** passed full size/SHA256 readback. Every
destination was checked before writing; no existing data was overwritten or
deleted. No quota was raised. The first read-only plan encountered a stale,
already-rotated refresh cookie and failed before any file write; a fresh normal
login passed the next plan and publication. That failed receipt is retained.

Fresh provider counters after publication: 5,000,000,000 bytes allocated,
4,811,599,000 used, **188,401,000 bytes free**. The 31 MiB preview is deliberately
not the full raw-regeneration bundle. Raw trajectories/restarts remain in the
qualification storage and local delivery bundle, not Rene's nearly full bucket.

Actual browser checks passed desktop header/history, six workflow cards, and
390×844 mobile layout without horizontal overflow. All four Apps appear in the
caller-scoped Apps panel. The authenticated browser's `/api/mcp/tools` response
contains `submit_gromacs_workflow`, `submit_namd_workflow`,
`submit_amber_workflow` and `submit_lammps_workflow`. The earlier exact-image,
ordinary-Rene-key grant/schema inspection is retained separately; discovery is
not an actual GPU submission or capacity reservation.

The browser downloaded all five MP4s and four analysis PNGs from Workspace;
all nine downloaded files matched the frozen source SHA256 and size. This is
**download qualification, not an inline-media playback pass**. An attempted
local `file:` playback probe was blocked by the browser automation boundary;
no bypass was attempted. The real agent never reached its media-viewer calls.
Screenshots/snapshots stay in the ignored/private
`output/playwright/rene-md-final-20260923/` directory rather than being committed
with private historical chat titles.

## Exact external blocker

Initial startup failed at 19:54:22 because a positive authenticated model
catalog omitted the configured Flash ID. A host request then saw 24 IDs while
an exact-image Node request saw 23, differing only by Flash. A later paired
Python/Node × three-User-Agent check returned all 24 IDs in all six calls.
The omission was therefore not established as a Node/UA defect. The one
authorized same-endpoint/image/environment retry became healthy at 20:03 UTC.
No code, image or default-model change was made to conceal the first failure.

The actual browser prompt requested live schemas for the four Apps, CPU-only
CSV calculations using `/opt/md-analysis/bin/python`, and the existing video
and Ramachandran plot. It explicitly prohibited new MD, Docker, package
installation and raw-trajectory downloads. Conversation
`c9589281-3a2e-5e42-8d19-fc430e3f2e4f` failed with structured
`model_not_found` before any tool call. The requested calculation/summary JSON,
usable final answer and inline viewer therefore remain **unqualified**.

The request selected `agent_nebius_scientific_ai`; both persisted agent model
fields and the browser model catalog contained Flash. The provider uses the
fixed environment key and `https://api.tokenfactory.nebius.com/v1`; it does not
consult a per-user key in this configured path. Offline source tracing found
LangChain maps upstream HTTP 404 to `MODEL_NOT_FOUND`; this was not the local
catalog validator. Existing console formatting omitted numeric status, so
bounded direct probes retained actual upstream response evidence.

At 20:16:10–11, a contemporaneous 2×2 using the exact image, same key/URL/peer,
512-token bound and selected Flash ID returned HTTP 404 for **all four**
streaming/nonstreaming × tool/no-tool combinations. The response said the model
does not exist. A same-time GLM-5.3 streaming/tool probe also returned 404. An
earlier nonstream Flash request had returned 200, so this is an observed
upstream availability/catalog inconsistency, not proven streaming causality.

Two diagnostic-only alternative probes returned actual streamed
`ready_check({"value":"READY"})` calls at 20:17:52–53:

| Probe model | HTTP | Provider request ID |
| --- | --- | --- |
| `zai-org/GLM-5.2` | 200 | `061163aaee585ee3ffc7db081a6e8886` |
| `Qwen/Qwen3-30B-A3B-Instruct-2507` | 200 | `be0133f1a0cab64502f6c24f6f6c13dd` |

Neither is deployed as a substitute. These tiny capability probes are not the
full scientific-agent acceptance prompt. The owner must explicitly choose any
change; then the real analysis and inline media gate must run successfully.

The LibreChat and Serverless skills informed stop-first and supported recovery;
Playwright kept real browser evidence separate from APIs, and release
qualification kept the external failure visible. This report does not relabel
the eight separately executed hosted MD workflows or portable CPU regeneration
as a full browser rerun.
