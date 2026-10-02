# Bounded scientific-agent reasoning

Status: implemented and tested in an isolated local candidate, **not deployed to
customers and not selected as the default image**. This does not resolve the
separate model-correctness/completion promotion blockers in
[the reliability report](agent-reliability-20261001.md).

The owner requested preventing the Lynx failure mode: prolonged high-reasoning
generation and unproductive tool loops without a useful result. Token Factory,
the chosen model, user data, API limits and running instances must stay unchanged.

## Behavior and configuration

These are server-side execution limits, not instructions the model can ignore.
The deployment script forwards them as environment variables. They take effect
only in an image containing the bounded-reasoning patch.

| Setting | Default | Meaning |
| --- | --- | --- |
| `SCIENTIFIC_AGENT_MODEL_DEADLINE_MS` | `90000` | Absolute duration of one agent model generation, including its empty-response recovery and existing error/fallback handling. Streaming does not reset it. |
| `SCIENTIFIC_AGENT_MODEL_TIME_MS` | `300000` | Accumulated model-invocation time in one graph run. Tool execution and simulation waiting are excluded. |
| `SCIENTIFIC_AGENT_REPEAT_ROUNDS` | `2` | Stop after two consecutive tool rounds repeat already-seen evidence; one initial read plus two identical repeats stops before a fourth generation. |

Values must be positive integers; zero is not an off switch. Existing recursion,
context and completion-token limits remain in force. No model selection or
automatic fallback was added. Existing fallback configuration, if supplied,
cannot restart the same generation's clock or recover from a budget expiry.

The deadline aborts a **child model-request signal**, not the graph's parent
signal or scientific job APIs. The caller is bounded even if a provider ignores
abort. Late stream chunks are rejected before tool execution. With a cooperative
OpenAI-compatible server, the HTTP connection is actually closed; this does not
prove that a remote provider immediately stops computation or billing.

On expiry the existing chat message gains a visible, host-generated pause:
the task is incomplete, outputs are retained, and submitted work is not cancelled
or resubmitted. It links to Runs and includes well-formed work IDs from this turn's
tool receipts when available. A partial reasoning stream and its pause use the
same message identity. There is no extra model call just to explain the stop.

The loop check hashes canonical tool names, arguments and completed results.
Changed state/output resets the repeat streak; alternating already-seen calls
do not. Only observation timestamps on known polling receipts are excluded.
Parallel tool rounds are counted after their results arrive. This is conservative
exact-evidence detection, **not** an LLM judging scientific progress. Changed but
still-useless arguments can escape it; the model-time and recursion limits remain.

October 2 correction: bounded `read_execution` observations of a matching saved
job in `pending`/`running` state are exempt from the repeat detector. A real GPU
run showed that three identical long-poll receipts can be healthy waiting. The
exception checks the exact helper name, matching UUID, requested/effective wait
and nonterminal/error-free state. Terminal rereads, zero-wait loops and arbitrary
tools remain bounded. Observations never reset accumulated model time.

Budgets are isolated by graph object/run identity and discarded on graph cleanup.
The accumulated clock is process-local, not a customer quota or durable billing
counter. A new explicit customer turn gets a new budget; it must reuse existing
operation IDs. No automatic unbounded continuation is installed. Existing durable
studies and Runs remain responsible for observing long-running scientific work.

## Implementation and integration

- `scientific-agent-budget.cjs`: deadline leases, run-local accounting, repeat
  detection and deterministic incomplete-work text; no job/provider/admin APIs.
- `patch-bounded-reasoning.mjs`: exact, fail-closed seams in pinned
  `@librechat/agents` 3.8.0. Both Graph and invocation patches are checked before
  writing. Drift or duplicate installation fails the image build.
- `Dockerfile.agent-reliability`: includes the patch in the reusable reliability
  build, including its exported runtime layer.
- `Dockerfile.bounded-reasoning`: small qualification overlay over the exact
  existing reliability candidate, without rebuilding unrelated frontend code.
- `scripts/deploy.sh`: forwards the three explicit controls; the release selector
  and default chat model are unchanged.

This applies to the scientific agent's main generation path and its existing
provider error/recovery path. It does not claim to bound every background/title
or separate context-summarization component in LibreChat. Domain execution,
scientific validation, monitoring and simulation limits are not replaced.

## Evidence (2026-10-01)

Baseline source: `49932c9` in `rene-tech/serverless-ai-cookbook`.
Isolated worktree: `/home/tux/worktrees/scientific-ai-bounded-reasoning-20261001`.
No edits were made in the main thread's reliability worktree.

Candidate local image:
`sha256:4bd14b9787853fe95da17d784f5d17dda6df115e77b20af3b4eed927b85f5f96`.
Base local image:
`sha256:5f6a45ff7044d75ad478d078c1a26cccdbb6af58bca0780215a2ff805b2e21f6`.
The standalone Dockerfile pins the corresponding registry base manifest
`sha256:16815c8cf0d0b8d3c343c56f90559bca1fea26d8c93e7294d544a826ec636af9`.
The clean R11 → reliability → reasoning-patch composition was also checked
against local R11 `sha256:259112f87cc5236866bed03e137fbd5ea5572287ccecef9e558e8b762f212161`.

Targeted coverage:

- 12 budget unit tests: continuous output, ignored abort, shared retry/fallback
  deadline, cancellation, listener cleanup, accumulated time, run isolation,
  changed evidence, alternating loops and retained work IDs.
- 9 installed-runtime tests on the actual compiled Graph/Run/ToolNode: visible
  pause after streamed reasoning, three-read loop boundary, changing results,
  accumulated budget, rejected late tool chunk, surviving submitted work,
  slow tool versus fast concurrent run, and real HTTP-stream socket closure.
- 15 existing recovery/completion/verified-delivery Node regressions.
- 15 deployment-script tests, including forwarding and unchanged model defaults.

Fault tests shorten deadlines to 40–400 ms; production defaults are unchanged
by those test settings. Scientific work in these tests is a controlled durable-job
fixture, **not** a claim to have run a new GPU simulation or measured platform
capacity. The unchanged tool APIs are never called by the budget module.

Live compatibility: six actual Token Factory responses through the installed
graph (three low and three high reasoning) completed normally on the existing
`zai-org/GLM-5.3-Flash` model. The fixed `17 + 25` probe returned `42`, finish
reason `stop`, with reported usage. Latest pair: 801 ms low / 589 ms high;
each reported 26 input and 3 output tokens. This is only integration compatibility,
not a scientific or performance qualification.

Retained failures/limitations:

- The live catalog check hit a connection timeout with direct fetch, the installed
  SDK and the model's client transport, while chat generation worked. The live
  check suite therefore reports **2 passed / 1 failed**, not all green. The
  `GET /models` connectivity discrepancy remains unresolved; it is not a reason
  to alter a customer's provider/model selection.
- The unchanged baseline `test_agent_instructions.py` has two failures: the
  current instructions have 12,571 characters versus its 10,000-character gate,
  and rendered prefixes exceed 10,500. Neither the prompt nor those assertions
  were changed or relaxed here. These belong to the main reliability workstream.
- No full browser/customer rollout, resumed real GPU study, production fallback
  qualification or complete scientific acceptance cohort was performed here.
  Those remain required before promoting the shared candidate to customers.

## Reproduce

From the checkout root, build the qualification overlay with the pinned base
manifest in `Dockerfile.bounded-reasoning`, then run:

```bash
docker run --rm --network none --entrypoint node \
  --mount "type=bind,src=$PWD/templates/hcls-librechat,dst=/qa,readonly" \
  scientific-ai-bounded-reasoning:20261001-side-candidate --test \
  /qa/test-installed-agent-budget.cjs /qa/test-scientific-agent-budget.cjs \
  /qa/test-scientific-provider-recovery.cjs /qa/test-scientific-completion.cjs \
  /qa/test-scientific-verified-delivery.cjs
python3 -m pytest -q -p no:cacheprovider \
  templates/hcls-librechat/test_deploy_networking.py
```

The opt-in `test-live-tokenfactory-agent-budget.cjs` needs `NEBIUS_API_KEY` via
the environment and network access. Never put its value in arguments or evidence.

## Ownership and promotion

Owner/purpose: side-conversation implementation of explicitly requested bounded
reasoning. Local test containers used `--rm`; none remain running. No cloud
resources, tenants, buckets, keys, platform jobs or customer deployments were
created or changed. Only local candidate/base image tags and this worktree are
retained for integration. Reconcile these task-owned artifacts at handoff or by
2026-10-08; do not remove shared base images, customer clients or parent worktrees.

Integrate this isolated change into the main reliability work, resolve its
existing promotion blockers, then qualify the exact final image through the
customer browser path with chat/storage/job preservation before changing the
shared release selector. This side change is not permission to deploy a failing
main candidate or switch the user's model.
