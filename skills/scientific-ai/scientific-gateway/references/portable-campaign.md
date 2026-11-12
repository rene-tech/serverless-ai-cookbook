# Portable RFdiffusion campaigns

`invoke-scientific-campaign.py` partitions a campaign into ordinary requests of
at most 64 designs, then uses the existing batch client's upload, admission,
receipt and observation implementation. It is a local command, not a hosted
MCP tool or a new scheduler. The native service still owns GPU placement,
fanout, queueing, retries and cancellation. Use your issued endpoint/key through
the environment as described in `README.md` of the extracted client package.

## Hotspot binder campaign: pre-upload the actual target

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

## Larger offline plan

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
its saved typed status/error or held-graph flag; otherwise it is null. A failed
scientific result does not prove its quota slot was released. Scientific state
counts, including `held`, are not a count of occupied admission slots.
Already verified children are not submitted, polled or downloaded again. Retain
the whole private campaign directory, including `.receipt-history`, for restart.

CPU regressions establish client planning and failure handling. Large live
campaign throughput, cost and scientific success require separate measurements;
this client feature does not qualify every RFdiffusion capability or fleet GPU.
