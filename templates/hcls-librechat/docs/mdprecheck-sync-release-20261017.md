# Synchronous MD precheck — 17 October 2026

`run_mdprecheck` now returns the completed verdict and owned JSON/HTML reports
in one call. No asynchronous option, background Job or operation polling is
offered. The runner and Scientific AI MCP connection allow 40 minutes. The
server allows 30 minutes of CPU checking inside a 35-minute native request.

The exact [image receipt](evidence/mdprecheck-sync-release-20261017.json) pins
source `a8fafa3c394137505aa9cf6f618b3bf59ded6d17` and skills `2026.10.17.3`.
This adds one layer to the preceding current-contract image; browser assets,
branding, CPU preparation, scientific progress and durable MD studies are
unchanged. MD simulations remain durable jobs; only precheck is synchronous.

The existing optional-precheck consent flow remains. An exact completed report
can be reused by lookup. A disconnected/ambiguous call is not automatically
resubmitted: look up completion, then explicitly retry when needed. `--rerun`
requests a new check. Upload idempotency is separate from execution.

Qualification includes the installed runner's nine tests; public REST/MCP
checks on 1UBQ source files and a standalone TPR; a deliberately defective
input; an 82-second source/probe call; overlapping requests; checksummed report
downloads; and an actual QA chat rendering the full interactive report inline.
Four simultaneous calls produced two explicit admission refusals; no quota was
raised and this is not a sustainable-capacity claim.

All five retained workbenches received the same managed skill/renderer files
and 40-minute live MCP deadline, without restarting the API or study/state
supervisors. Existing logins, chats and workspace bindings remain. New launches
use the pinned image. Provider endpoint image metadata on existing in-place
patched clients still names their base image; runtime hashes prove the patch.

Private release evidence: `mdprecheck-sync-20261017.HSjiPr` in the operator's
secure handoff area. No customer-key inference or customer data was used.
This release does not requalify every other model, capacity or GPU recovery.
