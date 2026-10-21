---
name: rfd4-proteina
description: Generate protein sequences and structures, or refine conditioned designs, with the hosted RFD4-Proteina App and annotated CIF inputs. Use for RFD4, not the separate RFdiffusion or Proteina-Complexa workflows.
license: BSD-3-Clause
---

# RFD4-Proteina generation

Use App `rfd4-proteina`, operation `generate`, and the typed MCP tool
`submit_rfd4_proteina` on `scientific-ai-apps`. LibreChat adds its server suffix.
Read the caller's live `get_model_schema` before submitting: skill installation
does not establish access or runtime readiness. Do not substitute `rfdiffusion`
or `proteina-complexa` if this App is unavailable.

This is hosted **generation**, not a local GPU installation or an oracle/search
workflow. Follow `scientific-gateway` for artifact transfer and native job
identity. A single generation request needs no campaign planner or local model.

## Establish the design problem

Confirm the intended length/chains and which sequence, coordinates or motif
regions are fixed versus designed. For conditioned work, establish the target,
chains, residue correspondence and intended interactions before changing inputs.
Preserve the original file; do not silently repair chemistry or remove conditions.

The input is one **annotated CIF**, not a plain sequence, PDB, server path or
upstream Hydra configuration. The annotations encode length and conditioning.
Use the pinned upstream monomer example for an unconditional demonstration;
see [input guidance and sources](references/inputs.md). YAML source must be
converted and validated to annotated CIF outside the hosted call. Do not assume
AtomWorks/RFD4 authoring dependencies are installed in LibreChat.

Fixed side-chain coordinates also constrain identity. Backbone-only conditioning
is appropriate when redesigning sequence. Preserve bonds, charges, ligands and
annotation columns; a generic CIF-to-PDB round trip can lose scientific intent.
Round-trip serialization alone does not prove that a condition is supported.

## Submit and observe

1. Upload the actual input with the existing trusted file helper. The scientific
   manifest has one entry named `annotated-cif`, semantic type
   `rfd4-proteina-annotated-cif/v1`, media type `chemical/x-cif`, compression
   `none`. Decompress a `.cif.zst` source to a new file first; renaming it is not
   decompression. Finalize the file and its manifest; never invent artifact IDs.
2. Pass the advertised staged run fields directly to `submit_rfd4_proteina`,
   with `operation: "generate"`, `service_class: "customer-batch"`, finalized
   `input_manifest`, `parameters`, and one stable `idempotency_key`.
   [parameters.json](examples/parameters.json) preserves the published defaults
   for one generated candidate. One candidate is a functional example, not a
   statistically meaningful design campaign or a guaranteed successful binder.
3. Keep requested scientific settings. `num_replicates` counts generated designs;
   `batch_size` controls processing batches, not how many accepted designs exist.
   `nsteps` and recycling affect the scientific budget. The `thinking_*` presets
   are upstream front-loaded schedules requiring `nsteps: 60`. For a different
   budget, explicitly supply `recycle_schedule` as `[step_count, recycle_depth]`
   bands whose step counts sum to `nsteps`; this replaces the chosen preset
   unchanged. A null/omitted schedule retains that preset. Never rescale it
   automatically. See the [deliberate custom-budget example](examples/custom-schedule.json);
   fewer steps or recycling is not an equivalent-quality claim or default.
   `partial_trajectory_fraction_steps` requests a fraction of the diffusion
   trajectory for an existing structure; it is not a distance in Angstroms.
   Do not reduce steps, disable compilation, change the seed or remove conditions
   just to make an error or slow run disappear.
4. Report the returned native `op-...` ID. Observe that same ID with
   `get_operation` and `get_operation_result`; an accepted/queued job is not a
   completed design. A status-read timeout is not permission to resubmit.
   Preserve specific errors, failed stage and the reported recovery action.
   If admission is unknown, recover the existing receipt/ID before another call.

In LibreChat, the installed `invoke-scientific-batch.py` helper can perform the
upload/manifest/submission/download steps from real workspace files; see the
[concrete client example](references/client-example.md). Do not write another
uploader or paste structure bytes into chat.

## Results and inline viewing

Wait for published, hash-verified results. The `designs` artifact is an
uncompressed tar (`rfd4-proteina-designs-tar/v1`); the `result` artifact is JSON
(`rfd4-proteina-result/v1`). Inspect `designs[]` for each exact relative path,
SHA256, size and atom/sequence counts; do not guess filenames. The tar preserves
upstream `outputs/inference_samples/` files, optional trajectories,
`resolved-config.yaml` and `provenance.json`. Generated CIFs are uncompressed.
Safely extract to a fresh owned workspace directory, rejecting traversal, links
and excessive expansion. Never overwrite the input or strip annotations from
originals. Verify the selected files against the result inventory.

For LibreChat, pass one to four verified, decompressed structure paths to
`visualize_structure_mcp_structure-viewer` as `workspace_files: [{path, label}]`
and include its returned UI marker verbatim. The operation-only viewer does not
resolve arbitrary staged archives. Show the actual structure inline, with the
original CIF/archive available secondarily; a download link alone is not the
requested visualization. If the viewer is unavailable, report that client gap
without resubmitting the model.

Report `progress.designs_completed` versus `designs_requested`, conditioning
evidence and observed validation failures. Preserve measured runtime fields;
do not turn missing timings into a speed claim.
Coordinate/provenance validity does not establish foldability, binding affinity,
specificity or experimental function. This hosted route does not run refolding
oracles, reward-guided/beam search or BioIR evaluation. Never invent their scores.
Any separate folding/evaluation step needs an authorized, schema-supported call.
