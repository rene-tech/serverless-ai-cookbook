# Proteina-Complexa targets

Use App `proteina-complexa`, operation `design-binders` and the discovered
`submit_proteina_complexa` tool. Read its live model/parameter schema and
`input_artifact_contract` before preparing the request. A catalog lists useful
presets, not the proteins a user is allowed to target. If discovery lacks the
explicit `target` object, report that deployment/schema mismatch; preserve the
requested design rather than substituting a catalog target or an older API.

A retained MCP connection may cache an older submission schema even when
`get_model_schema` advertises `target`. If its direct tool still requires
`target_id`, use the normal discovering batch/study client below and report the
stale connection; do not add a dummy preset ID. An API `tools/list` response
alone does not prove that the client refreshed its loaded tools. Keep the
original caller identity and any already accepted operation.

## Preserve the scientific input

Use exactly one of `parameters.target` and `parameters.target_id`. For a custom
protein target, `target` contains:

| Field | Meaning |
| --- | --- |
| `bundle_path` | Exact relative path of the supplied structure inside the uploaded target bundle; not a URL, client path or preset ID. |
| `target_input` | Selected chains/residues in the structure's numbering, such as `A1-76` or `A1-40,B5-30`. |
| `hotspot_residues` | Explicit chain/residue identifiers such as `["A8", "A44", "A70"]`. An empty list deliberately omits hotspot conditioning. |
| `binder_length` | Fixed length `[64]` or inclusive range `[60, 90]`; equal endpoints `[64, 64]` also fix the length. |
| `pdb_id` | Optional provenance identifier; it does not download a structure or select a preset. |

Inspect the actual structure before choosing fields. Each selected chain and
hotspot must exist, and every hotspot must lie within the selected residues.
Keep a residue map for deliberate renumbering or chain changes. Do not silently
drop missing hotspots, crop domains, repair atoms, select an alternative model,
or change the supplied structure to make validation pass. Resolve ambiguous
insertion codes, alternate conformers or ensemble models explicitly. Preserve
the original bytes and record any scientifically intended preparation.

Ask for the structure or its unambiguous public source, chain selection, intended
epitope/hotspots and binder length only when that information is missing. A
protein name or sequence alone is not a prepared structure. If hotspot choice
is delegated, propose an evidence-linked patch and distinguish it from a
validated epitope. Do not invent hotspots or turn missing information into a
claim that custom targets are unsupported.

Keep `variant`, `run_name`, `seed`, `num_samples` and `diffusion_steps` in the
parameter object alongside `target`. Sampling steps are an explicit scientific
choice: the pinned upstream baseline is 400; a shorter run is a different
protocol and does not establish equivalent geometry or quality. Respect the
user's supplied settings and validate against current schema bounds.

An intentionally selected preset uses its exact published `target_id` and
bundle path instead. Read its chains, hotspots and length range: two presets
can share a PDB and encode different experiments. Do not invent aliases or use
both inputs to override a preset.

## Upload and submit through the normal client

The source is an authenticated, finalized `target-bundle` artifact with semantic
type `proteina-complexa-target-bundle/v1`. Match the live media/compression
contract. An attachment, workspace filename and artifact reference are distinct.
Use the trusted upload helper; do not fabricate artifact IDs, hashes or signed
URLs, paste the PDB into tool arguments, or expose credentials.

The [parameter example](../examples/proteina-custom-target.json) uses the public
[1UBQ ubiquitin structure](https://www.rcsb.org/structure/1UBQ), chain A residues
1–76 and three explicit structural anchors. It is a small pipeline example,
not evidence of a functional binder or a validated epitope. For another target,
replace the structure and scientific fields together after inspection.

Prepare in a fresh directory, retaining the downloaded bytes and source URL:

```sh
mkdir -p /workspace/proteina-example/inputs/targets
curl --fail --location https://files.rcsb.org/download/1UBQ.pdb \
  --output /workspace/proteina-example/inputs/targets/1UBQ.pdb
cp /app/skill/binder-design-campaigns/examples/proteina-custom-target.json \
  /workspace/proteina-example/parameters.json
python3 /app/skill/gromacs/scripts/make-input-bundle.py \
  --source /workspace/proteina-example/inputs \
  --output /workspace/proteina-example/target.tar.gz
```

The existing bundle helper preserves relative paths and reports measured hashes;
it does not run a simulator. Other clients resolve it from their installed skill
directory. The parameter file contains only model parameters, not an outer
scientific-run envelope. In LibreChat, prefer the durable batch study path in
`scientific-batch` for a campaign. The packaged standalone path is:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model proteina-complexa --tool submit_proteina_complexa \
  --operation design-binders \
  --source /workspace/proteina-example/target.tar.gz \
  --parameters /workspace/proteina-example/parameters.json \
  --entry-name target-bundle --semantic-type proteina-complexa-target-bundle/v1 \
  --media-type application/x-tar --compression gzip \
  --output /workspace/proteina-example/receipt \
  --display-name 'Ubiquitin custom target' \
  --idempotency-key YOUR_STABLE_REQUEST_KEY \
  --service-class customer-batch --wait-seconds 1 --poll-seconds 10
```

This uses configured authentication, discovers the schema, uploads/finalizes
the real bytes and submits the typed request. Other MCP clients use their
trusted file bridge and the same discovered submission contract. Retain the
receipt and returned native `op-...` ID. A pending result (exit 75) is observed
with `get_operation`; do not change the key or submit again to poll. Retrieve
the completed result and verify every declared artifact before interpretation.

## Other variants and actionable failures

`ligand-target` and `ame` have different scientific inputs. Use their current
published target fields; a protein hotspot list does not describe either task.
Upstream `ligand_only: true` consumes the entire supplied file as the ligand;
`false` selects ligand residue names. Keep the intended molecule, atom naming,
bond topology and protonation. Multiple ligand names require bonds from the
file; upstream SMILES-based bond regeneration is single-ligand only. AME uses
`contig_atoms`, for example `A64: [O, C]; A86: [CB, CA, N, C]`, to name actual
motif atoms. Validate every residue and atom; malformed or missing constraints
must not disappear silently.

For a rejected request, report the failing field, missing archive member,
chain/residue/atom or unsupported feature and the concrete correction needed.
Keep a rejected draft distinct from an admitted operation. If a constraint is
absent from the live schema, do not invent a field or promise an upstream CLI
feature such as a different search algorithm, cyclic topology or arbitrary
chemical restraint. Explain the specific unavailable feature without limiting
ordinary custom protein targets. Preserve terminal error details and the
operation ID; do not relabel execution failure as successful design.

Retain target/parameter hashes, seed, sampled binder length, raw designs,
refolded structures and score provenance. Evaluate raw and refolded geometry
separately, with explicit chain/residue correspondence. Contacts, confidence
and successful execution do not prove affinity, specificity or function.

Primary implementation references, reviewed 24 October 2026 at upstream
revision `54058860d43444c7289873f77d3e50b5b02348cd`:
[protein selection and hotspot matching](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/54058860d43444c7289873f77d3e50b5b02348cd/src/proteinfoundation/utils/pdb_utils.py),
[target and ligand features](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/54058860d43444c7289873f77d3e50b5b02348cd/src/proteinfoundation/datasets/gen_dataset.py),
[motif atom parsing](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/54058860d43444c7289873f77d3e50b5b02348cd/src/proteinfoundation/utils/motif_utils.py).
