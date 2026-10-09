# Ripple evaluation for Scientific AI and the Lynx workflows

## Decision

**Do not enable Ripple by default.** There is a promising execution signal, but
this is not a qualified LibreChat integration or a reliable scientific agent.
Keep it an explicit experimental option until the integration and factual-output
issues below are addressed. The existing default and customer deployments were
not changed.

Ripple is a model gateway/router, not a replacement for the scientific agent,
OpenFF, GROMACS or the platform scheduler. Its [announcement and clarification](https://nebius.slack.com/archives/C0571SPM8SE/p1789505340535519)
describe routing, compatibility and observability across coding clients.

## What was actually tested

27 real LibreChat agent conversations, using the released R11 image and installed
tools, not a simulated LLM loop:

- Original private Lynx structure-inventory, force-field recommendation and
  OpenFF parameterization requests: three direct-GLM repetitions, two fixed-GLM
  Ripple repetitions and two quality-router repetitions (21 conversations).
- Three direct GPT OSS control requests using the same original inputs.
- One actual hosted GROMACS reference workflow per main arm (three conversations).
  This is the existing alanine onboarding protocol, not a production GPCR study.

All arms used the same core instructions, customer input file and molecule,
explicit low reasoning effort, 16,384 output-token request budget, 131,072 client
context setting, CPU OpenFF environment and 240-second chat observation deadline.
Each conversation had a fresh output prefix. The original CIF hash and prompt
hashes are retained privately. Polling adds up to roughly three seconds to chat
wall time. No failed scientific operation was secretly resubmitted.

Timing is exploratory: small sample, non-randomized order, shared provider
capacity and possible prompt caching. It is not a statistically established
speedup or SLA. The third direct repetition and second Ripple repetitions ran
in parallel. Early setup attempts were retained separately and are not reported
as model benchmarks: explicit-client registration, provider discovery, capability
token format and client readiness had to be configured first.

### Exact versions and isolation

- Workbench source baseline: `e3319bfbf5234c52cb8056027e9881b312f885c2`;
  R11 image source `4239aa4a6ed2c02ee3ed392b1a3242266c4ec82e`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:06d0ca2e976242c4120c4f56773359fff2b9a2464e890e262a6e3b7c5018da4d`.
- Core instruction SHA-256:
  `ba07139072eb8f6b660095520fb44f42916d0cde4ef9161f360e724f258be1e9`.
- Ripple local source: `2842cdbb7c897a4c0177058b54e2c152925b56a6`.
- Fixed route: singleton GLM-5.3-Flash allowlist. Quality route: only the verified
  Token Factory IDs GLM-5.3-Flash, Kimi-K3, Qwen3-235B-A22B-Instruct-2507,
  GPT OSS 120B and DeepSeek-V4-Pro. No native-login providers or external demo
  routing service. Compression was off in both Ripple arms.
- Each arm: isolated local R11 container, 4 CPUs / 12 GiB, separate workspace
  and Mongo state. Same system QA non-admin platform identity; no new tenant,
  bucket, key, public endpoint or GPU node.

This Ripple version does **not** provide a stock managed LibreChat adapter.
The experiment added a small evaluation-only launcher and explicit
`advanced-unmanaged` capability/client identity to the full production gateway
and routing manager. No routing, scoring, provider-projection or retry algorithm
was changed. The client provider URL/key were overridden only inside the two
candidate containers. This is an experimental adapter, not a deployable upstream
LibreChat integration. It did not impersonate Codex or modify global Ripple state.

## Measured outcomes

Times below are user-visible chat wall times. A fast incomplete reply is a failure,
not a performance win.

| Path | Original CIF inventory | Original OpenFF request | Hosted GROMACS reference |
| --- | --- | --- | --- |
| Direct GLM-5.3-Flash | 21.1, 27.1, 30.1 s; answers had interpretation errors | 1/3 completed: 159.4 s. Two stopped after skill loading at about 6 s | Stopped after skill loading; no job submitted |
| Ripple, fixed GLM | 24.1, 24.1 s; some unsupported interpretation | 1/2 completed in-chat: 141.4 s. Other chat exceeded 240 s; its CPU job later finished and files were recovered | 165.5 s; job/files verified; correctly described the short protocol |
| Ripple, quality routing | One empty answer at 3.1 s; one answer at 15.1 s | 2/2 executed and produced valid exports: 102.3 and 108.4 s; handoff defects remained | 123.4 s; job/files verified, but final scientific report materially wrong |

The quality router actually used **GPT OSS 120B and GLM-5.3-Flash**, including
switches within one OpenFF tool loop. The client-facing model label remained
GLM, so that label cannot be used as actual-model attribution. Gateway records,
not the UI label, establish the executing model.

The direct GPT OSS control returned the inventory/advice in about six seconds,
but the OpenFF request only checked identity and offered instructions instead
of executing parameterization. Thus neither a model switch alone nor the current
direct default solved unattended task completion.

Force-field advice was faster through the tested router (about 9 s), but included
invalid helper flags, treating OPLS as Amber-family, and CGenFF penalties labeled
as kcal/mol. Direct/fixed GLM also made unsupported chemical/structural claims.
There is no clean scientific-success cohort for any complete configuration.

### Independent artifact checks

Five completed OpenFF bundles passed the installed independent verification
suite and authenticated HTTP checksum readback for ten files each. Checks covered
the customer's molecular identity/stereochemistry, 78 atoms, neutral net charge,
Sage 2.2.1, exported charges/coordinates and manifest hashes. One routed request
used an equivalent canonical SMILES rather than preserving the original string;
identity equivalence was independently checked, not counted as a different
molecule. The late fixed-route bundle does **not** convert its timed-out chat
into a success.

Both accepted GROMACS jobs finished successfully. For each, all 56 raw artifacts
and 55 native files were read back over authenticated HTTP. Native names, sizes
and hashes were matched against the engine's result manifest, not guessed from
artifact ordering:

- Fixed Ripple operation: `1296b71d-ab3f-4073-bac7-a7c9c5baf935`.
- Quality Ripple operation: `e35453c3-dfe0-4452-9cca-5f2995085576`.

The recipe minimized, then ran **20 ps NVT + 20 ps NPT + 20 ps production**.
Successful short execution is not evidence of equilibrium, force-field accuracy,
full GPCR readiness or long-run throughput. GPU snapshot performance was not
evaluated here; the reported reference job did not use a GPU snapshot.

## Why this is not a default-on recommendation

1. **Execution success did not ensure correct scientific reporting.** The quality
   route's GROMACS answer described a 1 ns NVT-only run, said pressure was absent,
   invented energy-drift/temperature checks and reported the wrong system size.
   Actual native files showed the short NVT/NPT/production protocol. Its first
   OpenFF report also claimed finite energy confirmed physically reasonable
   parameters; a finite calculation does not validate the force field.
2. **Transport success can still mean no usable answer.** The empty routed CIF
   reply was recorded as `succeeded` by the gateway, but LibreChat rejected it as
   incomplete. Source inspection and the passing upstream test
   `TestVerifyChatCompletionStreamPreservesReasoningOnlyOutput` confirm that
   reasoning-only streamed output is deliberately preserved. This is not semantic
   completion checking. Pre-output fallback cannot solve a valid final answer
   that fails to perform the requested work.
3. **Conversation continuity is not integrated.** Advanced-client requests had
   no `X-Ripple-Session-ID`. We observed GLM/GPT OSS switching during the same tool
   loop. Ripple has session/continuity mechanisms, but this LibreChat adapter does
   not supply the required identity. A default integration must pin/attribute a
   scientific workflow deliberately, not assume coding-client integration applies.
4. **The router has no validated chemistry objective.** These inputs were commonly
   classified as `unknown` or `mathematics`; no scientific correctness outcomes
   were supplied to its learner. Its quality ranking is not a molecular-dynamics
   validation system.
5. **User handoff still broke.** A generated ligand download link used a Unicode
   non-breaking hyphen in place of the real filename's ASCII hyphen. That exact
   advertised link returned HTTP 404, although the actual file passed readback.
6. **Cost and token-rate improvement are not established.** The current workbench
   response hook retained finish reasons but received empty provider usage metadata
   on these streamed calls. Usage/cost are therefore **unavailable**, not zero.
   Catalog pricing was fetched, but multiplying unverified client token estimates
   would not establish billed cost. We measured end-to-end time, not reliable TTFT.

Fallback/protocol tests in Ripple's gateway and executor passed locally, including
pre-output recovery and terminal-stream tests. They do not constitute a live
provider-outage or multi-tenant qualification. All allowed providers in this
experiment share Token Factory's endpoint failure domain, so endpoint-wide
failover was not demonstrated.

Scientific review references: [CGenFF parameter/charge penalty methodology](https://pmc.ncbi.nlm.nih.gov/articles/PMC3528813/)
and [OpenFF Interchange compatibility limitations](https://docs.openforcefield.org/projects/interchange/en/stable/using/edges.html).
Provider integration reference: [Token Factory's OpenAI-compatible API](https://docs.tokenfactory.nebius.com/quickstart).

## What to do next

Prioritize deterministic execution/result checks in the existing workbench:
an execute request must yield the requested verified artifacts or an explicit
recoverable operation; scientific numbers and download links should come from
measured records. Keep Lynx's direct API route for prepared MD inputs so its
pipeline need not depend on an LLM at all.

If pursuing Ripple, use an opt-in per-workbench sidecar first. It needs a supported
LibreChat client grant, stable conversation/run identity, observed-model attribution,
token usage and task-correctness feedback. Then repeat original customer requests,
long jobs, interruption/resume and concurrent users on the exact candidate. Do
not automatically replace models inside explicitly pinned scientific workflows.

Ripple cannot make OpenFF's charge calculation or GROMACS's numerical kernels
faster. Its opportunity is reduced agent waiting, provider compatibility and
model selection. This experiment suggests potential, not sufficient reliability
to make it the default.

## Evidence and closeout

Task: `fs2-ripple-lynx-evaluation-r20261001`, under NIM Fast Start Platform.
Private evidence root (contains customer input and credentials; do not publish):
`/home/tux/secure-handoff/fs2-ripple-lynx-evaluation-20261001`.

Retained there: setup/replay/verification scripts, original input manifest,
per-conversation transcripts, `comparison.json`, provider metadata, gateway route
records, `artifact-verification.json`, `links-md-verification.json`, catalog
snapshots and the evaluation adapter. Sanitized measurements are adjacent to
this report. No source customer CIF, molecule prompt, token or password belongs
in the public repository.

The three task-owned local containers were stopped on 1 October at 14:14 UTC,
after scientific subprocesses had finished and evidence was captured. Their
local files are retained for review through at least 8 October; no automatic
deletion has been scheduled. Customer resources, the existing QA cloud endpoint
and global provider defaults are unchanged. Closeout and all 27 timing records
are in [the sanitized measurement receipt](ripple-lynx-evaluation-20261001.json).
This closes the evaluation only, not the parent workbench-release qualification.
