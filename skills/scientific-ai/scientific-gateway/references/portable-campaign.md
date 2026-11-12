# RFdiffusion campaigns

## Hosted campaign: one operation

When `get_model_schema(model_id="rfdiffusion")` advertises `parameters.campaign`, prefer
one `submit_rfdiffusion` request through the existing typed MCP or portable
`invoke-scientific-batch.py`. One finalized input manifest, idempotency key,
operation ID and operation-owned result prefix cover the campaign. The service
registers its chunks; you do not create child requests, keys or bucket folders.
After all stage admissions are confirmed, execution continues if the observer
disconnects. If admission is incomplete/unknown, preserve the returned ID and
reconcile only the saved request with its original key, as the error instructs.

**Qualification boundary:** one typed-MCP hotspot campaign completed 65 designs
on H100 in eu-north1, in nine single-attempt chunks (eight batches of eight plus
one), with `max_parallelism=4`. Delivered structures, partial and final artifacts,
REST/MCP parity and complete owner export were verified; later chunks started
after the submission client disconnected, and portable result recovery added no
inference. The 1,000-design plan and transport/failure checks retain CPU-only
evidence. This is not evidence of 1,000-design throughput, affinity or fleet capacity.
Use only fields advertised by the live schema and an authorized compute budget.

Without `campaign`, `num_designs` retains its ordinary 1–64 request meaning.
With `campaign`, `num_designs` is the native **batch size per GPU chunk** (1–64);
`campaign.total_designs` is the total and `campaign.max_parallelism` bounds
simultaneously eligible GPU chunks. Chunk size changes startup amortization and
retry granularity. Smaller chunks do not create a new execution-time budget.

This template requests 1,000 unconditional 80-residue backbones: fifteen batches
of 64 plus one of 40, seeds 8100–9099. These are proposed backbones, not accepted
binders. From the extracted portable-client directory:

```bash
mkdir -p inputs runs
printf '%s\n' '1000 unconditional 80-residue backbones; seeds 8100..9099; no binding claim.' \
  > inputs/hosted-campaign-note.txt
cat > inputs/hosted-campaign-parameters.json <<'EOF'
{
  "schema": "fs2-serve.nebius.ai/rfdiffusion-parameters/v1",
  "operation": "design-backbone",
  "contigs": ["80-80"],
  "num_designs": 64,
  "campaign": {"total_designs": 1000, "max_parallelism": 4},
  "seed": 8100,
  "diffuser_T": 50
}
EOF

# This command uploads input and submits the authorized scientific campaign.
.venv/bin/python invoke-scientific-batch.py \
  --model rfdiffusion --tool submit_rfdiffusion --operation design-backbone \
  --source inputs/hosted-campaign-note.txt --media-type text/plain --compression none \
  --entry-name design_constraint --semantic-type rfdiffusion-design-constraint/v1 \
  --parameters inputs/hosted-campaign-parameters.json \
  --idempotency-key hosted-backbones-001 --display-name '1000 backbone designs' \
  --output runs/hosted-backbones-001 --wait-seconds 1800
```

The helper writes the canonical `input-manifest.json`, exact typed MCP
`request.json` and accepted root in `receipt.json`. For a hotspot campaign,
follow the [target upload example](portable-rfdiffusion.md) first, retaining the
actual `input_pdb_artifact_id`, contig, hotspots and checkpoint. Add the same
`campaign` object and batch size to that parameter file; invoke the normal batch
helper with `--operation scaffold-motif`, its PDB/`target_structure` contract and
`--source-artifact` pointing to that exact finalized upload. No target is uploaded
per chunk, and no source ID or manifest role is inferred from a filename.

The current conservative dependency-envelope check accepts at most **116
chunks** for these member names: 7,424 designs at batch size 64, or 116 at batch
size 1. It rejects the next chunk before model admission; increase a smaller
supported batch size or reduce the total. This is a CPU-checked transport bound,
not a measured execution capacity. The final 8 GiB output bound, scientific
validation, seed range and advertised execution deadlines still apply.

### Observe, retrieve and handle partial work

```bash
.venv/bin/python invoke-scientific-batch.py \
  --observe-output runs/hosted-backbones-001 --wait-seconds 180
```

This only observes/downloads the saved operation. Observation timeout/exit 75
does not stop the hosted campaign or reset its cumulative execution/retry budget.
Use `get_operation` / `get_operation_result` with that one ID. Full success
requires `result_available=true` and verified final artifacts.

Before full completion, `partial_results` exposes `requested_units`,
`chunk_count`, `verified_chunks`, `verified_units` and
`running_assigned_units`, `failed_assigned_units`, `waiting_assigned_units`,
`cancelled_assigned_units`, `unknown_assigned_units`. These count designs
assigned to chunks; they are not live within-chunk completion measurements.
`partial_results.complete=false` never means full campaign success. A failed
chunk and downstream blocked work remain visible; successful chunks are retained.

If `partial_results.available=true`, resolve its `output_manifest` through the
existing `get_scientific_artifact` / `download_scientific_artifact` path using
trusted file transfer, or sync the exact returned
`partial_results.customer_storage` bucket/prefix using [own-bucket access](bucket-access.md).
The ordinary batch observer verifies the final result; it does not automatically
download partial manifests after a failed/action-required observation. Verify
each manifest entry's SHA-256 and size before using partial files.

Each `rfdiffusion-campaign-chunk/v1` artifact is a zstd-compressed tar containing
sanitized per-design PDB/JSON files and a chunk index. Full completion adds one
`rfdiffusion-campaign-index/v1` JSON artifact joining every chunk, design, seed
and declared file hash. Select by semantic type, not an ordinal download name;
verify archives before safe extraction. Source/seed lineage remains meaningful
even when some designs fail, and does not establish experimental binding.

### Account admission and failure handling

Read `get_account_budget({})` (REST `GET /v1/me/budget`). When advertised,
`concurrency` contains `max_concurrent`, `limit_unbounded`, `active_operations`,
`remaining_admission_slots`, `scope` and `basis`. Null means unknown, not zero;
`limit_unbounded=true` describes only that key's admission limit. These are
**logical root reservations**, including failed graphs whose reservations remain,
not GPU counts. All campaign chunks share one root reservation. Observed headroom
may be cached and is neither reserved capacity nor a promise of immediate admission.
`max_parallelism` bounds this campaign's GPU chunks; fleet availability can yield fewer.

When `action_required=true`, inspect the structured error and `graph.blocked_on`
(`stage_id`, `status`, `failed_at`, `dependents`), retaining successful partials.
When advertised, `graph.admission_slot_held` reports whether this operation's
original root reservation is currently held; the structured error repeats it
when present. An exact `true` means held and `false` means no reservation. Null
or an absent field is unknown. Failure or a graph's action-required flag alone
does not prove release or retention. Fence new client-driven fanout while
admission or failure disposition is unresolved. Inspect account reservation
counts and, when abandoning the exact owned operation is intended, use the
existing `cancel_operation` with its actual ID; re-read status/capacity afterward.
Never automatically cancel unrelated work or change keys to evade a limit.

Native retry, failure-grace and cumulative graph-deadline policy still governs
execution. `graph.deadline_at` is a returned deadline, not a fresh allowance per
chunk. Do not promise automatic slot release after a fixed delay, automatic
failed-science replay, or stage resume after the graph has automatically closed.

## Client-driven compatibility path

`invoke-scientific-campaign.py` partitions a campaign into ordinary requests of
at most 64 designs, then uses the existing batch client's upload, admission,
receipt and observation implementation. It is a local command, not a hosted
MCP tool or a new scheduler. The native service still owns GPU placement,
fanout, queueing, retries and cancellation. Use your issued endpoint/key through
the environment as described in `README.md` of the extracted client package.

### Hotspot binder campaign: pre-upload the actual target

For `scaffold-motif`, `parameters.input_pdb_artifact_id` must be the **actual
finalized target artifact ID**, not the manifest entry name `target_structure`,
a filename or a placeholder. The existing batch helper does not substitute
that field. Upload the target once before freezing the campaign, then reuse
that same reference in every child. Planning rejects a mismatched ID or source
hash/size/MIME/compression before any child admission.

First supply `inputs/target.pdb` and choose real retained receptor residues and
hotspots from it. The parameter example below requires chain A residues 1–47
and hotspots A12/A27; edit those scientific choices to the actual target before
planning. Do not infer residue numbering or accept this example as evidence of
binding. Check the live schema for the named checkpoint and operation first.

```bash
.venv/bin/python upload-artifact.py \
  --model rfdiffusion --file inputs/target.pdb \
  --media-type chemical/x-pdb --compression none \
  --idempotency-key binder-target-001 --output-dir runs/binder-target-001
```

Read the returned reference when creating the parameter file; do not hand-copy
an ID from another operation or upload:

```python
import json
from pathlib import Path

artifact = json.loads(Path('runs/binder-target-001/artifact.json').read_text())
parameters = {
    'schema': 'fs2-serve.nebius.ai/rfdiffusion-parameters/v1',
    'operation': 'scaffold-motif', 'contigs': ['A1-47/0 100-100'],
    'length': 100, 'hotspot_residues': ['A12', 'A27'],
    'input_pdb_artifact_id': artifact['artifact_id'],
    'num_designs': 1, 'seed': 8100, 'diffuser_T': 50, 'checkpoint': 'complex-beta'
}
Path('inputs/binder-parameters.json').write_text(json.dumps(parameters, indent=2) + '\n')
```

Freeze a bounded two-child pilot (two designs plus one). The `plan` command is
offline; `run` submits authorized science and observes it through the same public
MCP client as ordinary requests:

```bash
.venv/bin/python invoke-scientific-campaign.py plan \
  --designs 3 --chunk-size 2 --operation scaffold-motif \
  --source inputs/target.pdb --source-artifact runs/binder-target-001/artifact.json \
  --media-type chemical/x-pdb --compression none \
  --entry-name target_structure --semantic-type protein-structure-pdb/v1 \
  --parameters inputs/binder-parameters.json \
  --idempotency-key binder-pilot-001 --display-name 'Hotspot binder pilot' \
  --output runs/binder-pilot-001
.venv/bin/python invoke-scientific-campaign.py run \
  --output runs/binder-pilot-001 --wait-seconds 1800
```

The client creates each canonical scientific manifest with entry
`target_structure`, semantic type `protein-structure-pdb/v1`, and the same actual
artifact reference. All child parameter files preserve that ID and the target,
contig, hotspot, checkpoint and other settings; only seed/count change. Missing
or changed source references fence further admission instead of causing another
target upload. Plan larger campaigns only with the requested compute budget and
deliberate seed ranges; do not replay the pilot's seeds under fresh keys.

### Larger offline plan

The example below plans 1,000 **unconditional backbones**, not 1,000 accepted
binders. The same procedure supports a schema-valid `scaffold-motif` parameter
file with its real target PDB, published target role and explicit constraints.
Do not change contigs or hotspots just to fit a chunk. Scientific features must
be supported by the caller's live model schema before execution.

```bash
mkdir -p inputs
cat > inputs/campaign-note.txt <<'EOF'
Research campaign: 1000 unconditional 80-residue backbones, seeds 8100..9099.
No receptor, hotspot or experimental binding claim.
EOF
cat > inputs/campaign-parameters.json <<'EOF'
{
  "schema": "fs2-serve.nebius.ai/rfdiffusion-parameters/v1",
  "operation": "design-backbone",
  "contigs": ["80-80"],
  "num_designs": 1,
  "seed": 8100,
  "diffuser_T": 50
}
EOF

# Offline only: no credentials, upload, model call or scientific work.
.venv/bin/python invoke-scientific-campaign.py plan \
  --designs 1000 --operation design-backbone \
  --source inputs/campaign-note.txt --media-type text/plain --compression none \
  --entry-name design_constraint --semantic-type rfdiffusion-design-constraint/v1 \
  --parameters inputs/campaign-parameters.json \
  --idempotency-key backbone-campaign-001 --display-name '1000 backbone designs' \
  --output runs/backbone-campaign-001
```

Inspect `campaign.json` and its 16 frozen child parameter files: 15 × 64 designs
plus 40, with seeds 8100–9099 exactly once. `--designs` supplies the total; each
child replaces only `num_designs` and `seed` in the parameter template. Other
scientific choices remain unchanged. Changing the source hash, parameters or
campaign key changes child identities; an existing output directory cannot be
reused for different science. The current server seed ceiling remains 1,000,000.
For a small two-request pilot, choose `--designs 3 --chunk-size 2` in a separate
campaign directory/key. Chunk size is explicit and frozen, defaults to 64, and
cannot exceed the existing native request limit.

When the user has authorized this campaign's compute, run it using the normal
Scientific AI environment. This is the first command that may submit science:

```bash
.venv/bin/python invoke-scientific-campaign.py run \
  --output runs/backbone-campaign-001 --wait-seconds 1800
```

The source is finalized once and recorded in `source-artifact.json`; every
child gets its own canonical manifest, typed request, idempotency key and
receipt. An existing finalized `artifact.json` can instead be supplied to
`plan --source-artifact PATH`; its exact hash, size, MIME and compression must
match the source. Original files must remain intact while admitting new chunks.
Live schema/parameter/source preflight still happens through the unchanged batch
client before each new request; an offline plan is not scientific qualification.

Iteration is sequential by default. A bounded observation timeout exits `75`
and does not submit later chunks; `--wait-seconds` is the observation bound per
child, not a renewed scientific execution budget. Repeating `run` first observes accepted IDs;
unknown admission is reconciled only through the original saved request/key.
If any unknown exists, that invocation reconciles unknowns only; a subsequent
explicit `run` can admit remaining chunks. Failed, rejected, cancelled or held
children fence later admissions and remain in the summary. There is no
automatic failed-science replay or filter relaxation.

```bash
# Read-only operation observation and verified result retrieval; no submission.
.venv/bin/python invoke-scientific-campaign.py observe \
  --output runs/backbone-campaign-001 --wait-seconds 180

# Permanently fence this campaign's future admissions; no remote cancellation.
.venv/bin/python invoke-scientific-campaign.py stop \
  --output runs/backbone-campaign-001
```

If cancellation is requested, take the actual accepted operation IDs from the
retained child receipts and use the existing `cancel_operation` contract. Never
cancel an inferred ID or replace an unknown request. Observation can continue
after the admission fence. No new owner, bucket or concurrency allowance is
created, and no sibling is implicitly cancelled.
Only one local campaign owner may run at a time. If `run` is still observing,
interrupt that local command before invoking `stop`; this leaves remote science
untouched and its original receipts available. Do not start a competing owner.

`summary.json` is a projection of original receipts: requested/submitted/
succeeded/failed/cancelled/unknown and other pending design counts, exact seed
ranges, operation IDs, source references, verified output manifests, and hashed
request/runtime/result references. Counts describe requested designs per child,
not experimental binders or a guarantee of affinity. Unknown cost remains null.
Each child's separate `admission_slot_held` is true/false only when proved by
its saved explicit typed status/error field; otherwise it is null. A failed
scientific result does not prove its quota slot was released. Scientific state
counts, including `held`, are not a count of occupied admission slots.
Already verified children are not submitted, polled or downloaded again. Retain
the whole private campaign directory, including `.receipt-history`, for restart.

CPU regressions establish client planning and failure handling. Large live
campaign throughput, cost and scientific success require separate measurements;
this client feature does not qualify every RFdiffusion capability or fleet GPU.
