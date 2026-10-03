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
