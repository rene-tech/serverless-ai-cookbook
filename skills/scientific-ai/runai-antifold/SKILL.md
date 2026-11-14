---
name: runai-antifold
description: Score antibody sequence compatibility, sample antibody regions and extract structural embeddings with the managed AntiFold inverse-fold workflow through Scientific AI REST or MCP.
---

# AntiFold inverse folding

## Inverse-fold

Discover `antifold` with `GET /v1/models/antifold` or MCP `md_models`
`{"model":"antifold","detail":true}`. Select a version from that response and use a placement permitted by your account. This skill describes scientific version **0.4.0** and the named
managed AntiFold checkpoint. Availability is determined by the live release;
the existence of this document does not grant access or establish qualification.

Read the shared [portable client](../runai-scientific-gateway/references/client.md)
for secure configuration, upload, one-time submission, polling, cancellation and
verified download. Use your existing bound bucket. Neither native Run:ai admin
access nor a LibreChat-specific helper is required. Do not guess missing metadata.

The reference requests below use **EU-North1 / H100**. Replace `region` and
`gpu` only with a placement permitted by your account; a forbidden placement
returns a permission error. Omit placement fields only when the live model
has qualified automatic routing. Checkpoint and data-copy regions remain
subject to your grant.

## Prepare a paired-antibody example

Create a fresh private client directory. Download this public, upstream IMGT
fixture **without** a Scientific AI bearer header and verify its exact bytes:

```sh
mkdir -p prepared-inputs
curl --fail-with-body --silent --show-error \
  https://raw.githubusercontent.com/oxpig/AntiFold/9918344067f34a6b026f2634fdba212fc3e6e986/data/pdbs/6y1l_imgt.pdb \
  --output prepared-inputs/target.pdb
printf '%s  prepared-inputs/target.pdb\n' \
  19513b0fee557e501229c4acd13d462a4ddf38212bc1e83fa6f1696f1c97f282 | sha256sum --check
tar -czf input.tar.gz -C prepared-inputs target.pdb
```

The fixture contains heavy H and light L chains. It is a finite software example,
not evidence that a designed sequence binds a target. Source: the pinned Oxford
Protein Informatics Group AntiFold example, with SAbDab IMGT numbering of PDB 6Y1L.
PDB archive data are [CC0](https://www.wwpdb.org/about/usage-policies);
SAbDab annotations are [CC-BY-4.0](https://opig.stats.ox.ac.uk/webapps/sabdab),
attributed to SAbDab/OPIG (Dunbar et al., 2014; Schneider et al., 2022).
Retain that attribution and the upstream BSD-3-Clause notice where applicable;
the example download changes only the local filename to `target.pdb`.

The seeded catalog example uses the same paired fixture under `paired.pdb`,
alongside the other published workflow fixtures. Use its returned filenames when
submitting that example; the custom-upload recipe here explicitly uses `target.pdb`.

Upload `input.tar.gz` into a new key in your bound bucket using the shared client.
Produce `input-reference.json` with `name`, `key`, `sha256` and compressed
`size_bytes`, exactly as shown there. There is **one** outer archive: its members
are `target.pdb`, not `data/inputs/target.pdb` or another nested archive.

Create the REST request after the upload reference exists:

```sh
jq -n --slurpfile input input-reference.json '{
  model:"antifold", workflow:"inverse-fold", version:"0.4.0",
  region:"eu-north1",gpu:"h100",
  inputs:[$input[0]],
  parameters:{pdb_file:"target.pdb",heavy_chain:"H",light_chain:"L",
    skip_anarcii_numbering:true,regions:"CDR1 CDR2 CDR3",
    num_seq_per_target:2,sampling_temp:"0.10 0.30",
    extract_embeddings:true,num_threads:2,batch_size:1,seed:42}
}' > request.json
```

Follow the shared client's `POST /v1/runs` and preserve the request/idempotency key.
For MCP call **`antifold_inverse_fold`** with the same `parameters`, `inputs`,
`version`, `region`, `gpu` and saved `idempotency_key`; omit REST's `model` and `workflow` fields.
Poll `md_run_status` with the returned `run_id`, then use `md_run_artifacts`.
Submission acknowledgement is not a successful scientific result.

## Inputs and native controls

All scientific paths are relative to the archive root. Runtime staging below
`data/inputs/` is handled by the service. Files must contain usable N/CA/C protein
backbones. Sampled chains require canonical amino acids. Supply **one** of
`pdb_file` or `pdb_dir`; `pdbs_csv` is for the directory form.

For a batch, archive `structures/first.pdb`, `structures/second.pdb` and
`batch.csv`; use `pdb_dir:"structures",pdbs_csv:"batch.csv"`. CSV columns are
`pdb,Hchain,Lchain`; `pdb` is a basename without `.pdb`, e.g.
`first,H,L`. Do not use relative subdirectories in that column: the native output
writer cannot create the corresponding nested output path. Batch selections
belong in CSV, not ignored scalar chain flags. For nanobody plus antigen use
`pdb,Hchain,Agchain` and e.g. `nanobody,A,B`, with `nanobody_mode:true`.
Chain columns follow `pdb` in heavy, light (when present), then context order;
empty cells are omitted. Only the first chain is sampled in nanobody mode.
Confirm that the exact live version publishes this contract.

| Controls | Meaning |
|---|---|
| `heavy_chain`, `light_chain` | Explicit paired chain IDs; light requires an explicit heavy/nanobody selection. |
| `nanobody_chain`, `nanobody_mode` | Native single-domain selection/mode; do not conflict with a different heavy chain. |
| `antigen_chain` | Include antigen structural context; antigen is not a designed antibody chain. |
| `skip_anarcii_numbering` | True only when the supplied antibody residue numbering is already suitable IMGT numbering; otherwise native ANARCII numbering applies. |
| `regions` | Space-separated native CDR/FW selectors or role-qualified IMGT positions/ranges, e.g. `CDRH3 L:66-70` or `H:111`. Preserve spaces. Insertion-coded IMGT positions remain distinct. H/L designate selected antibody roles. |
| `num_seq_per_target`, `sampling_temp` | Samples per target **per temperature**; zero samples scores only. Temperatures are a space-separated string; native values below 0.001 clamp to 0.001. |
| `limit_variation` | Native mutation-limiting sampling option; preserve the requested scientific setting. |
| `extract_embeddings` | Also return per-residue structural encoder embeddings. |
| `custom_chain_mode` | Native custom chain interpretation; use only its published supported chain/numbering contract. |
| `batch_size`, `num_threads`, `seed` | Native resource/RNG controls. Original whole-batch RNG semantics are preserved; changing batching or target ordering may change samples. |

PDB is the qualified reference path. Native mmCIF author/label chain namespaces
and multi-character chain IDs have recorded unresolved compatibility cases; do
not promise general mmCIF support, silently rename chains, or change the scientific
input to conceal a failure. Raw caller checkpoint files, Python code and arbitrary
Torch pickle import are not accepted; select a named qualified scientific version.
Training and fine-tuning are not enabled by these inference workflows.

## Interpret and validate results

Inspect the returned artifact inventory and verify downloaded sizes and SHA-256
checksums. For each target, expect the following when their options were requested:

- Per-residue CSV: the twenty amino-acid columns are **natural log normalized
  probabilities**, not raw logits or affinity scores. Preserve chain labels,
  residue numbers and insertion codes when joining to a structure.
- FASTA: the original sequence followed by the requested samples at each
  temperature. Residues outside the selected design regions must stay unchanged.
  `score` and `global_score` are positive mean negative log-likelihoods; **lower
  is better**. Selected-region and whole-sequence scores have different scopes.
- NPY: float32 structural encoder embeddings, one row per returned residue and
  512 features per row. This is not a decoder-input embedding.
- Per-residue `perplexity`: `exp(entropy)`, an effective amino-acid alphabet size
  between 1 and 20, rather than sequence-level perplexity.

Native sampling is independent sampling from teacher-forced marginals conditioned
on the supplied original sequence. It is not autoregressive sequence design and
does not establish folding stability, binding affinity or experimental validity.
Use an explicitly qualified downstream folding/scoring workflow for those goals.

## Lifecycle and errors

AntiFold is submitted as a finite GPU job and releases compute after completion.
Owner-private working storage is temporary and asynchronously synced to the bound
bucket. Shutdown retries final uploads for at most five minutes, then deletes
scratch even during a bucket outage; only verified bucket data can be recovered.
The native CLI has no mid-forward or mid-batch checkpoint: an interrupted atomic
batch must be recomputed. Do not describe it as resuming a partly computed batch.

Use the shared client's owner-scoped status/artifact/cancel methods. A `403` is an
authorization/data/region failure, not permission to switch identities. Correct
structured `422` field/rule errors before another execution. Preserve the same
request key after an uncertain response and report the original run ID; never
fan out duplicate work to bypass queue limits. Detailed runtime failures must be
reported with their public error and run ID, without publishing credentials,
signed download links, scientific payloads or internal deployment information.
