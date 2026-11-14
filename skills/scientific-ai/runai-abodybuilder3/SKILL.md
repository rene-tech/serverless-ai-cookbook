---
name: runai-abodybuilder3
description: Predict paired antibody variable-domain structures with the managed ABodyBuilder3 REST or MCP workflow, selecting native structure checkpoints and understanding confidence and optional ProtT5 features.
---

# ABodyBuilder3 antibody structure prediction

## Predict

Discover `abodybuilder3` using `GET /v1/models/abodybuilder3` or MCP
`md_models` with `{"model":"abodybuilder3","detail":true}`. Check the returned
scientific versions, input/output contract and your authorized placement. This
guide describes the pinned scientific snapshot **18e40580** and its three named
published checkpoints; availability and qualification come from the live catalog.

Read the shared [portable client](../runai-scientific-gateway/references/client.md)
for secure endpoint/token configuration, owner-bucket upload, submit-once,
polling, cancellation and verified artifact retrieval. No native Run:ai admin
access or LibreChat helper is required. Use your existing owner-bound bucket;
passing a bucket key or cloud credential in model parameters cannot change it.

The worked request explicitly selects `eu-north1` / `h100`. Substitute a placement
permitted by your account; a forbidden region is an authorization error. Omit
placement only when the live model has qualified automatic cost routing.

## Prepare and submit a paired example

Create a fresh private directory and the official publisher's paired example:

```sh
mkdir -p prepared-inputs
cat > prepared-inputs/sequences.fasta <<'FASTA'
>H
QVQLVQSGAEVKKPGSSVKVSCKASGGTFSSLAISWVRQAPGQGLEWMGGIIPIFGTANYAQKFQGRVTITADESTSTAYMELSSLRSEDTAVYYCARGGSVSGTLVDFDIWGQGTMVTVSS
>L
DIQMTQSPSTLSASVGDRVTITCRASQSISSWLAWYQQKPGKAPKLLIYKASSLESGVPSRFSGSGSGTEFTLTISSLQPDDFATYYCQQYNIYPITFGGGTKVEIK
FASTA
sha256sum prepared-inputs/sequences.fasta
tar -czf input.tar.gz -C prepared-inputs sequences.fasta
```

Expected FASTA SHA-256 is
`0003bf402b15fd8b0a33bf54478e5bd361b015631c290c7eb6f9b395b2ebab1d`.
The native example has H122/L107 residues. Source: the pinned Exscientia
ABodyBuilder3 example notebook and Kenlay et al. (2024), DOI
[10.5281/zenodo.11354577](https://zenodo.org/records/11354577); retain the publisher's
CC-BY-4.0 attribution. This finite software example is not a binding experiment.

Use the shared client's AWS CLI upload to a new key in your existing bound bucket,
and construct `input-reference.json` with `name`, `key`, `sha256`, `size_bytes`.
The outer archive contains `sequences.fasta` directly, without a `data/` wrapper
or nested archive. Then construct the request:

```sh
jq -n --slurpfile input input-reference.json '{
  model:"abodybuilder3",workflow:"predict",version:"18e40580",
  region:"eu-north1",gpu:"h100",inputs:[$input[0]],
  parameters:{input_file:"sequences.fasta",checkpoint:"plddt-loss",
    cpu_threads:4,include_unfixed_structure:true,include_intermediates:true}
}' > request.json
```

Submit `POST /v1/runs` exactly as in the shared client, preserving the request and
idempotency key. For MCP use **`abodybuilder3_predict`** with the same
`parameters`, `inputs`, `version`, `region`, `gpu`, `idempotency_key`; omit REST's
`model` and `workflow`. Poll `md_run_status`, then `md_run_artifacts`. A submission
acknowledgement is not a completed or scientifically correct prediction.

## Native controls and input files

| Field | Meaning |
|---|---|
| `input_file` | Archive-relative UTF-8 FASTA; default `sequences.fasta`. Exactly one nonempty H and one nonempty L record, first header tokens H/L. Canonical20amino acids; whitespace is ignored and lowercase normalized. |
| `checkpoint` | `base-loss`, `plddt-loss` (default), or `language-loss`; fixed qualified pretrained scientific variants, not execution-state checkpoints. |
| `cpu_threads` | Positive integer for the native runtime; default4. It does not reserve additional resources. |
| `embeddings_file` | Optional archive-relative safe NPY only with `language-loss`; see below. Omit it to generate native ProtT5 features automatically. |
| `include_unfixed_structure` | Defaultfalse; additionally return the indexed native PDB before PDBFixer processing. |
| `include_intermediates` | Defaultfalse; return safe numeric NPZ native block tensors with explicit axes, units, atom masks and sequence mappings. |

Inputs represent paired antibody variable domains. Native nanobody prediction is
a separate model. This workflow does not accept executable code, arbitrary Torch
pickle checkpoints, antigen conditioning or a model-weight filesystem path.
Training/fine-tuning is outside this inference contract, pending separate scope.

The `language-loss` variant generates both chains' native ProtT5 features when
`embeddings_file` is omitted. If using already prepared features, include e.g.
`embeddings.npy` in the same archive, select `checkpoint:"language-loss"` and
`embeddings_file:"embeddings.npy"`. Required NPY dtype is **float32**, shape
**[len(H)+len(L),1024]**, finite values, rows for the complete H chain followed by
the complete L chain, with no BOS/EOS rows. Expected source is
`Rostlab/prot_t5_xl_uniref50` revision
`973be27c52ee6474de9c945952a8008aeb2a1a73`. The service validates shape, finiteness
and file hash; it does not attest that caller-provided vectors came from that
model. Incorrectly derived features are scientifically different input.
Object arrays/pickle, missing files and incompatible options fail validation.

## Interpret the delivered files

Inspect the actual artifact inventory and verify each downloaded SHA-256 and
size. Native results are under `data/outputs/abodybuilder3/`:

- `result.json` indexes scientific outputs and records the selected scientific
  variant, source/checkpoint/input provenance, native settings and phase timings.
- `native/structure.pdb` is the existing native `output_to_pdb`/PDBFixer output,
  with H/L chain labels and contiguous **zero-based** model numbering: H starts0;
  L starts at len(H). It is not IMGT numbering. B-factors are zero; do not
  interpret them as uncertainty. Native-added hydrogen positions can vary even
  in unchanged repeated CPU runs. PDBFixer cleanup is not MD relaxation.
- `native/confidence.json` contains per-residue native **pLDDT** in H-then-L order
  for `plddt-loss` and `language-loss`. It is **null** for `base-loss`, which has
  no confidence head. pLDDT is neither affinity nor a calibrated Kd estimate.
- `native/structure_unfixed.pdb`, only when requested, follows the exact official
  evaluator's numbering: H1..len(H), L501..500+len(L). Native pLDDT fills its
  B-factors when available, otherwise zero. It precedes PDBFixer hydrogen and
  terminal-atom repair; its atom count can differ from the fixed PDB. Join the
  two representations by chain and sequence position, not equal residue IDs.

When `include_intermediates:true`, the indexed `native/intermediates.npz` and
`native/intermediates.json` provide all native numeric forward outputs. Read the
JSON sidecar before loading the NPZ with `numpy.load(path,allow_pickle=False)`:

- `frames`, `sidechain_frames`, `angles`, `unnormalized_angles`, `positions` and
  `states` follow eight native structure-module blocks, with a singleton batch
  axis, then H-then-L residues. This is **not** physical time or an MD trajectory.
- `single` is the final **128-dimensional** native state, not the1024-dimensional
  ProtT5 input feature matrix. `states[-1]` equals `single`.
- `plddt` in this NPZ is **50-bin raw confidence logits**, absent forbase-loss.
  Use `confidence.json` for the normalized per-residue0-100pLDDT scores.
- Final `atom37`, atom14/37 existence masks/mappings, `aatype`, `is_heavy` and
  native `residue_index` preserve scientific correspondence. Positions and
  translations are in angstrom; angles are native sin/cos pairs. Respect absent
  atoms and residue-specific torsion applicability; the sidecar specifies axes.

Check chain sequences, completeness, confidence and geometry for your intended
scientific use. Model completion does not establish binding, experimental
accuracy for a new target, or a simulation-ready structure. The paper's training
throughput/relaxation experiments are not an identical end-to-end serving
benchmark. Runtime phase timings include model loading/ProtT5 feature generation
and native forward/PDBFixer/output work as stated by the returned metadata.

## Lifecycle, concurrency and failures

Each request is a finite owner-isolated job: no model GPU remains allocated when
idle. Concurrent requests have separate temporary private working storage and
share the authorized compute pool/queue. Use the live owner's concurrency and
capacity limits, rather than creating extra identities or duplicate requests.

The native unit is one atomic antibody pair. An interrupted unfinished pair must
be recomputed with the same owner, scientific version/settings and original
deadline; it has no intra-forward checkpoint. Completed output reuse is not a
claim of resuming partial model computation. Inputs, scratch and results belong
to the owner. Shutdown retries final upload for at most five minutes, then deletes
scratch even if the bucket is unavailable; only verified bucket data survives.

Follow the shared client's owner-scoped status/artifacts/cancel/resume contract.
Correct structured422 field/rule errors before resubmitting; report terminal
runtime failures with the public run ID and sanitized error. A403 is not
permission to switch identities. On an uncertain response, preserve the same
request key and reconnect to the same run, rather than blindly starting another.
Keep credentials, signed URLs and scientific payloads out of shared logs/chat.

## Model terms

ABodyBuilder3 code is Apache-2.0; publisher structure checkpoints and example data
are CC-BY-4.0. ProtTrans pretrained model weights use **AFL-3.0**, distinct from
the MIT source code, with external-deployment, notice and recipient-assent
conditions. Model access follows the platform's verified entitlement and
[the publisher's terms](https://github.com/agemagician/ProtTrans#license).
This guide itself does not grant hosted-use clearance.
