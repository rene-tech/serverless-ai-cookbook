# One complete portable RFdiffusion request

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
