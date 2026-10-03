# GROMACS multi-GPU client candidate — 2026-10-03

Source preparation only: no candidate image has been built/published by this
subtask, no shared default selector changed, and no customer instance replaced.
Live MPI shape/performance qualification belongs to the parent MPINAT campaign.

## What changes

- The root-owned scientific batch helper gives a check-once (`wait_seconds=0`)
  observation its normal bounded network deadline. It must preserve the original
  remote operation and receipt rather than replay scientific work after timeout.
- Canonical GROMACS skill 2026.10.03.1 describes single-node and multi-node MPI,
  `nodes` 1–8, `gpus_per_node` 1/2/4/8, maximum 16 GPUs, per-rank threads and
  backward-compatible one-GPU defaults. Live discovery still wins.
- Examples cover legacy 2×1 and new 1×8/2×8 shapes, exact customer TPR physics,
  practical REST/MCP submission, native checkpoint identity and explicit output
  budgeting. They do not assert new live qualification or GPU process snapshots.
- The skill distinguishes outer platform result from native runtime artifacts.
  Benchmark completion requires the requested repeat set and actual native
  timing records, not an empty table following a successful platform status.
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
native-MD artifact bridge with explicit runtime-result file references, and
`/opt/hcls-librechat/gromacs-mpi-release.json` provenance. The image preserves
customer-state supervision, entrypoint/environment, current UI/agents, CPU
OpenFF runtime, ClawBio extensions and existing analysis tools. It does not run
the old full OpenFF installation or derive from the older Lynx image. The build
verifies the core bundle and exercises the real inherited LibreChat skill loader;
those are install checks, not customer or molecular-dynamics acceptance.

The provenance binds client source revision, immutable base, helper/bridge bytes, bundle
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

Build only from the reviewed, clean committed overlay files. This command has
not been run by this subtask. Do not push a tag or change the shared selector
merely because the recipe exists; the parent owns publication and deployment.

## Acceptance remaining before promotion

1. Build from the committed source, record exact image digest and inspect the
   provenance document and inherited base identity.
2. On the final candidate, recover the saved system/QA study and hash-verify its
   original artifacts without another admission. Keep the old receipts.
3. Exercise authenticated API, MCP and actual installed-skill paths with internal
   QA credentials, same TPRs and meaningful native results. Verify nonempty
   benchmark reporting and requested repeats, including queue/disconnect recovery.
4. Verify backend-supported 1×1, 1×2/4/8 and 2×8 execution as capacity permits,
   rank/GPU receipts and actual transport. Record pending/failed bounds honestly;
   TCP inter-node execution is not proof of RDMA or a performance improvement.
5. Check a sibling OpenFF/analysis/client-state workflow on the candidate before
   selecting it for future installs. Do not replace the Lynx instance in this task.

180 combined offline tests passed across portable GROMACS examples/contracts,
bundle integrity, release provenance, native artifact references, polling and
scientific workflow/client regressions. Bundle version `2026.10.03.1` verifies
36 skills / 84 files. Skill validation, Ruff and `git diff --check` pass.
Source and bundle tests are recorded in the linked Task Deck card
`fs2-gromacs-mcp-observation-r20261003`; a code test is not a live deployment claim.
