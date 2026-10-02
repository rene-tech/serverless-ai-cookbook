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

## Qualification in progress

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
