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

Archive `target.pdb` and `settings.json` at its root; they stage as
`data/inputs/target.pdb` and `data/inputs/settings.json`. Include referenced FASTA
or JSONL data files in the same archive and use the published logical input paths
for fields such as `path_to_fasta`, `fixed_positions_jsonl` or `pssm_jsonl`.
All chain/residue and sequence mappings must match the actual supplied backbone.

## Choose the scientific workflow

Select qualified `model_name`, `ca_only` and `use_soluble_model` combinations
from the live schema. CA-only/soluble combinations are not universally available.
Use `num_seq_per_target`, `batch_size`, `sampling_temp`, seed and amino-acid
omissions deliberately. Do not turn requested scoring into sequence generation.

Fixed/tied positions, chain selection, residue biases, PSSM, score-only and
conditional/unconditional probability modes use the schema's typed controls and
their actual JSONL contracts. Supply ordinary scientific data, not Python code.

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

## Interpret and retain results

Verify FASTA sequences align to the selected chains and length, retain requested
fixed residues/ties and obey amino-acid restrictions. Check scores/probability
arrays for correct shapes and finite values. ProteinMPNN likelihood is not
experimental affinity or a folding validation.

These short stateless native commands can repeat an unfinished unit. An
input-boundary retry is not restored optimizer/RNG state. Use the same owned
run/idempotency key and retain completed outputs where the workflow supports it.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
