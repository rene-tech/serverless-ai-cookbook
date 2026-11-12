---
name: proteinmpnn
description: Design research protein sequences for an inline PDB backbone with the proteinmpnn native model.
license: Apache-2.0 AND CC-BY-4.0
---

# proteinmpnn (native)

Public model ID `proteinmpnn`; typed tool `infer_proteinmpnn_native` on the
`scientific-ai-apps` MCP server (LibreChat suffixes tool IDs). Shared lifecycle
rules: `scientific-gateway`. Call `get_model_schema` when unsure — its live
schema and example win over this skill.

## Payload contract

Allowed fields only:

- `input_pdb`: 40 B–2 MB UTF-8 PDB text containing `ATOM` records; populate
  from the real file outside chat, or use the artifact variant if advertised.
- `input_pdb_chains`: optional list of 1–16 one-character chain IDs to design.
- `num_seq_per_target`: positive integer (default 1), subject to the live
  schema. Internal bounded batches are not a request-count cap; larger counts
  increase runtime and output size within the execution deadline.
- `sampling_temp`: finite number or single-element list in 0.01–1;
  `0.1` and `[0.1]` are both valid (default 0.1; lower is more conservative).
- `random_seed` 1–2^31-1 (default 1).
- `omit_AAs`: optional amino acids to exclude from design.

The schema example is [examples/request.json](examples/request.json).
It includes structure bytes and is a file-client input, **not** text to load
into chat. Use it directly outside model context, or construct a new local JSON
from the customer's actual structure. Keep the original input and hash. Never
substitute this teaching fixture for the customer's dataset.

## Result

Designed sequences per requested chain with per-position log-probabilities.
Sequences are research suggestions; validation by structure prediction
(`openfold2`/`boltz2`) can supply further research evidence before synthesis.
Installing this skill does not establish exact-runtime readiness or validation.
One ordinary typed-MCP request with an inline 20-residue PDB, scalar temperature
`0.1` and 100 requested sequences passed on L40S in eu-north1. All 100 sample
labels, probability normalization, REST/MCP results and owner-bucket export
hashes were verified. This does not qualify every sequence length, concurrent
capacity or the artifact-upload variant.
