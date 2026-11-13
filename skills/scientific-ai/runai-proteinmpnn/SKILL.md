---
name: runai-proteinmpnn
description: Design or score protein sequences with the reviewed ProteinMPNN workflow on the managed Scientific AI Run:ai service. Use for backbone-conditioned sequences, qualified weight families, fixed/tied positions, bias/PSSM controls and probability outputs.
license: Apache-2.0
---

# proteinmpnn on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `proteinmpnn`. Documented scientific version: `source-8907e6671bfb`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Archive `target.pdb` and `settings.json` at the root of `input.tar.gz`; they stage
as `data/inputs/target.pdb` and `data/inputs/settings.json`. Alternatively include a
parsed JSONL dataset, set `jsonl_path: data/inputs/targets.jsonl` and omit the unused
PDB. Include every referenced FASTA/JSONL file in the same archive. Submit its exact
`name/key/sha256/size_bytes` reference through `inputs`, following the gateway.
All target names, chains and sequences must agree with the supplied backbone.
The archive media type is `application/gzip`; JSONL is `application/x-ndjson`,
FASTA is `text/x-fasta`, and PDB is `chemical/x-pdb`. Coordinates are Angstroms; full-backbone models use N/CA/C/O, CA-only uses CA.
Read live `input_contract.file_schemas` for full schemas; do not guess missing roles.

| File parameter | Native content |
|---|---|
| `jsonl_path` | One parsed target per line: unique `name`, concatenated `seq`, `num_of_chains`, `seq_chain_ID`, matching `coords_chain_ID` atom arrays. |
| `chain_id_jsonl` | `{"target":[["A"],["B"]]}` designs A, retains B. PDB inputs use `pdb_path_chains`, e.g. `"A B"`. |
| `fixed_positions_jsonl` | `{"target":{"A":[1,2,3]}}`. |
| `tied_positions_jsonl` | `{"target":[{"A":[4,5]}]}`; weighted groups use `[positions,weights]`. |
| `omit_AA_jsonl` | `{"target":{"A":[[[4,5],"C"]]}}` excludes C at free positions 4 and 5. |
| `bias_AA_jsonl` | Finite amino-acid biases, e.g. `{"A":0.5,"C":-1}`. |
| `bias_by_res_jsonl` | Target → chain → chain-length-by-21 finite matrix. |
| `pssm_jsonl` | Target → chain → chain-length `pssm_coef`, plus length-by-21 `pssm_bias` and `pssm_log_odds`. |
| `path_to_fasta` | One or more FASTA records; requires `score_only:true`. |

Positions are one-based **within each chain**, not original PDB residue numbers.
Matrix alphabet is `ACDEFGHIKLMNPQRSTVWYX`. Bias/PSSM controls are soft preferences;
fixed positions, omissions and ties constrain free generated positions. Ordinary
control JSONL readers use their last complete mapping; target-dataset rows are
separate records and PSSM objects merge.

## Choose the scientific workflow

Vanilla and soluble families support `v_48_002`, `v_48_010`, `v_48_020`, `v_48_030`;
CA-only supports the first three and cannot be combined with soluble. Select the
qualified combination from the live schema. Managed defaults are vanilla
`v_48_020`, seed 42, one sequence and temperature 0.1. Seed zero selects native
random seeding. Preserve the selected version, weights and scientific precision.

`num_seq_per_target` must be divisible by `batch_size`; generation produces that many
sequences per temperature and target. Temperatures are finite positive values
separated by ordinary whitespace. `backbone_noise` is coordinate-noise standard
deviation in Angstroms; `omit_AAs` sets global omissions. `max_length` must cover
all targets: silently dropping targets is not success. Use `save_score` and
`save_probs` deliberately; `suppress_print` controls native verbosity.

Fixed/tied positions, chain selection, residue biases, PSSM, score-only and
conditional/unconditional probability modes use the schema's typed controls and
their actual JSONL contracts. Supply ordinary scientific data, not Python code.
PSSM mixture, threshold, bias and log-odds flags require the matching PSSM file.

| Purpose | Parameters | Outputs below `data/outputs/proteinmpnn/` |
|---|---|---|
| Generation | All scoring flags false | `seqs/TARGET.fa`; requested `scores/` and `probs/` NPZs |
| Native sequence and optional FASTA scoring | `score_only:true` | `score_only/TARGET_pdb.npz` plus `TARGET_fasta_N.npz` per FASTA record |
| Conditional probabilities | `conditional_probs_only:true` | `conditional_probs_only/TARGET.npz` |
| Backbone-only conditional probabilities | Also `conditional_probs_only_backbone:true` | The conditional directory |
| Unconditional probabilities in one forward pass | `unconditional_probs_only:true` | `unconditional_probs_only/TARGET.npz` |

Select at most one of `score_only`, `conditional_probs_only` and
`unconditional_probs_only`. Backbone-only conditional mode requires conditional
mode. Native FASTA scoring removes `/` and replaces the prefix in sorted designed-,
then fixed-chain order. A shorter record retains remaining native residues; it
requests scoring, not redesign. Do not silently reorder chains.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### sequence-design

MCP tool: `proteinmpnn_sequence_design`. Execution: GPU.

```json
{"model":"proteinmpnn","workflow":"sequence-design","version":"source-8907e6671bfb","parameters":{}}
```

For an uploaded archive with `settings.json`, `target.pdb` and `score.fasta`,
replace `parameters` with the following and add the archive's `inputs` reference.
Every FASTA record is scored in addition to the native backbone sequence.

```json
{"score_only":true,"path_to_fasta":"data/inputs/score.fasta","num_seq_per_target":2,"batch_size":2,"seed":42,"model_name":"v_48_020"}
```

For MCP, call `proteinmpnn_sequence_design` with `version`, `parameters`, `inputs`
and the saved `idempotency_key`, omitting REST `model/workflow`. A native CPU
validation attempt precedes GPU allocation; queued/validating is not completed
GPU work. Poll `md_run_status`, then `md_run_artifacts`, with the public `run_id`.

## Constrained multichain example

Use the public [1BRS structure](https://www.rcsb.org/structure/1BRS), whose PDB
coordinates are [CC0](https://www.wwpdb.org/about/usage-policies); cite Buckle,
Schreiber and Fersht (1994), doi:10.1021/bi00196a004. This example retains target
chain C and redesigns contacting partner F. The actual supplied C has 108 residues
(PDB 3–110), F has 89 (PDB 1–89); do not substitute deposited full-sequence lengths.
Prepare these public scientific files in a new caller-owned working directory:

```python
import gzip, hashlib, io, json, tarfile, urllib.request
from pathlib import Path

raw = urllib.request.urlopen('https://files.rcsb.org/download/1BRS.pdb', timeout=60).read()
assert hashlib.sha256(raw).hexdigest() == '0076aae54252706a8c8c02f7b1e71ce2394b0e928b413590b4ac12aade9e8f6c'
lines = [line for line in raw.decode().splitlines()
         if line.startswith(('ATOM  ', 'TER   ')) and line[21:22] in {'C', 'F'}]
Path('target.pdb').write_text('\n'.join(lines) + '\nEND\n')
Path('settings.json').write_text('{}\n')
controls = {
    'fixed.jsonl': {'target': {'F': [1, 2, 3]}},
    'tied.jsonl': {'target': [{'F': [10, 11]}]},
    'omit.jsonl': {'target': {'F': [[[20, 21, 22], 'C']]}},
}
for name, value in controls.items():
    Path(name).write_text(json.dumps(value, separators=(',', ':')) + '\n')
with Path('input.tar.gz').open('wb') as destination:
    with gzip.GzipFile(fileobj=destination, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name in ['target.pdb', 'settings.json', 'fixed.jsonl', 'tied.jsonl', 'omit.jsonl']:
                data = Path(name).read_bytes()
                member = tarfile.TarInfo(name)
                member.size, member.mode, member.mtime = len(data), 0o444, 0
                archive.addfile(member, io.BytesIO(data))
```

Upload this archive with the gateway procedure. Add its exact `inputs` reference
to the ordinary generation request, then use these `parameters`:

```json
{"pdb_path_chains":"F","num_seq_per_target":4,"batch_size":2,"sampling_temp":"0.1","seed":42,"model_name":"v_48_020","save_score":true,"save_probs":true,"fixed_positions_jsonl":"data/inputs/fixed.jsonl","tied_positions_jsonl":"data/inputs/tied.jsonl","omit_AA_jsonl":"data/inputs/omit.jsonl"}
```

After verified delivery, expect four 89-residue designs after the native FASTA
record. Only designed F is in this FASTA: check F1–3=KKA, F10=F11 and no C at
F20–22. Numerical `S` is `[4,197]`; `probs/log_probs` are `[4,197,21]` and
`chain_order` is `[2,2]`, both rows F,C. The first 89 tensor sites are F; the last 108
must decode to the unchanged target C. The loss/design mask is `[2,197]` with 85
active sites. F native position 89 (PDB 89) and C native position 108 (PDB 110) lack O
coordinates and are masked; do not invent
coordinates or require generation probabilities at inactive sites to normalize.
The masked F89 retains native S. These are native chain positions, not global
PDB residue numbers. Correct constraints do not establish experimental binding.

## Interpret and retain results

Verify FASTA sequences align to the selected chains and length, retain requested
fixed residues/ties and obey amino-acid restrictions. Check scores/probability
arrays for correct shapes and finite values, and check every target. Generation
FASTA starts with a native record before the requested designs. Conditional and
unconditional `log_p` arrays have shape `[samples,L,21]`; interpret native masks
and normalization of `exp(log_p)` over valid positions. Retain requested numerical
artifacts and `science.json`. For local NPZ inspection, install NumPy in the
caller's normal environment and use `numpy.load(..., allow_pickle=False)`.
Lower mean negative log likelihood indicates greater
model confidence, not measured affinity or independent folding validation.

The workflow exports a bootstrap and completed native-command units. ProteinMPNN
has no mid-command progress/RNG checkpoint: an unfinished command recomputes its
original input under the original two-week deadline. Do not promise incremental
campaign continuation; seed zero may produce different sequences on retry. Use
only the gateway's authorized compatible resume path. Temporary private volumes
are removed after stopping, with at most five minutes for final upload retries;
unsynced scratch is then lost. Shared pool/queue limits do not guarantee 32 GPUs
immediately available to one caller.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
