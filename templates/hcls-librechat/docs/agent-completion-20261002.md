# Complete-result candidate, October 2

Scope: the three original Lynx agent requests (CIF inventory, force-field advice,
OpenFF preparation), compound CSV/plot delivery, a real packaged GROMACS protocol,
and interruption/reconnect without duplicate work. Token Factory only. This is
not qualification of arbitrary GPCR production protocols or shared GPU capacity.
The original customer has not supplied a complete production GPCR input bundle.

## Implementation

- Builds on the pinned R10 workbench and the bounded-reasoning implementation
  documented in `bounded-reasoning-20261001.md`. Model invocation deadlines and
  loop limits do not cancel admitted scientific jobs or change customer limits.
- Inspection no longer terminates the graph, including old saved calls with
  `finish_request=true`. Only explicit final verified delivery can end a turn.
- Final delivery can include every requested CSV/plot/output file alongside a
  measured inventory, OpenFF or MD report. Missing files prevent that delivery;
  existence/checksums are not misrepresented as scientific validation.
- The existing Gemmi inspector exports CSV from measured records, including
  optional polymer-only rows. Missing values remain blank, distinct from zero.
  Exports are create-only and read back after closing.
- The shared agent core remains below 10,000 characters. Scientific details
  remain in the installed domain references. No customer-specific prompt fork.
- Replay qualification reuses its login session instead of logging in for every
  prompt and artificially saturating the authentication limiter.
- Real bounded waits on pending/running execution jobs no longer trigger the
  repeated-tool detector. Errors, terminal rereads and zero-wait loops still do;
  the accumulated model-time limit is unchanged. Batch observation emits only
  authoritative state changes and the existing operation ID, not customer data.

## Qualification record

No customer promotion or default-model change has occurred. Product-owner
approval is pending for a possible Kimi K3 default if complete workflows qualify.
The current approved default remains GLM-5.3-Flash.

Private prompts, inputs, sessions and evidence:
`/home/tux/secure-handoff/fs2-agent-completion-20261002/`.
The task-owned local client `fs2-default-release-side-completion-r1` uses loopback
port 3197 and the existing system/qa API identity, with its unchanged two-operation
limit. No tenant, bucket, API key or cloud endpoint was created. Owner: this
side-conversation completion task. Purpose: isolated candidate qualification.
Expiry: October 3, or earlier after results/export. Close only this container
after its admitted work is terminal; preserve evidence. No other worktree or
running client is modified by development.

R1 candidate `sha256:bac7cf568a5b298775c1769acff55dff271d1677155e7e5e7ffe0d773bb16c04`
passed 36 installed-runtime/Node checks, 22 Python contracts and eight Gemmi tests.
Live qualification correctly rejected it: without explicit final delivery, the
model added unsupported structural claims to the CIF inventory. A second cohort
also exposed the replay harness's excessive login calls (HTTP 429). Neither is
counted as a pass. R2 corrects final factual delivery and session reuse.

R2's actual GROMACS operation `56608cc2-67bb-474f-a19d-f1a5c623391c`
succeeded, but exposed a repeat-detector false positive during healthy long
polling. The chat stopped early at 111 seconds. Browser resume delivered the
same completed operation without a new submission. This is retained as failed
unattended acceptance, not counted as a clean cohort; R3 corrects that detector
and adds an installed-graph regression with five identical running observations.
R4 adds concise operation-state progress so waiting is not a silent log.
Its first packaging attempt reached 128 filesystem layers: build succeeded but
Docker refused to start it. R5 uses a two-stage build exporting one changed layer
on the fixed R10 base (123 final layers), never another candidate as its base.
The 121 installed MCP/polling/recovery/artifact tests pass on that image, without
network, GPU, skipped cases or replaced application dependencies. A final
revision-labeled build still needs its live cohorts before any promotion.

R2 technical output checks passed all nine general cases with both the approved
GLM default and Kimi. This does not approve all scientific prose: both still
overgeneralized parts of a separate short-MD interpretation question. Kimi was
faster in these cases but is not automatically promoted. The dated DeepSeek ID
was rejected by this image's curated chat-model list (nine pre-provider errors),
not by its inference endpoint. That is not a model-quality result.

The file-only delivery verifier now permits prose around checked downloads;
parallel viewer + file-link calls intentionally do not trigger the graph's final
report shortcut. Numeric inventories, ligand preparation and MD reports still
require their exact factual cards. Every delivered link is independently fetched
and checked. R2's initial plot failure was this overstrict file-only assertion;
the CSV values, PNG, links and browser plot were present and correct.

Remaining gate: verified original and holdout outputs on the final unchanged
image/configuration, two clean cohorts, browser/files/reconnect, and the exact
customer-policy route. Prior R9/R10 or model-comparison evidence does not qualify
this new image. Preserve both customer accounts, chats, key and mounted bucket
before any later replacement; Serverless stop is destructive to local state.

## Final candidate and observed boundary

Implementation commit: `d97546f10484625e853bfa3aad2b4ca1687f52ad`, on top of
bounded-reasoning commit `5507b9b965cda28444f4560a15f3366a06237e2e`.
The candidate was published without changing the shared release selector or
Lynx's running endpoint:

```text
cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:candidate-bounded-completion-20261002-d97546f
cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:22ef9a7d50d6442cdf9066f295b17480d23d561f88662c970c157183197392d1
```

Remote manifest config matches the tested local image:
`sha256:93411fe7d89f48d03a014d2abff1781b62d054f4eea03d03b96c287e50e3f72a`.
The final image has 123 layers. On this exact image, 38 Node/installed-graph tests,
8 Gemmi tests, and 121 installed MCP/polling/recovery/artifact tests passed, with
no skipped cases. The earlier 47 source-level Python checks are separate evidence.

The approved seeded GLM-5.3-Flash/low agent passed all three original Lynx requests,
eight of nine general output cases, and catalog discovery. **12/14 technical
delivery cases passed; this is not a clean release cohort.** The failures were:

- `data-summary`: two normally stopped provider generations produced reasoning
  but no answer/tool call. The bounded single retry was exhausted. The client
  reported incomplete work in 6.0 seconds; no CSV or plot was produced.
- `hosted-gromacs`: GLM ignored the installed starter helper, made four failed
  command attempts, then completed operation `5433350c-176b-4e14-8c48-e4a7773a3072`
  through the external example runner. It did not recover native named outputs
  or deliver the promised verified report, instead asking for a follow-up. Its
  215.9-second final answer is not a successful end-to-end delivery.

Kimi K3/high on Token Factory passed all 14 **technical delivery** cases on the
same image. This was a comparison agent, not a changed or qualified default.
It retained the same core instructions but the replay appended an output-directory
instruction and explicitly set a 131072 context limit. Therefore these are
observed workflow times, not a controlled model-only performance claim:

| Workflow | Seeded GLM low | Kimi comparison high |
|---|---:|---:|
| Original CIF inventory | 21.1 s, delivered | 6.0 s, delivered |
| Original ligand advice | 35.3 s, answered | 9.0 s, answered |
| Original OpenFF preparation | 98.5 s, verified | 102.6 s, verified |
| CSV and error-bar plot | 6.0 s, incomplete | 9.1 s, delivered |
| Packaged GROMACS protocol | 215.9 s, incomplete delivery | 130.0 s, verified |

Kimi's GROMACS operation `61a674a3-fe8e-493f-8c2a-daf292300bd9` completed with
five bounded observations, no manual resume, and the exact native report and
download links. This exercises the long-poll repeat-detector correction that
R2 had failed. It is the packaged 20 ps NVT + 20 ps NPT + 20 ps production case,
not a customer GPCR protocol, scientific convergence or shared-capacity test.

Both models still overgeneralized parts of the held-out short-MD interpretation
answer. For example, Kimi assumed different cross-engine 1-4 conventions and
asserted a typical equilibration timescale without examining the supplied runs.
The delivery verifier does not grade this prose. Neither model is qualified as
an unattended scientific adviser, and a model switch alone does not fix that.

A fresh browser-initiated compound CIF request completed, retaining the measured
inventory plus a CSV. The real Workspace download returned the same bytes/hash
as its report. Screenshots retain the Scientific AI branding. Browser reload
during GLM's GPU work did not submit another operation. This is local-client
evidence, not qualification of Lynx's external tunnel or S3 mount.

Evidence directories under the private root:
`final-c1-{lynx,general,hosted}`, `final-kimi-{lynx,general,hosted}-comparison`,
their `*-delivery.json` reports, `final-polling-runtime`, and `output/playwright`.
Failures are retained alongside passes. A sanitized machine-readable summary is
in `agent-completion-20261002-receipt.json` beside this document.

### Closeout and remaining decision

Only task-owned loopback clients were stopped. R1, R2 and
`fs2-default-release-side-completion-final` retain exported `/data`; the final
client also retains a readable workspace export. At final closeout its 38 local
execution jobs were terminal (34 completed, four failed attempts from GLM's
GROMACS detour); both admitted final-image GPU operations had succeeded. The
task-owned browser session is closed. No tenant, key, bucket, cloud endpoint,
quota, customer model set or shared default was changed. Lynx's existing public
`/health` returned HTTP 200 after testing; this is availability, not new-release
qualification.

Combined verdict: **candidate published; not promoted; not customer-ready**.
Owner approval is still needed before selecting a different default. Then run
the chosen configuration unchanged through two clean cohorts and the authorized
customer-shaped public/client/storage path before replacement. Back up both
customer accounts, conversations and local state before any Serverless cutover.
Do not promote this GLM-configured image on the strength of the Kimi comparison.
