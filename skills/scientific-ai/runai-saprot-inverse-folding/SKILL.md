---
name: runai-saprot-inverse-folding
description: Generate amino-acid sequences from structure-aware tokens or PDB/mmCIF using managed SaProt inverse folding through REST and typed MCP.
---

# SaProt inverse folding

Discover `GET /v1/models/saprot-inverse-folding` or MCP `md_models` with
`{"model":"saprot-inverse-folding","detail":true}`. Select the named version
`saprot650m-if-ba725f3e` and a region/GPU permitted by your account. The live
catalog controls availability and qualification; this guide does not establish
commercial hosting or clinical clearance.

Use the [shared portable client](../runai-scientific-gateway/references/client.md)
for environment-based authentication, bucket upload, submission, polling and
checksum-verified result retrieval. Download [fixture.py](fixture.py) from the
**same public cookbook commit** as this guide. Downloads are unauthenticated;
never send your scientific bearer token to GitHub or a fixture website.

```sh
export INPUT_KEY=work/your-campaign/saprot-inverse-input.tar.gz
python3 fixture.py --key "$INPUT_KEY" --output prepared
```

Upload `prepared/input.tar.gz` unchanged to your bound bucket using that client.
Discover the workflow example into `request.json`, then replace its input and
parameters with the generated files:

```sh
jq --slurpfile input prepared/input-reference.json \
   --slurpfile parameters prepared/parameters.json \
   '.inputs=[$input[0]] | .parameters=$parameters[0] |
    .version="saprot650m-if-ba725f3e" | .region="eu-north1" | .gpu="h100"' \
   request.json > request-with-input.json
mv request-with-input.json request.json
```

Use a new request directory and saved idempotency key for every new operation.
After an uncertain response, recover the original run/key; do not submit twice.

## Inverse fold

REST uses `model:"saprot-inverse-folding", workflow:"inverse-fold"`.
The typed MCP tool is **`saprot-inverse-folding_inverse_fold`**. Pass `inputs`,
`parameters`, `version`, `region`, `gpu` and `idempotency_key`; omit REST's
`model` and `workflow`. Poll `md_run_status`, retrieve `md_run_artifacts`, and
verify complete delivered file hashes and sizes.

The input is one gzip tar named `input.tar.gz`, containing flat UTF-8
`sequences.fasta`. `fasta_file` can select another archive-relative member.
FASTA IDs must be unique. Tokens alternate an uppercase canonical amino acid
or `#` with a lowercase Foldseek 3Di state or `#`. For example
`##Ev#pQp##Vy#dYa#v` has nine residues and masks amino-acid positions1,3,5,7,9.
The second character describes structure: it is not a secondary-structure label.
The 3Di alphabet is `acdefghiklmnpqrstvwy`; `#` denotes unknown structure.
The first-character `#` requests an amino-acid prediction. Amino-acid-only mode
is unsupported by this inverse-folding interface.

Alternatively include a PDB/mmCIF and set `structure_file` to its relative path.
This overrides FASTA. Native Foldseek derives the tokens. `chains:["A"]`
selects exact author chain IDs, including multi-character IDs. Whitespace inside
protein chain IDs is currently rejected before compute. Derived record IDs are
the selected chains. `plddt_mask:"auto"` detects AlphaFold metadata; experimental
B factors are not automatically treated as confidence. Explicit `true`/`false`
and `plddt_threshold`0–100 are available; default threshold70.

`mask_positions` is an optional list of one-based sequence positions applied
to **every** input record. These are not PDB residue numbers/insertion codes.
With no explicit list, FASTA preserves its existing amino-acid masks, while a
structure input masks every derived amino acid. Known unmasked residues remain
fixed. A fully known FASTA is a legitimate native no-op, rather than a request
to redesign every residue.

Defaults are `sampling_method:"argmax"`, `num_samples:1`, `seed:null`,
`precision:"float32"`, `cpu_threads:4`. For stochastic designs set
`sampling_method:"multinomial", num_samples:3, seed:17`. Argmax requires exactly
one sample. Seeds range0–18446744073709551615; omission is nondeterministic for
sampling. The native algorithm samples the full446-token distribution at all
sequence positions, then replaces only masked amino acids. Argmax selects the
largest full token. This is simultaneous prediction, not autoregressive design
or an amino-acid-marginal softmax; temperature and top-k are not native controls.
FP16/BF16 require their own live qualification; execution alone is not accuracy
clearance. The checkpoint has33 blocks,20 heads and1,280 hidden features.

Results appear under `data/outputs/saprot-inverse-folding/`.
`native/sequences.csv` has exact columns **`id,sample,sequence`**, in original
record order followed by zero-based sample index. `(id,sample)` identifies a
row; the same ID across multiple samples is expected. The two fixture records
contain9/8 residues. `result.json` records the scientific settings and unresolved
amino-acid count. Native `#` predictions may remain unresolved; do not conceal
them or treat them as complete amino acids. A native special/non-residue token
produces an execution error, without silent filtering or resampling.
Structure inputs also deliver the actual `structure-sequences.fasta`.

This predicts sequences conditioned on structure tokens. It does not produce
new coordinates, prove experimental function/binding, or estimate affinity/Kd.

## Storage and continuation

Model compute returns to zero when idle. Input, temporary data, generator state,
checkpoints and results stay in your authorized bucket and a private temporary
job volume. Final upload retries last at most300seconds; scratch is then removed
even if an unsynced tail is lost. Resume uses only a verified bucket checkpoint.

Completed internal32-record units retain original IDs/order, native settings and
Torch generator state. This is not a32-record eligibility cap. Restore happens
after model loading and before the next sampling unit; unfinished work recomputes.
Use only a live-qualified source/target pair with the original owner, settings and
deadline. There is no mid-forward continuation, fixed five-minute recovery-point
promise, or bitwise sampling guarantee across different GPU architectures.

Correct structured field/rule errors using the schema. A forbidden region or
foreign run returns an authorization error. Arbitrary code, caller checkpoints,
training/fine-tuning and unqualified model variants are outside this interface.

Source and the fixed checkpoint declare MIT:
[pinned source](https://github.com/westlake-repl/SaProt/tree/e91e4858b55944523f1f8d385f7b96a0d3d34c1d),
[pinned model card](https://huggingface.co/westlake-repl/SaProt_650M_AF2_inverse_folding/tree/ba725f3e95436505db599bfa9efe3913916af34a).
Structure conversion uses GPLv3 Foldseek; retain the accompanying notices.
