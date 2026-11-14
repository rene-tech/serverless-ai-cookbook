---
name: runai-boltz2
description: Predict biomolecular structures and protein–ligand affinity with Boltz 2.2.1 on the managed Scientific AI Run:ai service, using owner-bucket inputs, supplied alignments, native constraints and complete scientific outputs.
license: Apache-2.0
---

# Boltz2 on Scientific AI Run:ai

Read [the scientific gateway](../runai-scientific-gateway/SKILL.md) and its
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model `boltz2`, workflow `predict`, typed MCP tool `boltz2_predict`, scientific
version `2.2.1`. Discover the authorized live model schema before submission;
availability and the usage guide do not establish production qualification or
commercial clearance. This is the managed scientific API, not Run:ai administration.

## predict

Anchor: <a id="predict"></a>

Submit an owner-bucket `input.tar.gz` reference with exact
`name/key/sha256/size_bytes`. Its media type is `application/gzip`; members have
relative archive-root names and stage below `data/inputs/`. Include
`prediction.yaml` and `settings.json` containing a JSON object, plus every supplied
MSA/template file. YAML media types are `text/yaml` or `application/yaml`; settings
use `application/json`. MSA A3M is alignment text; paired CSV must follow the
live file contract. Do not use the old platform's scientific artifact manifest.

`parameters.input` defaults to `data/inputs/prediction.yaml`; it may select a
native YAML/FASTA file or directory of distinctly named predictions. MSA/template
paths resolve relative to that prediction document, including its subdirectory.
Use owner-relative paths, never URLs, operator paths or cloud credentials.
Alternatively supply typed `parameters.prediction` and omit the prediction file;
its referenced files resolve at the archive root. Explicit parameters override
the same controls in settings. Discover `input_contract.file_schemas` for exact
native content and cross-field rules; do not invent missing fields.

## Portable known-structure example

In a fresh caller-owned directory, run the bundled Python 3 helper. It downloads
SHA-256-pinned public alignment/licence/reference data, prepares a 76-residue
ubiquitin input, and writes `request.json`. The alignment has 1,066 supplied
sequences; no sequence is sent to an online MSA service. Reference coordinates
stay outside the archive and are used only for independent evaluation.

```sh
: "${SCIENTIFIC_AI_URL:?Set the approved scientific API base}"
: "${SCIENTIFIC_AI_TOKEN:?Load your token securely}"
: "${INPUT_KEY:?Choose a new object key in your bound bucket}"
: "${SCIENTIFIC_AI_SKILLS_DIR:?Set the directory containing your installed runai-boltz2 skill}"
SKILL_DIR=$(cd "$SCIENTIFIC_AI_SKILLS_DIR/runai-boltz2" && pwd)
PREPARED=boltz2-example
python3 "$SKILL_DIR/fixture.py" --key "$INPUT_KEY" --output "$PREPARED"
aws s3 cp "$PREPARED/input.tar.gz" "s3://$SCIENTIFIC_DATA_BUCKET/$INPUT_KEY" \
  --endpoint-url "$SCIENTIFIC_DATA_ENDPOINT" --region "$SCIENTIFIC_DATA_REGION"
cd "$PREPARED"
```

Use the gateway's submit-once, saved idempotency key, polling and verified
artifact-download procedure with this `request.json`. The example requests an
authorized EU-North1 H100 and supported optional kernels explicitly; check these
are permitted by your live grant. A missing region/GPU grant is an error, not
permission to change placement or science silently. `no_kernels:true` selects
the portable alternative; treat it as a different performance configuration.

For MCP use the same `version`, `region`, `gpu`, `pvc_gib`, `parameters` and
`inputs` from `request.json`, plus your saved `idempotency_key`. Omit REST's
`model` and `workflow`. Poll `md_run_status`, then `md_run_artifacts`, with the
returned public `run_id`. Both submission and all later reads use your own
identity. API acknowledgement and CPU validation are not completed GPU inference.

After downloading verified output paths beneath a caller-selected result
directory, run the bundled checker in an environment with NumPy and Gemmi:

```sh
python3 "$SKILL_DIR/check_result.py" --outputs ./results \
  --reference ./reference-1UBQ.cif
```

The checker tests residue identity/backbone geometry, full and core CA RMSD,
CA-lDDT and confidence against a known experimental structure. These control
thresholds do not establish accuracy on unseen targets or experimental binding.
OpenProteinSet alignment attribution and its CC BY 4.0 licence travel in the
input archive; the wwPDB reference is CC0. Preserve these notices.

## Native scientific controls

The same typed controls are available through REST and MCP. Consult the live
schema for complete combinations, exact bounds and currently supported values.

| Capability | Controls and interpretation |
|---|---|
| Entities | `prediction.sequences` supports protein, DNA, RNA and SMILES/CCD ligands; unique IDs can describe repeated copies. Proteins require explicit supplied `msa` or `msa: empty`. |
| Chemistry | Native modifications, cyclic polymers and atom-specific bond constraints use the documented CCD/residue/atom identifiers. Supply all referenced chemistry as permitted by the live schema. |
| Alignments | Owner A3M/paired CSV, `max_msa_seqs`, `subsample_msa`, `num_subsampled_msa`. Query sequence/entity mapping must agree. There is no implicit online MSA. |
| Conditioning | Native `constraints` includes bond, contact and pocket controls; templates use exactly one `pdb`/`cif` field plus chain/template mappings and optional force/threshold. `use_potentials` controls supported steering. |
| Sampling | `recycling_steps`, `sampling_steps`, `diffusion_samples`, `max_parallel_samples`, `step_scale`, `seed` and experimental `method`. Omitted values preserve the pinned native defaults; do not shorten a customer's requested science. |
| Outputs | `output_format` selects `mmcif` or `pdb`; `write_full_pae`, `write_full_pde`, `write_embeddings` request additional native arrays. |
| Affinity | `prediction.properties` selects the ligand binder; `affinity_mw_correction`, `sampling_steps_affinity`, `diffusion_samples_affinity` control its native prediction. One single-copy small molecule against a protein target is required; the native maximum is 128 ligand atoms, with a training-domain warning above 56. |
| Kernels | `no_kernels` selects the supported runtime implementation; native mixed BF16 inference remains the scientific precision. Availability is GPU/runtime-specific. |

Native defaults include three recycles, 200 diffusion steps, one structure
sample, at most five parallel samples and mmCIF output. Omitted/null `step_scale`
preserves 1.5; omitted/null seed remains unseeded. Affinity defaults to five
diffusion samples, independently of structure sampling. Record actual selected
controls/version alongside every result. A seed does not promise cross-GPU
bitwise identity.

## Results, lifecycle and limitations

Inspect `data/outputs/boltz2/science.json` and the indexed native prediction files.
Each target/sample needs coordinates and its confidence fields; optional requested
arrays/affinity must actually exist. Coordinate/PAE/PDE units are Angstroms.
Native confidence scores such as pLDDT/pTM/ipTM range from zero to one;
`affinity_pred_value` is log10(IC50 in micromolar), and
`affinity_probability_binary` is a predicted binder probability. These are
different outputs, neither a measured clinical result nor binding validation.
Retain structures, requested arrays, complete settings and public tool provenance
in your own bucket. Do not load unknown pickle artifacts to inspect results.

This workflow uses private per-run execution storage, with complete outputs and
checkpoint units synchronized to the authorized owner bucket. Native Boltz has
no in-flight diffusion-state continuation: interrupted inference can require
recomputation. Pretrained model weights are not execution checkpoints. Use only
the gateway's authorized resume operation and report partial results honestly.
The original server deadline persists across attempts; this workflow's native
command budget is exposed by its live contract. Cancelling/stopping removes
temporary scratch after at most five minutes of final-upload retries; an
unexported tail can be lost. Shared queue limits do not guarantee instant GPUs.

An error must be read from terminal REST/MCP status with the saved run ID; never
start duplicate computations merely because a client disconnected. For other
input datasets, validate every target and sample, preserve requested settings,
and distinguish computational success from a scientifically useful prediction.
The guide grants no access to another user's bucket or model licence.
