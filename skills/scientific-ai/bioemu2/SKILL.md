---
name: bioemu2
description: Predict biomolecular structures, sample conformational ensembles, or generate time-lagged structural rollouts with the hosted Microsoft BioEmu2 model. Use for BioEmu2, not classical force-field MD, sequence design or binding-affinity prediction.
license: CC-BY-4.0
---

# BioEmu2

Discover App `bioemu2` and read its live schema before using `submit_bioemu2`
on `scientific-ai-apps`. Skill installation is not an availability or permission
claim. Use the hosted GPU model, not a local installation on the chat VM.

Choose the scientific operation explicitly:

- `predict-structure`: folded-structure predictions, native sharpening.
- `sample-equilibrium`: independent conformations, **not successive time frames**.
- `propagate`: independent endpoints conditioned on starting structures and a lag.
- `simulate-trajectory`: repeated propagation, producing time-ordered rollouts.

The model supports protein complexes, ligands and nucleic acids through the
native system format. It does not generate protein sequences, predict affinity,
or replace force-field MD. Sampling frequencies are not calibrated Boltzmann
probabilities; do not infer quantitative free energies from them.

## Prepare the molecular input

Use a tar bundle containing `system.yaml` in the upstream BioEmu2 format
(`entities`, optional `bonds` and `contacts`). Preserve explicit bonds, modified
residues, atom/chain identities and contact conditions. Plain Boltz YAML is a
different format; convert and inspect warnings before submission.

For each protein chain, include `msa/CHAIN.a3m`; query sequences must match the
system. Optional paired alignments use `paired-msa/CHAIN.a3m` for every protein
chain. Alternatively explicitly request `msa_mode: single_sequence` and explain
the lack of evolutionary information. Never silently send customer sequences to
public ColabFold or fabricate alignments. The hosted default is `provided`.

For a public introductory input, copy [examples/system.yaml](examples/system.yaml)
and [examples/parameters.json](examples/parameters.json) into a new workspace
directory. The example explicitly uses query-only inference, not a fabricated
homolog alignment. Package with `tar -cf input.tar system.yaml` from that directory.

Propagation also requires `initial.cif` with all system atoms. A prior BioEmu2
`topology.cif` can be copied to that name. Optional `initial.xtc` supplies several
starting frames; its atom order must match the system and CIF. Do not repair
missing atoms by renaming files. A complete CIF with molecular metadata can
define the system when `system.yaml` is absent.

The original inputs remain unchanged. For an introductory run, ask for the
user's scientific goal and choose a small explicit sample count; retain native
denoising defaults. `num_samples` and `batch_size` are different: the latter
changes memory/throughput, not the requested number of conformations.
Reducing denoising steps or changing steering/precision changes scientific
settings and must not be an undisclosed workaround.

## Submit, observe and deliver

Use `scientific-gateway` for trusted file upload. The scientific manifest entry
is named `workload`, semantic type `bioemu2-workload-tar/v1`, media type
`application/x-tar`, compression `none`. Pass the finalized manifest,
`operation`, `service_class: customer-batch`, parameters and a stable idempotency
key directly to `submit_bioemu2`. Do not send raw CIF/XTC bytes in the tool call.

LibreChat's existing helper handles real workspace files:

```bash
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model bioemu2 --tool submit_bioemu2 --operation sample-equilibrium \
  --source /workspace/my-study/input.tar --entry-name workload \
  --semantic-type bioemu2-workload-tar/v1 --media-type application/x-tar \
  --compression none --parameters /workspace/my-study/parameters.json \
  --output /workspace/my-study/result --display-name 'BioEmu2 ensemble' \
  --idempotency-key YOUR_STABLE_REQUEST_KEY --service-class customer-batch \
  --wait-seconds 1 --poll-seconds 10
```

Paths are examples, not existing files. Observe the returned native `op-...` ID
with `get_operation` and `get_operation_result`. Queued admission or a lost
status response is not completion and not a reason to resubmit. Keep useful
errors and failed stages visible. Recovery/download observes the same ID.

Download and hash-verify the `result` JSON and `results` tar. Extract only safe
regular files into a fresh owned directory, and check every `files[]` hash.
Each trajectory directory contains `topology.cif`, `samples.xtc` and
`physicality.json`. Report rejected and unchecked frames honestly; the model
does not silently remove them. Protein physicality checks do not validate
ligand/nucleic-acid geometry or biological usefulness.

Render verified structures inline using the installed structure viewer's
`workspace_files` input, and include its returned UI marker verbatim. Use
trajectory rendering for time-ordered rollouts; don't present independent
equilibrium samples as a time evolution. Download links are secondary access,
not a substitute for a requested inline view.

Report measured frames/s and runtime, with queue/startup separate. A model lag
in ns is not classical-MD simulated time or interchangeable GROMACS ns/day.
Native steering presets are `edm`, `edm_gd`, `edm_fk`, `edm_fkc`; time-ordered
rollouts cannot use particle resampling (`edm_fk`/`edm_fkc`). Optional compilation
adds startup work and may help large repeated batches. Multi-GPU context
parallelism, custom Python potentials and GPU process snapshots are not implied
by this single-GPU contract; consult live advertised capabilities.

Upstream documentation: https://github.com/microsoft/bioemu2/tree/f99e0d899a2548ee6d9d54b6854b2bc35b6652d5/docs
