# Native workflow identity — 17 October 2026

The workbench exposes **only the native Serverless operation ID as a job ID**.
Saving a workflow is not GPU admission: its acknowledgement says explicitly
when no job exists yet. The live panel then shows each admitted native job,
measured progress/rate, durable progress and verified inline results. Those
operation IDs are the same ones shown in Serverless Jobs.

A workflow can prepare inputs, run several model operations and analyze results.
Its owned `output_directory` locates this saved work; it is not an execution ID.
The public surface does not expose the supervisor's private receipt UUID or
provide an old-ID resolver. Receipt identity and immutable scientific execution
internals remain private, preserving running work and historical evidence.

## Exact release

See the [machine-readable receipt](evidence/workflow-native-identity-release-20261017.json).
Image `workflow-identity-20261017-r4` contains runtime source
`319f7e517df82a6905442df990e61b515547f47e` and canonical skills `2026.10.17.5`.
`Dockerfile.workflow-identity` builds the qualified delta on the pinned
synchronous-precheck image. The full `Dockerfile` includes the same public
projection. The README launch button and deployment scripts select the same
immutable manifest; older release recipes are not deployment defaults.

## Current interfaces

- `run_scientific_workflow` saves work and returns the public projection;
  `read_scientific_workflow` observes it by `output_directory` without submitting
  or restarting work. Both are registered in the seeded agents.
- The packaged command-line submission returns the same projection and exits
  successfully after confirmed admission. It does not print another job ID.
- The authenticated workbench uses `GET /studies/status?output_directory=...`
  and `POST /studies/cancel` with `output_directory`. UUID path routes are removed.
- Links use `/demos?tab=runs&workflow=<encoded output_directory>` and render live
  progress/results inline. Local shell execution IDs are explicitly local
  command identities, not Serverless jobs.
- Unknown progress is unknown, not zero. Several model jobs have several real
  operation IDs, never a fabricated parent job ID. No GPU shape is added to the
  customer projection.

## Qualification and retained clients

Two independent final-release System QA chats submit unchanged 0.1 ns GROMACS
workloads from a public 1UBQ fixture, reusing its hash-matching completed
precheck. Acceptance checks admission, automatic execution/analysis, measured
ns/day, durable completion, eight verified artifacts per run, inline report/3D
rendering and the identical operation IDs in the real Jobs console. The fixture
warning is retained; these are interface/workflow tests, not convergence or
sustainable-capacity measurements.

An earlier candidate's second chat exposed a remaining command-line UUID and
missing observer registration; it is retained as a **failed** candidate test.
The final image fixes both paths. Runtime verification also checks the loaded
skill registry, not just the copied files: running APIs cache skill bodies.

The five retained clients receive a paired in-place patch, including explicit
refresh of the six platform-managed agent instructions and stale tool lists.
User-created agents, model settings, ACLs, keys, buckets and existing processes
are preserved. The scientific executor, worker and batch transport are unchanged;
the command-line helper's transport functions are AST-identical. Active customer
work is not restarted. Exact old generated acknowledgement links are repaired
once with backups; historical user messages and tool receipts are not rewritten.

Provider endpoint metadata still names the original image for in-place patched
clients. VM recreation must select the current pinned default and retain existing
state/storage bindings; it must not recreate an old base image and assume its
runtime overlay survived. Existing browser tabs need one normal reload.

Offline qualification: 159 Python workflow tests, 71 installed-image Node tests,
10 React tests, six deployment-link tests, a production UI build, branding checks
and canonical skill-bundle verification. The actual deployed five clients pass
public health/login, exact assets and loaded-agent/skill checks.

Private detailed evidence is retained in the operator packet
`workflow-native-identity-20261017.BM6aPI`. This release does not requalify other
models, long simulations, MPI, sustained capacity or GPU failover. Known missing
step counters in the native timing report remain explicitly unknown; live
observed/durable progress remains available separately.
