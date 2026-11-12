# Portable RFdiffusion requests

## Unconditional backbones

This example creates two **unconditional backbones**. It is not hotspot binder
design or an affinity prediction. Run it only after your live
`get_model_schema(model_id="rfdiffusion")` exposes `submit_rfdiffusion`, the
`design-backbone` operation and the matching input contract. A catalog entry
alone is not qualification of every workflow.

Install/configure the portable client first, then run from its extracted
directory. The parameter schema and source role below are exact named values;
artifact IDs, hashes and the eventual operation ID come from the actual
responses, never copied placeholders.

```bash
mkdir -p inputs runs
cat > inputs/backbone-note.txt <<'EOF'
Research test: two unconditional 80-residue protein backbones, seed 7.
No receptor, hotspot or experimental binding claim.
EOF
cat > inputs/backbone-parameters.json <<'EOF'
{
  "schema": "fs2-serve.nebius.ai/rfdiffusion-parameters/v1",
  "operation": "design-backbone",
  "contigs": ["80-80"],
  "num_designs": 2,
  "seed": 7,
  "diffuser_T": 50
}
EOF

.venv/bin/python invoke-scientific-batch.py \
  --model rfdiffusion --tool submit_rfdiffusion \
  --operation design-backbone \
  --source inputs/backbone-note.txt --media-type text/plain --compression none \
  --entry-name design_constraint --semantic-type rfdiffusion-design-constraint/v1 \
  --parameters inputs/backbone-parameters.json \
  --idempotency-key rfdiffusion-backbones-80-seed7-001 \
  --display-name 'Two unconditional 80-residue backbones' \
  --output runs/backbones-80-seed7 --wait-seconds 1800
```

The client performs all five steps without sending file bytes through the LLM:

1. Hash/upload/finalize `backbone-note.txt` as `text/plain`.
2. Create `input-manifest.json` with schema
   `fs2-serve.nebius.ai/scientific-artifact-manifest/v1` and an entry containing
   **all three** fields: `name`, `semantic_type`, `artifact`. The last field is
   the server's verified immutable reference, including hash/size/media type.
3. Upload/finalize that outer manifest as
   `application/vnd.fs2.scientific-manifest+json`, then submit the typed request.
4. Preserve the returned `op-...` ID in `receipt.json` and poll that exact ID.
5. Download `output-manifest.json`, `result.json` and `output-NN.artifact` files,
   checking every declared byte count/SHA-256 before recording `state=verified`.

If the wait expires, use `--observe-output runs/backbones-80-seed7`; do not
change the idempotency key or submit a replacement. An unexpected admission
result remains unknown until reconciled. A model failure is retained, not
converted into a successful retry.

Select coordinate artifacts by the output manifest's semantic/media type,
not their ordinal filename. Inspect sequence length, structure completeness,
finite coordinates and provenance before chaining into ProteinMPNN/folding.

For `scaffold-motif`, the source contract is a **PDB**:
`name=target_structure`, `semantic_type=protein-structure-pdb/v1`,
`media_type=chemical/x-pdb`, uncompressed. Its contig/hotspot parameters are a
different workflow; follow that live schema. A PDB, provenance note and JSON
manifest are not interchangeable, even when a filename ends in `.json`.

## Target-conditioned binder backbone

This public [upstream target](https://github.com/RosettaCommons/RFdiffusion/blob/9273ef67335acaf91df0150473a274759229cdf6/examples/input_pdbs/insulin_target.pdb)
contains chain A, residues 1–150. The request retains that receptor and designs
one 70-residue backbone conditioned on hotspots A59/A83/A91. This configuration
has completed with finite, complete coordinates and retained receptor geometry;
that is not evidence of binding affinity or an experimentally accepted binder.

First check that the live schema advertises `scaffold-motif`, space-separated
contigs, `hotspot_residues` and the PDB artifact contract. From the extracted
portable-client directory, upload the target once and use its actual returned
artifact ID in both the parameters and manifest:

```bash
set -e
mkdir -p inputs runs
curl --fail --location --output inputs/insulin_target.pdb \
  'https://raw.githubusercontent.com/RosettaCommons/RFdiffusion/9273ef67335acaf91df0150473a274759229cdf6/examples/input_pdbs/insulin_target.pdb'
.venv/bin/python - <<'PY'
import hashlib
from pathlib import Path
raw = Path('inputs/insulin_target.pdb').read_bytes()
assert len(raw) == 222658
assert hashlib.sha256(raw).hexdigest() == 'b5ab52ee165f33b3d467407ecc3607cb5b70fb6c2972cf2d6ed7ff3294153480'
PY

.venv/bin/python upload-artifact.py \
  --model rfdiffusion --file inputs/insulin_target.pdb \
  --media-type chemical/x-pdb --compression none \
  --idempotency-key rfdiffusion-insulin-target-upload-001 \
  --output-dir runs/binder-target-upload

.venv/bin/python - <<'PY'
import json
from pathlib import Path
artifact = json.loads(Path('runs/binder-target-upload/artifact.json').read_text())
parameters = {
    'schema': 'fs2-serve.nebius.ai/rfdiffusion-parameters/v1',
    'operation': 'scaffold-motif',
    'contigs': ['A1-150/0 70-70'],
    'num_designs': 1, 'seed': 8101, 'diffuser_T': 50, 'length': 70,
    'hotspot_residues': ['A59', 'A83', 'A91'],
    'input_pdb_artifact_id': artifact['artifact_id'],
}
Path('inputs/binder-parameters.json').write_text(json.dumps(parameters, indent=2) + '\n')
PY

.venv/bin/python invoke-scientific-batch.py \
  --model rfdiffusion --tool submit_rfdiffusion --operation scaffold-motif \
  --source inputs/insulin_target.pdb \
  --source-artifact runs/binder-target-upload/artifact.json \
  --media-type chemical/x-pdb --compression none \
  --entry-name target_structure --semantic-type protein-structure-pdb/v1 \
  --parameters inputs/binder-parameters.json \
  --idempotency-key rfdiffusion-insulin-binder70-seed8101-001 \
  --display-name 'Receptor-conditioned 70-residue binder backbone' \
  --output runs/insulin-binder70-seed8101 --wait-seconds 1800
```

`--source-artifact` reuses the finalized target without another source upload;
the client creates/uploads the canonical outer manifest and submits typed MCP
arguments. Retain the upload and operation directories. If observation times
out, use `--observe-output runs/insulin-binder70-seed8101` on the same helper.
Retrieve `get_operation` and `get_operation_result` with that saved operation ID;
download verification is identical to the unconditional example above.

The space after `/0` separates receptor and designed chain. The equivalent array
is `["A1-150/0", "70-70"]`: array entries are joined with spaces, not separate
designs. `A1-150/0/70-70` is invalid. Here `length=70` counts the designed chain,
excluding the 150-residue receptor; hotspot numbering comes from the uploaded
PDB, not the output's reordered chains. Review every design's actual seed,
checkpoint name/checksum, receptor mapping and coordinate validation before
sequence design or independent complex scoring.

## Checkpoints and optional advanced controls

Model checkpoints are RFdiffusion weights, not saved job-recovery checkpoints.
When advertised, `checkpoint="auto"` selects `complex-base` for hotspot designs
and `base` otherwise; explicit `complex-base` or `complex-beta` requires a
retained receptor. `complex-beta` changes the learned design distribution; it
does not guarantee binding. Sequence conditioning selects `inpaint-seq` before
the hotspot/default choice and requires that checkpoint.

The following advanced controls are available when your live parameter schema
advertises the operation and every field you intend to use. Omission preserves
the existing native defaults. Three bounded H100 workflows passed scientific and
artifact checks: partial diffusion with sequence preservation, motif masking with
`monomer_ROG`, and C2 symmetry with zero noise plus contact guidance. The first
two retain the sampling release; C2 uses the corrected launcher release. These
checks do not establish every option combination or every GPU/region.

| Control | Exact field semantics and requirements |
| --- | --- |
| Partial diffusion | `operation="partial-diffusion"`, an uploaded PDB and `partial_T` in `1..diffuser_T`. The complete input/output length must match, with zero offset for retained residue indices. This diversifies coordinates; it does not resume an interrupted job. |
| Preserve sequence during partial diffusion | `provide_seq=["0-4","145-149"]` selects inclusive **zero-based** positions in the complete ordered input/output; this example requires 150 positions. It is partial-diffusion-only and uses `inpaint-seq`. |
| Mask motif sequence | `inpaint_seq=["A2","A5"]` selects retained **PDB chain/residue identities**, unlike `provide_seq`. The backbone remains constrained; masked output residues are native glycine placeholders requiring downstream sequence design. Uses `inpaint-seq`. |
| Noise | `noise_scale_ca` and `noise_scale_frame` are nonnegative numbers; zero disables the corresponding translation/rotation noise. Both default to native 1 when omitted. |
| Guiding potentials | `guiding_potentials` is a list of typed objects, e.g. `[{"type":"monomer_ROG","weight":1.0}]` for monomer compactness. Use only the live registry's fields and required binder/hotspot context. `guide_scale`/`guide_decay` require a potential; omitted values retain 10/`constant`. Native `cubic` decay ignores `guide_scale`. These are heuristic constraints, not affinity scores. |
| Symmetry | `symmetry="c2"` describes two chains; exact total length must be divisible by symmetry order. Discover `cN`, `dN`, `t3`, tetrahedral/octahedral/icosahedral and their type-specific options from the schema. The native PDB output supports at most 62 unique one-character chain labels. Symmetric `olig_contacts` additionally needs a nonempty allowed contact selection, such as `olig_inter_all=true`; do not apply arbitrary potential/symmetry combinations. |

For more than 64 designs, prefer the [hosted campaign contract](portable-campaign.md)
when the live schema advertises it: one operation with explicit total designs,
native batch size and bounded chunk parallelism. That guide also retains the
client-driven compatibility path and exact qualification boundary. Campaign
design counts are not counts of accepted binders.
