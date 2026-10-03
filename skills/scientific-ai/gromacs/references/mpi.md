# Multi-GPU GROMACS: shape, submission and evidence

Use `gromacs-mpi` for **one** simulation spanning multiple GPUs, or for the
external-MPI 1×1 reference run. Use multiple independent `gromacs` jobs for
independent replicas/windows. These are different objectives: shorter time to
one result versus more completed simulations per GPU-hour. MPI does not create
independent samples, and a larger shape does not automatically make MD faster.

## Published shapes, not hard-coded client limits

Discover `get_model_schema(model_id="gromacs-mpi", protocol="scientific-batch-v1")`
before submitting. The implementation contract introduced on 2026-10-03 has:

| Field | Meaning |
| --- | --- |
| `nodes` | 1–8 distinct admitted nodes; default 2 |
| `gpus_per_node` | 1, 2, 4 or 8; default 1; one MPI rank per GPU |
| Total GPUs/ranks | `nodes × gpus_per_node`, at most 16 |
| `threads` | 1–8 OpenMP threads **per rank**, default 8 |
| `jobs` | Exactly one job with `id: "gang"`; ordered native steps |

Thus 1×1, 1×2, 1×4, 1×8 and 2×8 are contract-valid; 3×8 is not. Other published
accepted shapes remain usable too. A nodes-only request retains one GPU per node
and its old checkpoint identity. A shape accepted by JSON schema can still wait
for a compatible pool; acceptance, available capacity and measured speed are
separate facts. Do not change customer physics or use a different key to get
around admission. An older live deployment may not yet expose the new fields.

One-node execution uses a single Pod and local MPI. Multiple nodes are admitted
together by JobSet/Kueue. The platform selects ranks/host slots/device mapping;
do not insert `mpirun`, `-gpu_id`, `-gputasks`, `-ntmpi`, SSH configuration or
provider node names in the native command. Preparation, analysis and coherent
file publication run once on the coordinator, not independently on every rank.

## API and MCP use the same scientific operation

Read [the portable gateway client contract](../../scientific-gateway/references/portable-client.md)
for authentication and file transfer. Keep credentials in the trusted client,
never in parameters, archives or model context. Discover the current typed tool
`submit_gromacs_mpi_workflow`, operation `run-workflow`, and the source artifact
role `gromacs-inputs` / semantic type `gromacs-input-bundle/v1`.

For an inspected finite `simulation.tpr`, use the deterministic bundle helper
and one of the parameter files: [2×1 legacy](../examples/prepared-tpr-mpi.json),
[1×8](../examples/prepared-tpr-mpi-8gpu.json), [2×8](../examples/prepared-tpr-mpi-16gpu.json).
They do not create a TPR or choose its force field, timestep, steps or seeds.
The two larger examples use a **32 GiB example workspace budget**, not a universal
recommendation. Adapt it and the optional trajectory-analysis steps to the files
the actual TPR writes before submission.

MCP through the installed, resumable client:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model gromacs-mpi --tool submit_gromacs_mpi_workflow --operation run-workflow \
  --source /workspace/md/input.tar.gz --parameters /workspace/md/parameters.json \
  --entry-name gromacs-inputs --semantic-type gromacs-input-bundle/v1 \
  --media-type application/x-tar --compression gzip \
  --output /workspace/md/receipt --idempotency-key md-scaling-1x8-attempt-01 \
  --display-name 'Prepared MD, 1 node x 8 GPUs' --wait-seconds 0
```

`--wait-seconds 0` performs one bounded status observation, not a zero-second
network connection. Run the identical command against the same receipt directory
to resume observation. Do not change the idempotency key or submit a fresh job
because a poll times out. In LibreChat use its durable study executor so the
receipt and dependent analysis survive a disconnected chat. The parameter file
contains only model parameters, **not** the scientific submission envelope.

Direct REST does not need an LLM or MCP. First upload/finalize the real input
archive and canonical scientific manifest through the authenticated artifact
API. With the returned manifest artifact reference in `manifest-artifact.json`
and the same parameter document in `parameters.json`, construct the request:

```sh
request_key='md-scaling-1x8-attempt-01'
jq -n --slurpfile manifest manifest-artifact.json --slurpfile params parameters.json \
  --arg id "${request_key}" \
  '{schema:"fs2-serve.nebius.ai/scientific-run-request/v1",operation:"run-workflow",
    service_class:"customer-batch",input_manifest:$manifest[0],parameters:$params[0],
    client_context:{display_name:"Prepared MD, 1x8",correlation_id:$id}}' \
  > request.json
curl --fail-with-body --silent --show-error \
  --header "Authorization: Bearer ${SCIENTIFIC_AI_API_KEY}" \
  --header "Idempotency-Key: ${request_key}" \
  --header 'Content-Type: application/json' --data-binary @request.json \
  "${SCIENTIFIC_AI_BASE_URL}/v1/models/gromacs-mpi:submit"
```

Here `SCIENTIFIC_AI_BASE_URL` is the API origin without `/v1`, and the key comes
from the application's secret environment; do not enable shell tracing. The
REST envelope has **no** `idempotency_key` JSON field: use the `Idempotency-Key`
HTTP header. The named MCP tool instead accepts its flat `idempotency_key` field.
The manifest reference must contain the exact finalized artifact ID, hash, byte
count, MIME type and compression, not a guessed example. Send only one logical
submission through either interface; repeat the same identity only to recover
an uncertain admission, not to create a second comparison run accidentally.

Both paths return the same durable operation. Observe it at
`GET /v1/operations/{id}` / `get_scientific_status`, read
`GET /v1/operations/{id}/result` / `get_scientific_result` after publication, and
download/hash-check the manifest's artifacts. Cancel explicitly through
`POST /v1/operations/{id}:cancel` / `cancel_scientific_run` when requested.
An HTTP timeout is not cancellation. Record the interface and its timing
separately from engine runtime; a transport comparison must use a distinct
deliberate operation per run, the same input bytes and unchanged physics.

## Transport and qualification are operator-owned

The current candidate configures `ucx-local` within one node: CUDA-aware Open MPI
and UCX can use shared memory/CUDA IPC, while GROMACS checks algorithm support.
The multi-node path remains `tcp-host-staged`, with GPU-direct communication
disabled. On the inspected H100 full nodes, NVLink joins GPUs **within** each
node, but no RDMA/InfiniBand network is configured **between** the two nodes.
Customers do not select an unqualified transport through request flags.

Read `fs2-mpi-topology.json`, per-rank `FS2_MPI_RANK_BINDING` lines and native
logs in the returned outputs. Configured transport is not observed transport.
Missing rank/device receipts or GPU-utilization measurements mean unknown;
never translate them into proof of CUDA IPC, GPUDirect RDMA or full utilization.

As of this skill's 2026-10-03 source update, legacy 2×1 H100/TCP native recovery
has historical evidence; **new 1×2/4/8 and 2×8 live API/MCP qualification and
matched performance results are pending**. Do not turn passing offline examples
into a customer performance claim. Use the exact release's later evidence when
available; do not impose a permanent skill-side ban on published accepted shapes.

For a scaling recommendation compare the exact external-MPI image on 1×1,
1×2/4/8 and, if capacity allows, 2×8 with unchanged TPR hash, precision, requested
steps, offload flags, output cadence and checkpoint policy. The NVIDIA
thread-MPI `gromacs` App is a useful additional baseline but is not the identical
binary. Small systems or cross-node TCP can scale negatively. Retain engine
ns/day and ms/step, useful durably completed steps, wall/queue/staging/export
time, GPU allocation interval, total occupied GPU-hours, retries and returned
artifact hashes. Separate repeated work after recovery from unique completion.

## Read native results before reporting a benchmark

The helper's `result.json` is a platform scientific-run result containing
`output_manifest` and publication/semantic-validation status. It is **not** the
native GROMACS result. Reading a guessed `steps` field from that envelope and
returning a report with zero timing rows is incomplete analysis, not success.

After the helper returns `state: verified`, inspect
`native_outputs.results[].source_result_file` from the helper response or saved
receipt. Each reference includes engine, job/operation ID, schema, status, source
result hash and workspace URL; the actual command timings remain in that exact
hash-verified file. Listing these references from a saved receipt is read-only:

```sh
jq -r '.native_outputs.results[] | select(.engine == "gromacs")
  | .source_result_file' /workspace/md/receipt/receipt.json
```

For an older client without `native_outputs.results`, locate the already
hash-verified native runtime result artifacts by semantic type:

```sh
jq -r '.verified_artifacts[]
  | select(.semantic_type == "gromacs-workflow-result/v1")
  | .path' /workspace/md/receipt/receipt.json
```

Inspect **each returned path**, not `output-00.artifact` by assumption. For a
`--recover-operation-id` retrieval, use `recovery-receipt.json` instead. If only
the outer platform result was saved, retrieve its output manifest and referenced
runtime result through the existing verified client; no new simulation is needed.
Do not overwrite previous accepted receipts or resubmit to fix a report.

For each native document, check schema
`fs2-serve.nebius.ai/gromacs-workflow-result/v1`, matching `operation_id`/`job_id`,
`status: succeeded`, and a complete inventory when that field is present. Read
`completed_steps` and `commands`: command records carry `step_id`, `segment`,
`exit_code`, `wall_seconds`, `performance_ns_per_day`, `log` and `finished_at`.
Use the original request's step IDs and command types to identify actual
`mdrun` records; analysis commands are not simulation repeats. Segments and
retries are not additional independent replicas. Check the complete requested
repeat/window set against the actual completed records before any aggregation.

Require a nonempty timing table with real completed `mdrun` records. Null or
absent performance means unknown, not zero ns/day. Inspect the retained native
logs for GROMACS timing/`Performance:` output and record the source if recovering
a metric. If a requested timing still cannot be established, mark that part of
the benchmark incomplete and explain the exact missing evidence. Never emit an
empty table and call the benchmark done because the outer operation succeeded.
Do not sum per-segment ns/day; retain individual segments and compute aggregate
useful throughput from durably completed simulated duration and elapsed time.

## Output budget and failure diagnostics

`max_output_bytes` bounds total files in the workflow's workspace, not only a
single final download. The implementation default is 4 GiB and request maximum
is 48 GiB; live schema, assigned scratch and bucket quota remain authoritative.
Budget for staged TPR/input files, checkpoint generations, segment/final `.gro`
files, XTC/TRR/EDR parts, joined copies and analysis outputs. A ~12.5-million-atom
benchmark generated ~862 MB per final `.gro`; repeated files exhausted its 4 GiB
request budget even though integration progressed. File count also has a bound.

Estimate from real input sizes and requested trajectory cadence, retaining
headroom; do not silently disable requested output to make a run fit. Larger
bucket capacity alone does not raise this per-request limit or Pod scratch.
If the estimate exceeds published limits, report the exact requirement rather
than split/change the scientific protocol without agreement.

The candidate runtime publishes a failed diagnostic `result.json` when final
inventory exceeds the budget, with `inventory_complete=false`, exact error,
bounded log references and last committed checkpoint generation. That is a
failed/incomplete delivery even when GROMACS completed integration. It does not
erase native files to manufacture success. Retrieve diagnostics and committed
checkpoint references, and agree a corrected request/budget; do not report
missing scientific outputs as an empty successful result.

## Native continuation is not GPU process snapshotting

Recovery uses the same operation's coherently committed GROMACS `.cpt`, immutable
input/recipe identity and complete peer restart. The default one-GPU layout is
backward compatible; non-default GPU count is part of the recipe identity.
Changing shape/settings requires a new logical request and deliberate scientific
continuation, not silently mutating a retry. Retain all `.partNNNN` files and
validate joined times/overlap. Independent replicas need independent seeds.

No CUDA/CRIU process snapshot or MPI-world GPU snapshot is qualified by this
contract. Native checkpoints protect scientific progress; they do not remove
image pull, input localization, MPI initialization or transport startup.

## Primary references

- [GROMACS parallel performance](https://manual.gromacs.org/2026.2/user-guide/mdrun-performance.html)
- [Per-rank GPU selection](https://manual.gromacs.org/2026.2/user-guide/environment-variables.html#envvar-GMX_GPU_ID)
- [Open MPI CUDA support](https://docs.open-mpi.org/en/v5.0.8/tuning-apps/networking/cuda.html)
- [Native checkpoint continuation](https://manual.gromacs.org/2026.2/user-guide/managing-simulations.html)
