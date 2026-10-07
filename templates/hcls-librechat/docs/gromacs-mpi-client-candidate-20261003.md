# GROMACS multi-GPU client candidate — 2026-10-03

Immutable candidates have been built and published to the existing registry.
No shared default selector changed and no customer instance was replaced.
Live MPI shape/performance qualification belongs to the parent MPINAT campaign;
the analysis-only checks below do not rerun a simulation on the new backend.

## What changes

- The root-owned scientific batch helper gives a check-once (`wait_seconds=0`)
  observation its normal bounded network deadline. It must preserve the original
  remote operation and receipt rather than replay scientific work after timeout.
- Canonical GROMACS skill 2026.10.03.3 describes single-node and multi-node MPI,
  `nodes` 1–8, `gpus_per_node` 1/2/4/8, maximum 16 GPUs, per-rank threads and
  backward-compatible one-GPU defaults. Live discovery still wins.
- Examples cover legacy 2×1 and new 1×8/2×8 shapes, exact customer TPR physics,
  practical REST/MCP submission, native checkpoint identity and explicit output
  budgeting. They do not assert new live qualification or GPU process snapshots.
- The skill distinguishes outer platform result from native runtime artifacts.
  Benchmark completion requires the requested repeat set and actual native
  timing records, not an empty table following a successful platform status.
- Recovery delivery accepts the actual `recovery-receipt.json` without copying
  or rewriting it. The installed deterministic `report-native-md.py` command
  verifies receipt/result/log identities and produces JSON, CSV and Markdown
  timing reports. Missing values remain unknown; a missing requested repeat or
  timing row is incomplete, not success. Absolute checkpoint steps are not
  silently converted into useful or durably completed work counts.
- The portable schema fixtures are byte-identical to the backend MPI parameter
  and scientific-run REST envelope schemas
  committed at `0aecab6bdca3346a74426cea24a4753cd4f54270`. This pins contract
  validation, not a deployment digest or completed 8/16-GPU benchmark.
  An offline execution of the documented REST example verifies its actual
  generated body and `Idempotency-Key` header; curl is stubbed and no request is sent.

## Candidate composition

`Dockerfile.gromacs-mpi-release` inherits the exact current default:

`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:873be148673dec6dc191ba30d2933c01acee4622fd3fa14888388378539f13d3`

It overlays only the canonical skill bundle, corrected scientific batch helper,
native-MD artifact bridge with explicit runtime-result file references,
verified native-MD delivery and deterministic timing-report modules, and
`/opt/hcls-librechat/gromacs-mpi-release.json` provenance. The image preserves
customer-state supervision, entrypoint/environment, current UI/agents, CPU
OpenFF runtime, ClawBio extensions and existing analysis tools. It does not run
the old full OpenFF installation or derive from the older Lynx image. The build
verifies the core bundle and exercises the real inherited LibreChat skill loader;
those are install checks, not customer or molecular-dynamics acceptance.

The provenance binds client source revision, immutable base, overlaid module bytes, bundle
manifest/hash inventory and backend schema revision. Final overlay uses one
filesystem layer to respect the retained image's long layer history. The current
`scripts/release-image.sh` remains unchanged until root qualifies and promotes a
specific candidate digest.

After committing the complete client source (including root's helper), the
release owner can prepare a candidate using the repository root as context:

```sh
docker build -f templates/hcls-librechat/Dockerfile.gromacs-mpi-release \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  --tag fs2-gromacs-mpi-client:20261003-candidate .
```

Build only from the reviewed, clean committed overlay files. Publication was
explicitly authorized for this campaign; the parent still owns selecting the
customer default and deployment. Do not change either merely because a build
or local test passed.

## Actual candidate evidence

The five original native-complete operations (benchSFI, SNC, SNI, STC and STI)
are retrieved by the seeded Kimi-K3/high agent with the existing system/qa
identity. No customer key, customer instance or new GPU execution is involved.
Old reports and receipts are retained, including unsuccessful attempts.

- R1 (`0700a6fd...`, image `73a3340a...`) recovered all five operations and
  produced 15 independently verified timing rows, but exposed a real mismatch
  between normal and recovery receipt names during native-MD result delivery.
- R2 (`59789c88...`, image `74b57893...`) includes the receipt fix, but the seeded
  SNC recovery agent exhausted its unchanged 25-tool budget after repeated
  inspection and malformed ad-hoc Python. It did not produce the requested
  report or reach native-MD delivery. This is a failed qualification, not a
  successful run just because the chat finished. Its stopped local container,
  workspace, original operation and traces are preserved.
- R3 source `0ba9ee5177684749e38e2577059e955d89021285` includes the deterministic
  report command and skill instructions to use it once. Its immutable image is
  `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:6eb9ee53b2cef53ef604a9315147fef894943a132cf36d8c9f31e8606048359b`.
  The registry digest, source, bundle 2026.10.03.2 and all six provenance hashes
  match inside the isolated running image. All five first-attempt ordinary
  recovery prompts passed independent verification: 15 real native timing rows,
  successful native-MD delivery, no receipt copy or GPU replay. Tool counts were
  17/20/20/23/15; two incidental inspection commands failed (SNC `sed`, STI guessed
  manifest shape) without breaking the verified report/delivery outcome. These
  errors are preserved, not claimed as an entirely error-free interaction.
- The follow-up 2026.10.03.3 skill and truthful CLI help include the complete
  recovery invocation. This addresses the observed unnecessary source-code
  searching; no submission/recovery behavior is changed. Exact r4 source is
  `a09a40c1a099bcb2e99c7e03caa644b30f78e86b`, image
  `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:6d8b2038097b180d5edd997d7346a1b56c879a5f00b4890fcc08b81c2a96b2da`.
  A fresh unchanged SNC prompt passed in 51.2 seconds / 12 tool calls, with
  three independently verified native rows, successful native-MD/report
  delivery and no failed inspections, receipt copies or GPU resubmissions.
  The same isolated candidate is used for separate actual/assumed Lynx CPU
  tests with original input files hash-pinned and mounted read-only.

The actual three Lynx CPU requests and six separately labeled representative
controls then passed their bounded first-attempt acceptance on exact r4. This
includes real ligand exports, chemical identity/charge checks and authenticated
downloads of 30 hash-verified output files. The original complex ligand took
99.4 seconds end-to-end, including 89.1 seconds of CPU AM1-BCC; no GPU was used.
The deliberate missing-file rejection is recorded explicitly. A source-only
verification regression captures plain-text exceptions rather than losing them
when a tool does not return JSON status. This does not change the r4 product
bytes. Full evidence and scientific limitations are recorded in the backend's
`acceptance/gromacs-mpinat-20261003/LYNX_AGENT_QUALIFICATION.md`.

Private evidence is retained under
`/home/tux/secure-handoff/fs2-gromacs-mpinat-20261003`, with separate
`agent-recovery-candidate-r1`, `-r2` and `-r3` folders, build metadata, manifests
and isolated state. R4 uses `agent-recovery-candidate-r4*`; these are separate
from the Lynx CPU test folders. The backend acceptance directory's
`AGENT_QUALIFICATION.md` and the Task Deck card record the final observed bounds.

## Acceptance remaining before promotion

1. On the final candidate, recover the saved system/QA study and hash-verify its
   original artifacts without another admission. Keep the old receipts.
2. Exercise authenticated API, MCP and actual installed-skill paths with internal
   QA credentials, same TPRs and meaningful native results. Verify nonempty
   benchmark reporting and requested repeats, including queue/disconnect recovery.
3. Verify backend-supported 1×1, 1×2/4/8 and 2×8 execution as capacity permits,
   rank/GPU receipts and actual transport. Record pending/failed bounds honestly;
   TCP inter-node execution is not proof of RDMA or a performance improvement.
4. Check a sibling OpenFF/analysis/client-state workflow on the candidate before
   selecting it for future installs. Do not replace the Lynx instance in this task.

196 combined offline tests passed for the exact r4 runtime/skill source, covering
timing reports, recovery delivery, portable GROMACS examples/contracts, native
artifact references, release provenance, polling, workflow/client and isolated
persistence/read-only-input launcher and CLI-help regressions. Bundle version `2026.10.03.3` verifies
36 skills / 84 files. Skill validation, Ruff and `git diff --check` pass.
Source and bundle tests are recorded in the linked Task Deck card
`fs2-gromacs-mcp-observation-r20261003`; a code test is not a live deployment claim.

## R5: actual new-study report gap and explicit upload encoding

The first remaining r4 MPINAT pair did not pass customer-shaped delivery.
benchMEM native operation `7c59f87a-d62c-46aa-bd1c-14cb1a5cf0e6` succeeded, and
its durable study completed, but its generic `operation-timing` report read the
outer envelope and contained only unavailable measurements. The initial chat
truthfully said admitted, not finished. An accepted/completed study alone does
not qualify a requested native throughput report; the original files remain.

The r5 candidate adds the typed, discoverable `native-md-timing` analysis phase.
It consumes a completed batch's exact `native-files.json` reference and uses the
same existing receipt/result/log-hash verifier and reporter as recovery. It
publishes Markdown/CSV/JSON as durable study deliverables, with explicit repeat
count checks and retained incomplete diagnostics. No new timing parser, model,
scientific default, physics change or GPU replay is introduced. The installed
GROMACS skill's complete saved-study example plans both batch and analysis
before admission. Original successful operations can be analyzed without replay.

benchPEP never reached native admission. Its agent used a standalone upload after
local study validation rejected a missing report. That exact upload finalized
223,219,412 bytes after 688.1 seconds of total helper wall time (not a measured
network-only interval), but returned `compression: none` for the
gzip archive because the generic uploader had no encoding field. The original
artifact is retained, not relabeled. R5 carries explicit optional compression
through tool schema, frozen upload identity, CLI reservation and final metadata
verification. Omitting it preserves old uncompressed receipt identities. A
per-attempt receipt now measures hashing, reservation, object PUT and finalization
with monotonic durations, byte count and wall timestamps; failures retain their
known phase/error type without credential or signed-URL fields. Timeout behavior
is unchanged. A
new durable batch is the preferred owner of bundle upload and inference;
correcting an unadmitted draft must not create duplicate scientific work.

R5 extends the additive image overlay with the study runner/schema, importable
native reporter and uploader/execution bridge. Baseline study helper bytes were
confirmed identical between this source and r4 before editing; current UI,
seeded Kimi-K3/high and tool budget remain unchanged. Bundle 2026.10.03.4 contains
85 verified files. Source tests are not final image/agent acceptance: exact r5
read-only recovery and native study/report delivery remain required before any
default promotion. The first pair's errors and old reports remain in
`agent-remaining-r4`; the supervisor stopped before the next pair.

The focused r5 regression cohort passed 148 tests, including real deterministic
report execution, normal/recovery receipts, future batch references, unchanged
native bytes, missing/tampered evidence, explicit encoding identity, streamed
upload metadata, polling and artifact delivery. The final upload-only refinement
then passed its 20 tests; the complete portable plan passed real admission
validation. Two broader unchanged baseline tests still assert old literal seed
phrases (`bounded logical` and `several related steps per edit`) absent from the
current seed; these are recorded rather than changing seeded instructions merely
to satisfy wording checks. Local broad structure tests additionally require
NumPy, absent from this host test venv. Neither limitation is counted as a pass.

The obsolete source-only seed assertions were subsequently corrected: tool
registration is checked in the seed, while the detailed prose is checked in its
actual file-backed tutorial source. The real seeded-primary regression now loads
the existing three-way merge module, forwards seed errors out of its test sandbox,
and verifies that the tutorial receives the legacy manual while the primary agent
does not. No prompt, runtime or candidate-image bytes changed. The four focused
workflow/discovery/instruction modules pass 44 tests, and all three existing
Node seed-merge tests pass. This resolves the stale wording checks, not the
separate host NumPy limitation or the outstanding live agent qualification.
