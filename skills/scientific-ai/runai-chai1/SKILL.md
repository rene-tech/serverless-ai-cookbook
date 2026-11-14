---
name: runai-chai1
description: Predict all-atom biomolecular structures with managed Chai-1, or convert local A3M alignments to native MSA Parquet, using Scientific AI REST and typed MCP.
---

# Chai-1

Discover `GET /v1/models/chai1` or MCP `md_models` with
`{"model":"chai1","detail":true}`. Select `chai1-0.6.1-c691da74`, a workflow
and an authorized region/GPU. The live catalog determines enabled features,
continuation pairs and readiness. This guide does not establish scientific,
commercial hosting or clinical clearance.

Use the [shared portable client](../runai-scientific-gateway/references/client.md)
for environment-based authentication, owner-bucket upload, submission, polling
and full checksum-verified result retrieval. Download [fixture.py](fixture.py)
and [provenance](FIXTURE-PROVENANCE.md) from the **same public cookbook commit**
as this guide. Downloads are unauthenticated: never send your scientific bearer
or storage credentials to GitHub or a structure website.

```sh
export INPUT_KEY=work/your-campaign/chai-predict-input.tar.gz
python3 fixture.py --workflow predict --key "$INPUT_KEY" --output prepared
```

Upload `prepared/input.tar.gz` unchanged to your already-bound bucket. Discover
`predict`'s live example into a fresh `request.json`, then replace its input and
parameters with the generated files:

```sh
jq --slurpfile input prepared/input-reference.json \
   --slurpfile parameters prepared/parameters.json \
   '.inputs=[$input[0]] | .parameters=$parameters[0] |
    .version="chai1-0.6.1-c691da74" | .region="eu-north1" | .gpu="h100"' \
   request.json > request-with-input.json
mv request-with-input.json request.json
```

Use a new request directory and saved idempotency key for every operation.
Recover the original run/key after an uncertain response; do not submit twice.
For typed MCP, omit REST's `model` and `workflow`, passing `inputs`, `parameters`,
`version`, `region`, `gpu` and `idempotency_key`. Poll `md_run_status`, retrieve
`md_run_artifacts`, and verify every delivered artifact's complete size/hash.

## Predict

REST uses `model:"chai1", workflow:"predict"`; typed MCP is **`chai1_predict`**.
One gzip tar named `input.tar.gz` contains archive-root `input.fasta` by default.
Set `fasta_file` to another relative member if needed. Members cannot be links,
absolute paths, traversal paths or executable customer code.

Native FASTA supports `>protein|name=...`, `>rna|name=...`, `>dna|name=...`,
`>ligand|name=...` with SMILES, and `>glycan|name=...` with native glycan syntax.
Parenthesized CCD modifications retain native semantics. Use unique ordered
entity names; input admission rejects an entity silently lost by tokenization.
The supplied example has one 76-residue ubiquitin protein and no template/MSA.
It passes only `seed:42`; scientific sampling defaults are fully retained.

The current native defaults are `num_trunk_recycles:3`, `num_diffn_timesteps:200`,
`num_diffn_samples:5`, `num_trunk_samples:1`, `recycle_msa_subsample:0`, `seed:null`,
`use_esm_embeddings:true`, `low_memory:true`, `cpu_threads:8`,
`fasta_names_as_cif_chains:false`. Named sampling controls are available through
the live typed schema; inspect model-specific bounds before large work.
There is no arbitrary precision override: native component dtypes, including
FP16 ESM embeddings, are preserved. A fixed seed applies to native folding with
`seed + original_trunk_index`; it does not promise bitwise reproducibility
across restarts, context construction, GPUs or software/hardware revisions.

By default, logical FASTA names are mapped to native CIF chains such as A/B.
`fasta_names_as_cif_chains:true` requests exact names as subchains; native names
must then fit four ASCII characters. Restraints must use the matching chain
namespace. Do not assume long FASTA names become valid CIF chain identifiers.

### Local alignments and templates

`msa_directory` selects a relative directory inside the archive containing
`SHA256(UPPERCASE_QUERY_SEQUENCE).aligned.pqt` per protein. Native Parquet has
exact columns `sequence`, `source_database`, `pairing_key`, `comment`; the first
row is the query. Lowercase insertions and native gap/deletion handling are
preserved. Matching nonempty pairing keys express proposed pairing; they do not
prove biological interaction. Unpaired rows are supported. Use the CPU
[MSA converter](#msa-convert) for A3M rather than guessing Parquet layout.

`template_hits_path` selects native 13-column Foldseek m8 hits. Put local template
CIFs at `template_cifs/IDENTIFIER.cif.gz` in the same input archive; identifiers
must match native hit names. The adapter stages those files into the private
job cache. Template parsing alone is not evidence of predictive accuracy.

`use_msa_server:false` and `use_templates_server:false` are defaults.
Enabling external searches can send sequences/data to a third-party service;
provider access, privacy, licensing and egress qualification must be explicitly
enabled by the live platform. An external MSA search conflicts with local
`msa_directory`; external templates require external MSA search and conflict
with local `template_hits_path`. Arbitrary server URLs are not accepted.

### Restraints

`constraint_path` selects a UTF-8 native CSV with exact columns:
`restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment`.
Use native `contact`, `pocket` or `covalent` grammar. Residue positions are
one-based, with native residue/atom references such as the documented
`C217@SG` covalent form. Required distance/confidence columns must parse as
floats. Admission verifies that requested contact/pocket records map to native
features rather than silently disappearing. Native confidence/minimum-distance
fields are parsed but are not applied by this version; maximum distance is not
an experimentally guaranteed restraint satisfaction. Inspect the exact source
examples before describing noncanonical/covalent chemistry.

### Results

`data/outputs/chai1/result.json` records the scientific version and settings.
`native/` contains every `pred.model_idx_N.cif` and `scores.model_idx_N.npz`;
multiple trunks use `native/trunk_T/` with original zero-based trunk indices.
Scalar NPZ confidence fields are one-element arrays. Ranking combines
`0.2*pTM + 0.8*ipTM - 100*interchain_clash`; monomer ipTM can be zero.

Float32 `native/pae.npy` and `pde.npy` have shape
`[trunks*samples,tokens,tokens]` and Angstrom units; `plddt.npy` has shape
`[trunks*samples,tokens]` and values 0–1. CIF B-factors use 100×pLDDT.
All requested conformers remain available, including low-confidence results.
These predictions/confidences do not establish binding affinity, Kd, experimental
function, chirality correctness or clinical suitability.

## MSA convert

Use only if live discovery lists `msa-convert`. REST uses
`model:"chai1", workflow:"msa-convert"`; MCP is **`chai1_msa_convert`**.
This is a CPU operation: select `gpu:"cpu"` and an authorized region.

```sh
export INPUT_KEY=work/your-campaign/chai-a3m-input.tar.gz
python3 fixture.py --workflow msa-convert --key "$INPUT_KEY" --output prepared-msa
```

Upload that archive and construct a **new** request/idempotency key from the
converter's own live example, using its generated input/parameters. Do not copy
prediction-only FASTA defaults or reuse a prediction request's idempotency key.
Parameters are `a3m_files:[{"path":"hits_uniref90.a3m","source_database":"uniref90"}]`
and `insert_keys_for_sources:"uniprot"`. Sources are exactly `bfd_uniclust`,
`mgnify`, `uniref90`, `uniprot`, `query`. Other enum names in upstream code are
not accepted by this version's Parquet schema. `query` is a native row label,
not an external search. All supplied files must share the same query; duplicate
paths or sources are rejected to prevent native mapping overwrite.

Pairing-key modes are `all`, `none`, `uniprot` (default). They use unchanged
native source-specific header parsing; they do not infer homology or pairing.
Output is `data/outputs/chai1/native/<querySHA>.aligned.pqt` plus `result.json`.
For a subsequent prediction, download the verified Parquet to your own storage,
include it in that prediction's input archive under the selected `msa_directory`,
and submit a separate new operation. No hidden shared scratch or cross-owner
file handle is required. This operation performs no neural inference/search.

## Storage, time limits and continuation

Both workflows have a two-week execution budget; the original absolute request
deadline also applies after continuation. Scientific compute returns to zero
when idle. Input, scratch, contexts, RNG state, checkpoints and results stay in
your authorized bucket and private temporary job volume. Final-upload retries
last at most 300 seconds; scratch is then removed even if an unsynced tail is
lost. Recovery uses only the last verified checkpoint already in your bucket.

Prediction checkpoints close one original trunk with all its diffusion samples.
An unfinished trunk recomputes. There is no mid-diffusion checkpoint or fixed
five-minute recovery-point guarantee. Only live-qualified continuation pairs
are usable, with the original owner, inputs, scientific settings and deadline.
Functional continuation does not establish scientific numerical equivalence;
if its qualification gate is experimental/open, it is not production clearance.
The converter is one bounded native CPU unit and can recompute if interrupted.

Correct structured input field/rule errors using the published schema. Foreign
run information and forbidden regions return authorization errors. Inspect your
own validation/execution logs and detailed error if native execution fails.
No customer Python, pickled checkpoints, arbitrary feature-context import,
training/fine-tuning or unqualified checkpoint is accepted by this interface.

Pinned Chai code and weights declare Apache-2.0; ESM2 uses MIT:
[Chai source and current license](https://github.com/chaidiscovery/chai-lab/tree/c691da74d6f348b19bc9f931abe95d66d0b88e78).
Dependency/service/license and security acceptance remain separate live gates.
