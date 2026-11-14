---
name: runai-bioemu2
description: Predict molecular structures, sample conformational ensembles, propagate molecular states and generate model trajectories with managed BioEmu2 REST/MCP jobs and private owner-bucket inputs.
---

# BioEmu2

Discover `bioemu2` through `GET /v1/models/bioemu2` or MCP `md_models`
`{"model":"bioemu2","detail":true}`. Select a scientific version and GPU/region
qualified in your live authorized catalog. This guide describes
**BioEmu2 0.1.0rc0-f99e0d89** with its named `bioemu2-preview` checkpoint.
A catalog entry does not grant commercial rights or certify scientific validity.

Use the shared [portable client](../runai-scientific-gateway/references/client.md)
for endpoint/token configuration, existing bucket credentials, upload/reference,
submit-once, polling and verified artifact retrieval. Native Run:ai administrator
access and LibreChat are unnecessary. Read secrets from environment variables or
a secret store; never put them in model parameters or chat.

## Prepare a complete input archive

Take `usage_skill.download_url` from the live workflow discovery as
`MODEL_SKILL_URL`. Download [fixture.py](fixture.py),
[gcn4-initial.cif](gcn4-initial.cif) and
[provenance](FIXTURE-PROVENANCE.md) from that **same cookbook revision**:

```sh
python3 - <<'DOWNLOAD'
import os, urllib.parse, urllib.request
from pathlib import Path
base = os.environ['MODEL_SKILL_URL']
assert base.startswith('https://raw.githubusercontent.com/rene-tech/serverless-ai-cookbook/')
for name in ('fixture.py', 'gcn4-initial.cif', 'FIXTURE-PROVENANCE.md'):
    with urllib.request.urlopen(urllib.parse.urljoin(base, name), timeout=45) as response:
        data = response.read((2 << 20) + 1)
    assert len(data) <= 2 << 20
    with Path(name).open('xb') as output:
        output.write(data)
DOWNLOAD
python3 fixture.py --operation predict-structure --output input.tar.gz
```

The standard-library helper refuses overwrites and prints the archive SHA-256,
size, member names and matching parameters. Prediction uses sequence-only
ubiquitin; the other examples use a GCN4 dimer. The latter A3Ms are query-only,
not evolutionary sequence information. Regenerate the archive with the selected
operation, using a new output filename or a fresh directory.

Upload the tar.gz to a new key in your existing owner bucket. Construct the shared
client's `input-reference.json` with **name, key, sha256, size_bytes**; the name is
`input.tar.gz`. Archive members are relative to its root, without a `data/` wrapper
or nested archive. No legacy artifact manifest or semantic-type field is needed.

## Four worked workflows

These protein examples have completed technical REST/MCP tests at the stated
settings. Other native input variants and advanced features remain subject to
the qualification limits below.

Every workflow is an asynchronous finite job. This example explicitly selects
`eu-north1` / `h100`; substitute a qualified placement authorized for your account.
An unauthorized region is an error. Automatic cost routing uses only qualified
performance and price data; a missing benchmark is not evidence of compatibility.

### predict-structure

```sh
jq -n --slurpfile input input-reference.json '{
  model:"bioemu2",workflow:"predict-structure",version:"0.1.0rc0-f99e0d89",
  region:"eu-north1",gpu:"h100",inputs:[$input[0]],
  parameters:{num_samples:3,batch_size:1,seed:42,msa_mode:"single_sequence"}
}' > request.json
```

Submit `POST /v1/runs` with the shared client and a preserved idempotency key.
For MCP, call **`bioemu2_predict_structure`**, supplying the same `parameters`,
`inputs`, `version`, `region`, `gpu` and `idempotency_key`, omitting REST's `model`
and `workflow` fields.

For the other operations, run `fixture.py --operation WORKFLOW --output NEW.tar.gz`,
upload that archive and use its new input reference. Replace the REST workflow
and parameters with the following; the other submission fields remain explicit:

### sample-equilibrium

Use REST workflow `sample-equilibrium` or MCP `bioemu2_sample_equilibrium` with
`{"num_samples":2,"batch_size":1,"seed":42,"msa_mode":"provided"}`.

### propagate

Use REST workflow `propagate` or MCP `bioemu2_propagate` with
`{"num_samples":2,"batch_size":1,"seed":42,"msa_mode":"provided","lag_time_ns":1.0}`.

### simulate-trajectory

Use REST workflow `simulate-trajectory` or MCP `bioemu2_simulate_trajectory` with
`{"num_samples":2,"batch_size":1,"seed":42,"msa_mode":"provided","lag_time_ns":1.0,"trajectory_steps":2}`.

Poll the returned public run ID through REST or `md_run_status`. Use
`md_run_artifacts`/the artifacts route and the shared client to download or access
results in your own bucket, verifying size and SHA-256. Acceptance into a queue is
not completed inference or scientific success.

## Exact molecular staging

All operations accept native `system.yaml` defining entities and optional
contacts. For simple complete molecular inputs, `initial.cif` can define the
system instead. An explicit system is recommended for modified residues,
SMILES/InChI ligands, branched entities and additional bonds. Native proteins,
RNA, DNA, supported ligands, modifications and contact syntax retain their native
meanings; consult the pinned [system documentation](https://github.com/microsoft/bioemu2/blob/f99e0d899a2548ee6d9d54b6854b2bc35b6652d5/docs/system.md)
and the live schema. Requested CCD components must exist in the fixed dictionary;
SMILES/InChI may be appropriate for a component without a supported CCD entry.

With `msa_mode:"provided"`, include `msa/CHAIN.a3m` for every protein chain.
If paired alignments are supplied, include `paired-msa/CHAIN.a3m` for every protein
chain. `single_sequence` explicitly uses query-only alignments. There is no
external sequence search or upload to a public MSA service. Nonprotein systems
use an empty MSA.

`propagate` and `simulate-trajectory` also require `initial.cif` containing every
system atom. An optional `initial.xtc` must already use the exact native atom
ordering of that CIF and contain `num_samples` frames. Without XTC, the CIF's one
frame is replicated `num_samples` times. A CIF from a previous compatible output
can be used, but an incomplete experimental structure is not automatically repaired.

Files must be regular, owner-contained archive members, without links, duplicate
paths, traversal or collisions. The molecular envelope is 8192 members and 256MiB
expanded input. A bucket key is not a path inside the archive. Arbitrary Python,
Hydra constructors and caller Torch checkpoints are outside this managed model.

## Controls, outputs and interpretation

The live detailed schema is authoritative. The twelve existing controls are
`num_samples`, `batch_size`, `seed`, `num_steps`, `sampler`, `precision`,
`matmul_precision`, `compile_denoiser`, `physicality_filter`, `msa_mode`,
`lag_time_ns` and `trajectory_steps`. `lag_time_ns` affects propagation/trajectory;
`trajectory_steps` affects only the ordered trajectory workflow.

- A null `num_steps` preserves the pinned presets' native default of 200 steps.
  Explicit values must be at least two. Reducing steps changes the calculation.
- `batch_size` changes exact samples and the resampling population for `edm_fk`
  and `edm_fkc`. `simulate-trajectory` accepts `edm` or `edm_gd`, without resampling.
- `precision` is `bf16-mixed` or `32-true` for the trunk; denoising remains float32.
  `matmul_precision` controls native TF32 policy. Compilation has startup cost.
- The lag is in **nanoseconds**; the model mainly trained on 1–1000ns.
  These are learned dynamics, not a calibrated classical force-field simulation.

Read the returned inventory and `data/outputs/bioemu2/result.json`. Native results
include `results/trajectory-NNNN/topology.cif`, `samples.xtc`, `physicality.json`
and the original `system.yaml`. CIF coordinates are in angstroms; XTC/MDTraj
coordinates are in nanometers and frame times are in picoseconds. All frames
remain present. Physicality records say `passed`, `rejected` or `not_checked`;
pure RNA/DNA or `physicality_filter:"no_filter"` do not constitute a protein
physicality pass.

`predict-structure` returns predicted conformations. `sample-equilibrium` returns
independent ensemble samples, **not** a time series. `propagate` returns one
conditioned endpoint per starting frame in the same order. `simulate-trajectory`
includes each initial frame and ordered endpoints. Its published managed seed
policy is `seed + step`, which differs from native whole-rollout single-seed RNG
semantics. Predictions are hypotheses, not experimental measurements, binding
proof or calibrated free energies; inspect quality and rejected frames.

## Ownership, recovery and errors

Each request uses private temporary scratch and its authenticated owner's bucket.
Inputs, intermediate coordinates, checkpoints and outputs are owner data.
Completed native sampling batches use lossless float32 angstrom `.npy` plus native
completion markers; trajectory steps preserve lossless float32 nanometer arrays
and exact topology, rather than resuming from quantized CIF/XTC alone. Completed
closed units can be reused; unfinished work may be recomputed. Within-call
propagation checkpointing and cross-region recovery qualification remain open
unless the live catalog explicitly marks them qualified.

On completion, cancellation, timeout or failure, writers stop and final uploads
retry for at most300seconds. Scratch is then deleted, including during a bucket
outage; unsynced tail data can be lost. Recovery uses only a verified checkpoint
in your bucket and preserves the original deadline. Do not blindly resubmit an
ambiguously accepted request or replace its idempotency key.

An invalid archive, missing `msa/A.a3m` or malformed molecular input produces a
structured error with a field/rule, cause and next action. A model-produced frame
that fails physicality is a scientific result, not a claim that every generated
conformation is usable. Preserve the public run ID for runtime failures.

Advanced native potential/schedule controls, explicit embeddings import/reuse,
nullable seed/batch/matmul controls and context-parallel execution remain separate
qualification gates. Their absence is not permission to submit arbitrary code or
guess unpublished fields. Training/fine-tuning is outside this inference guide.
