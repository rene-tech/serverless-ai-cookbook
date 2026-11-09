---
name: scientific-ai-hackathon
description: Connect Claude Code to Nebius Scientific AI and run a reproducible hackathon workflow using the participant's hosted models, private artifacts and result files. Use for first access, model selection, folding, binder design, sequence scoring or a short molecular dynamics project.
license: Apache-2.0
---

# Scientific AI hackathon workflow

For first-time Claude Code setup, read [connection and walkthrough](references/claude-code.md).
The workbench login, Scientific AI API key, Claude subscription and Token Factory
credentials are different. Use the participant's issued Scientific AI key for
MCP; never request the organizer's shared Token Factory or Tavily key. Skills do
not grant access, install model weights or require a new cloud IAM account.

## Choose an achievable experiment

Ask for the scientific objective, supplied sequences/structures, intended
outputs and time available. Start with one small, representative input before
expanding the experiment. Preserve the input, sequence numbering, chain names,
random seed, software version and all explicitly requested scientific settings.

Discover the caller's current catalog, then read the selected model's schema.
Use the existing `scientific-gateway` skill for submission, artifacts and durable
operation tracking, and the relevant workflow skill for scientific parameters.
In Claude Code, hosted `list_models`, `list_scientific_models` and
`get_model_schema` are the portable path; LibreChat-only `workbench_*`, local
executor and viewer tools are not implied by this connection.

Names and generations matter: AlphaFold and OpenFold are distinct; RFdiffusion,
RFdiffusion3 and RFD4-Proteina are not aliases. A model absent from the live
catalog is unavailable to this connection. Report the gap; offer an explicitly
named alternative without silently substituting it. Availability does not prove
that every upstream feature or hardware class is qualified.

## Run and retain evidence

- Upload actual local bytes using the supplied file client; a laptop path is not
  remotely readable. Obtain a finalized artifact and use the exact source role
  and manifest contract from the schema. Do not paste file bytes into chat.
- Submit once with a stable idempotency key. Save the exact returned operation
  ID and request. On a chat timeout, observe that operation before considering
  another submission. Never restart an accepted job merely to get a reply.
- Poll until the operation's result is available. Download the returned files,
  verify their sizes/checksums and inspect the scientific result. A successful
  transport alone does not establish a successful experiment.
- A resumed simulation may retain its cumulative wall budget. Use only the
  documented checkpoint/resume contract; do not promise fresh execution time.
- Put outputs in a new participant-owned run directory. Include a concise
  report, parameters, operation IDs, raw outputs, limitations and complete
  working download links. An interim update must say what is still running.

## Interpret results honestly

For a short event, choose a modest structure/binder/sequence batch or an MD
precheck followed by a bounded simulation. Estimate runtime from a comparable
recorded workload, separating queue/startup time from computation. A few hours
of MD do not establish convergence, binding kinetics or an equilibrium Kd.

Keep structural confidence (pLDDT, PAE, ipTM), sequence likelihood/nativeness,
interface energy and measured affinity separate. Do not label a confidence
ranking as Kd or convert an uncalibrated model score into nM. Label any model's
explicit affinity prediction, units, domain and uncertainty; experimental
validation remains distinct. Preserve failed designs and report the selection
criteria used to rank successful outputs.
