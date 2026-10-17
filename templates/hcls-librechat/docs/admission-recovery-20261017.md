# Exact admission recovery — 17 October 2026

Runtime source `116728b7d4261e2bc6043165187a921384b8b21b`, image
`admission-recovery-20261017-r1`, digest
`sha256:7bec331506c04eabb00eb64d943bb63f9474edb75a5bdf3f913bb69c105ebce0`.
Built with `Dockerfile.admission-recovery` over the current identity/inline-viewer
release; scientist skills remain `2026.10.17.5`.

## Behavior

A lost submission response no longer permanently blocks the local study queue.
The batch transport persists the original owner, request, tool, key and input
identities before sending. It can recover a matching saved acknowledgement or
replay that **exact** request, at most three persisted reconciliation attempts.
It never reuploads inputs, invents another idempotency key, selects the latest
unrelated job, or restarts scientific computation. Explicit invalid requests,
changed input/owner, cancellation and exhausted reconciliation remain visible
failures. `ADMISSION_PENDING` is not treated as confirmed admission.

The receipt worker also recovers studies left in `needs_attention` by the prior
transport, including a process dying after the child acknowledgement but before
the study write. It then continues observing the admitted native job and
releases the next queued workflow normally. Only native operation IDs appear
as customer job IDs; no compatibility endpoint or old-ID mapping is added.

## Qualification scope

- 197 focused Python tests cover lost acknowledgements before/after acceptance,
  process death, immutable request binding, bounded replay, queues and cancellation.
- The exact installed image imports successfully. Its scientific executor
  `scientific_study.py` is byte-identical to the prior image, preserving analysis
  implementations already pinned by saved studies.
- The originally blocked System QA 185,486-atom GROMACS study recovered using
  its existing request and native identity. It completed 0.6 ns, automatic
  analysis and verified result publication. The UI reported a last measured
  simulation rate of 308.27 ns/day and 4m37s native operation elapsed time;
  these are different measures, not a universal workload-speed guarantee.
- A second independent chat submitted the same scientific workload through
  the normal skill and saved-workflow tool. It queued behind the first study
  and was admitted automatically after completion. It also completed 0.6 ns,
  analysis and publication, reporting 309.237 ns/day. The chat's live progress
  card showed the native job ID, measured rate and completed/checkpointed work.
  Its inline report rendered the final 7,844 protein atoms in an interactive
  3D view, visually inspected in the browser. This is a final-coordinate view,
  not a trajectory animation or scientific validation of the input system.

The full local scientific test collection requires additional libraries absent
from the operator's client-test environment; this is not a claim that that full
suite passed. No other model, sustainable capacity, or native GPU failure is
newly qualified by this transport release.

## Deployment

The shared default is selected by `scripts/release-image.sh`; full image builds
also copy the changed transport sources. Managed clients can receive these
three files in place. Refresh only the local receipt worker while holding its
existing queue lock, at an idle/known-admitted observation boundary. Preserve
the API, supervisor, scientific executor, user data, and native GPU job.
Do not terminate active analysis or preparation to acquire that lock.

The patch was applied to the five retained managed clients: Rene, Arseny,
LynxKite, Whitelab and System QA. Rene's observer was refreshed between cycles;
the existing native GROMACS pod retained its UID and zero restarts. No customer
inference was submitted for qualification, and no customer data or identities
were changed.

Provider endpoint metadata still names its original base image after an in-place
patch. Recreated instances must select the current default and preserve their
state/storage binding; do not assume runtime overlays survive VM recreation.
