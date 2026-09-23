# Bounded operation polling correction

The candidate is
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d`,
runtime source `88109af67d11726d1e07e14c5d0ff4e83a4837e0`.
It supersedes `d074317` for the pending Rene replacement. No endpoint has been
stopped or changed. Deployment still requires the release owner's explicit go.

The [machine-readable receipt](demos/evidence/20260923-operation-polling/receipt.json)
records exact-image tests, protected-byte comparison and two ordinary-owner
fresh result recoveries. This is a polling/transport correction, not the combined
customer-ready verdict.

## Demonstrated defect and correction

The long LAMMPS cohort's MCP status call exited with `Server returned an error
response`, after its last durable receipt at 18:57:23 UTC. The release owner
correlated this with control-plane OOM restarts and separately owns the backend
streaming fix. The original operation was resumed without another admission.

MCP 2.2.0 maps non-JSON-RPC HTTP errors, including both 401/403 and 5xx, to that
same generic exception. The corrected client retains only the underlying HTTP
status and bounded retry delay for the operation's reads/handshake. It does not
log credentials or raw server bodies.

- Status/result reads reconnect on identified transient HTTP, network, timeout
  or lost-session errors. There are at most five consecutive failed observations,
  with 1/2/4/8-second backoff (server delay capped at 30 seconds), within the
  original observation window. Individual reads have a 60-second timeout.
- HTTP auth/validation failures, real operation `not_found`, explicit permanent
  tool errors and mixed exception groups containing permanent errors stop.
- Last authoritative operation state, identity, input references and receipts
  survive observation failure. Exhaustion is incomplete, not scientific failure
  or success; normal CLI returns resumable exit 75.
- Upload/admission are outside the retry boundary. Ambiguous admission remains
  ambiguous and is never replayed. Completed-result recovery uses the same
  read-only path, without submission arguments.

## Exact-image evidence

The packaged Python 3.11.2/MCP 2.2.0 environment passed 120 tests, including 35
actual-SDK HTTP fault cases. External pure-Python pytest tooling was mounted
read-only; no application dependency was installed or upgraded. The tests used
an isolated HTTP transport, no network, supervisor, customer bucket or GPU.

All 111 base layers remain, plus one helper layer. Comparison of 81,138 protected
entries found exactly one changed file, `/opt/bionemo/invoke-scientific-batch.py`.
The analysis venv, all skills, receipt publisher and application configuration
are unchanged. The real installed skill loader passes 83 skills, 77 resources
and 75 core hashes.

Two completed GROMACS operations were recovered through the public MCP endpoint
using their original ordinary owner key and two fresh empty local directories:
112 artifacts, 238,789,960 bytes, plus two manifests. All 114 downloads required
one transfer attempt, passed independent hashes, and matched the original
manifests byte-for-byte. No simulation was submitted. Larger LAMMPS reads remain
paused until the backend owner authorizes them. Deliberate faults were not
introduced into the live service.

Private logs and receipts are under
`/home/tux/secure-handoff/fs2-md-engines-20260923/client-operation-polling-r1-*`.
The receipt preserves the original live failure and the initial test-harness and
owner-selection preflight failures separately. The release owner owns the final
four-engine analysis, backend, endpoint and browser gates.

For replacement commands use the existing [stop-first runbook](MD_ANALYSIS_REPLACEMENT_20260923.md),
the refreshed account/assets exports `client-preflight-account-08` and
`client-preflight-assets-04`, and this new exact image. Previous dry-run receipts
bind `d074317`; refresh the dry run for this successor before any authorized stop.

Used `scientific-ai-librechat` and `scientific-ai-mcp` for the durable operation
boundary, `registry-supply-chain` for the immutable additive image, and
`scientific-ai-release-qualification` for scoped claims and retained failures.
