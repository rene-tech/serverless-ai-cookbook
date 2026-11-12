---
name: runai-rfdiffusion
description: Run reviewed RFdiffusion backbone, motif and partial-diffusion workflows on the managed Scientific AI Run:ai service. Use for receptor-conditioned binder design, hotspots, qualified checkpoint families, symmetry, inpainting and supported guiding controls.
license: Apache-2.0
---

# rfdiffusion on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `rfdiffusion`. Documented scientific version: `1.1.0+symmetry.8810bf28`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Archive `target.pdb` and `settings.json` at the root. They stage below
`data/inputs/`. Required scaffold/motif scientific files must also be present
under that input tree. Inspect real chain/residue identifiers before defining
contigs or hotspots; do not silently renumber, crop or substitute targets.

## Choose the scientific workflow

Select `operation`: `design-backbone`, `scaffold-motif` or `partial-diffusion`.
Preserve native significant whitespace in a **single** contig string. A receptor
plus separate binder can use syntax such as `"A1-47/0 100-100"` only when those
receptor residues exist in the supplied target. Splitting that into separate
array entries or removing its space changes the scientific meaning.

Hotspots use chain/residue strings such as `A20` and must map to the receptor.
Choose `checkpoint_family` (`auto`, `ActiveSite`, `Complex_beta`) for the actual
task; a PPI-specialized checkpoint is not silently interchangeable with another.
Partial diffusion needs its compatible timestep and input mapping. Symmetry,
guiding potentials, noise, inpainting and scaffold controls must remain mutually
compatible; read the complete live schema instead of guessing Hydra strings.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### backbone-and-motif

MCP tool: `rfdiffusion_backbone_and_motif`. Execution: GPU.

```json
{"model":"rfdiffusion","workflow":"backbone-and-motif","version":"1.1.0+symmetry.8810bf28","parameters":{}}
```

## Interpret and retain results

Independently read designed structures and metadata. Confirm retained receptor,
new binder/motif mapping, requested lengths, hotspot conditioning, constraints
and actual design count. A target-only PDB is not binder design. Downstream
sequence design/refolding is a separate qualified workflow; a backbone does not
prove binding.

Recovery preserves completed native design units; an unfinished denoising unit
may recompute. Do not promise restoration of mid-denoising GPU/RNG state.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
