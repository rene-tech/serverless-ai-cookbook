---
name: runai-rfantibody
description: Design antibody or nanobody backbones, design CDR sequences with ProteinMPNN, and predict antibody/TCR structures using the managed RFantibody REST and MCP workflows with owner-bucket inputs and explicit scientific versions.
---

# RFantibody

Discover `rfantibody` with `GET /v1/models/rfantibody` or MCP `md_models`
`{"model":"rfantibody","detail":true}`. Use only versions, workflows and GPU/region
placements qualified in your live authorized catalog. This guide describes the
scientific version **1.0.0-947fd3dd** and its named native diffusion, MPNN,
antibody-RF2 and TCR-RF2 checkpoints. A listed model is not a commercial entitlement.

Use the shared [portable client](../runai-scientific-gateway/references/client.md)
for endpoint/token setup, existing owner-bucket credentials, upload/reference,
submit-once, polling, cancellation and verified artifact retrieval. Native Run:ai
administrator access and LibreChat are unnecessary. Never put credentials in model
parameters or chat. Bucket keys cannot change the authenticated request owner.

## Prepare one portable example archive

From discovery, take a workflow's versioned `usage_skill.download_url` as
`MODEL_SKILL_URL`. Obtain [fixture.py](fixture.py), [7Y1B.HLT.pdb](7Y1B.HLT.pdb)
and [provenance](FIXTURE-PROVENANCE.md) from that **same cookbook revision**.
A plain client can download all companions into a fresh private directory:

```sh
# Set MODEL_SKILL_URL to the workflow's discovered usage_skill.download_url.
python3 - <<'DOWNLOAD'
import os, urllib.parse, urllib.request
from pathlib import Path
base = os.environ['MODEL_SKILL_URL']
assert base.startswith('https://raw.githubusercontent.com/rene-tech/serverless-ai-cookbook/')
for name in ('fixture.py', '7Y1B.HLT.pdb', 'FIXTURE-PROVENANCE.md'):
    with urllib.request.urlopen(urllib.parse.urljoin(base, name), timeout=45) as response:
        data = response.read((2 << 20) + 1)
    assert len(data) <= 2 << 20
    with Path(name).open('xb') as target:
        target.write(data)
DOWNLOAD
python3 fixture.py input.tar.gz
```

It downloads checksum-pinned official public regression inputs, adds the bundled
CC0-derived known-positive 7Y1B structure, and prints the archive size and SHA-256.
It refuses to overwrite an existing file. Keep `fixture.py` beside its bundled
`7Y1B.HLT.pdb`; [provenance](FIXTURE-PROVENANCE.md) explains both sources.

The archive has root-level `framework.pdb`, `nanobody.pdb`, `target.pdb`,
`structures.qv`, `positive7Y1B.pdb`, `structures/ab_des_0.pdb`, `rf2/complex.pdb`
and `rf2/targets.json`. There is no `data/` wrapper or nested archive. Upload this
tar.gz to a new key in your existing owner bucket and construct the shared client's
`input-reference.json` with **name, key, sha256, size_bytes**. Its name is
`input.tar.gz`; all native file parameters below resolve inside that archive.
No legacy scientific-artifact manifest or semantic-type field is required.

## Four worked requests

Each request is an asynchronous finite job. The examples explicitly select
`eu-north1` / `h100` for GPU workflows; the CPU workflow explicitly selects `gpu:"cpu"`. Substitute an authorized, qualified placement. A forbidden
region is an authorization error. Automatic cost routing is available only where
the live catalog has qualified placement/performance data.

### Design

For a single full native backbone design:

```sh
jq -n --slurpfile input input-reference.json '{
  model:"rfantibody",workflow:"design",version:"1.0.0-947fd3dd",
  region:"eu-north1",gpu:"h100",inputs:[$input[0]],
  parameters:{target:"target.pdb",framework:"framework.pdb",num_designs:1,
    design_loops:"H1:7,H2:6,H3:5-13,L1:8-13,L2:7,L3:9-11",
    hotspots:"T305,T456",diffuser_t:50,final_step:1,deterministic:true}
}' > request.json
```

Submit `POST /v1/runs` using the shared client and a preserved idempotency key.
The corresponding typed MCP tool is **`rfantibody_design`**: supply the same
`parameters`, `inputs`, `version`, `region`, `gpu`, `idempotency_key`, omitting REST's
`model` and `workflow`. `num_designs` counts generated candidates, not accepted
binders; there is no experimental-binding guarantee.

### Sequence design

For native CDR sequence design, use REST `workflow:"sequence-design"` or MCP
**`rfantibody_sequence_design`**, with the same uploaded archive/reference and:

```json
{"input_path":"structures","input_format":"directory","seqs_per_struct":2,
 "temperature":0.2,"augment_eps":0.0,"deterministic":true,"debug":true}
```

### Sequence design CPU

For the unchanged native ProteinMPNN on CPU, select REST
`workflow:"sequence-design-cpu"`, `region:"eu-north1"`, `gpu:"cpu"`, or MCP
**`rfantibody_sequence_design_cpu`**. Use the same sequence-design parameters
and owner input reference above. This workflow allocates no GPU; CUDA workflows
never silently fall back to it. CPU and GPU sampling may give different
scientifically valid sequences at the same explicit seed.

### Predict complex

For the meaningful known-positive antibody structure prediction, use
`workflow:"predict-complex"` or MCP **`rfantibody_predict_complex`** and:

```json
{"input_path":"positive7Y1B.pdb","input_format":"pdb",
 "prediction_checkpoint":"antibody","num_recycles":10,"seed":42,
 "cautious":false,"hotspot_show_prop":1.0,"output_intermediates":false}
```

Poll the returned public run ID with REST status or `md_run_status`, then use
`md_run_artifacts`/the artifacts route and verify downloaded size and SHA-256.
An accepted submission is not completed or scientifically correct inference.

## Native controls and file contracts

The live detailed schema is authoritative for defaults, bounds and combinations.
All paths are archive-relative and must identify regular files/directories without
traversal, links or collisions. Raw caller Torch checkpoints and executable code
are outside this managed inference boundary.

| Workflow | Controls |
|---|---|
| `design` | `target`, `framework`, `num_designs`, `design_loops`, `hotspots`, `diffuser_t`, `final_step`, `deterministic`, `no_trajectory`, `output_format`, `cpu_threads`; typed `native_overrides` exposes the schema's native scientific noise/schedule/self-conditioning controls. |
| `sequence-design` / `sequence-design-cpu` | `input_path`, `input_format` (`directory` or `quiver`), `loops`, `seqs_per_struct`, `temperature`, `omit_aas`, `augment_eps`, `deterministic`, `debug`, `allow_x`, `output_format`, `cpu_threads`, optional `execution_granularity`. |
| `predict-complex` | `input_path`, `input_format` (`pdb`, `directory`, `quiver`, `json`), `prediction_checkpoint` (`antibody` or `tcr`), `num_recycles`, `seed`, `cautious`, `hotspot_show_prop`, `output_intermediates`, `output_format`, `cpu_threads`, optional `execution_granularity`. |

Native PDB inputs use **H/L/T format**, with H/L variable-chain roles, optional
antigen chain T where the workflow supports it, and native
`REMARK PDBinfo-LABEL: <absolute-residue-index> <CDR>` annotations. Ordinary raw PDB
author numbering is not automatically Chothia numbering. Prepare your own
structures using the pinned upstream HLT conversion instructions; do not guess
CDR boundaries. Native RF2 internally reorders complex chains to T-H-L before
returning H-L-T output.

`design_loops` has comma-separated unique CDR names, for example `H1:7,H2:6,H3:5-13`.
Native empty lengths (`H1:`), zero lengths and `|`-separated length alternatives
have their native meanings. Hotspots such as `T305,T456` reference existing
original target-chain/residue identifiers, not a newly numbered concatenation.
This pinned engine cannot unambiguously address negative or insertion-coded hotspot residue IDs; use a properly mapped, renumbered input.
For docked-complex partial diffusion, select `complex_input` instead of
`target`/`framework`, use CDR names without length changes and a compatible typed
`diffuser.partial_T` override. Consult the live cross-field schema first.
`diffuser_t` must be at least 15; `final_step` and `diffuser.partial_T` select shorter portions of that schedule.
The named diffusion checkpoint fixes `antibody.T_scheme` to `single_T_correct_selfcond` and `antibody.no_bugfix_t1d_mask` to `false`; incompatible values are rejected rather than silently overwritten.

Quiver is native text: each `QV_TAG <unique-tag>` starts a record containing HLT
PDB lines and optional native `QV_SCORE <tag> key=value|...` scores. Use a complete output file as the next
stage's Quiver input, or stage selected PDBs under `structures/` in a new archive.
A bucket key is not a path inside a running container. Keep campaign IDs and
stage-to-stage sequence/chain mappings yourself using the public run/artifact
contracts; this guide does not invent a separate campaign API.

RF2's JSON format is a mapping from unique structure tags to entries. Each entry
contains at least one nonempty `Hseq`/`Lseq`, target `T`, and optional target
`hotspots`. For a target of length N, `T.seq` is N native integer residue tokens
(0..21; canonical order ARNDCQEGHILKMFPSTWYV, then UNK/MAS), `T.idx` is N residue
indices, `T.xyz` is N×27×3 coordinates in angstrom, and `T.mask` is N×27 atom
presence flags. N/CA/C must be present and finite. `T.pdb_idx` and `T.cdr_bool` in
the official fixture are not used by this parser. Prefer exactly N JSON booleans
for explicit target hotspots. The original native fixture uses Python-JSON NaN
for absent sidechain coordinates; a strict external JSON parser must account for
that dialect. Coordinates with a false mask may instead use finite placeholders.
Do not replace missing backbone coordinates. The `rf2/targets.json` example is a
TCR input and must select `prediction_checkpoint:"tcr"`; it is not an antibody
positive control. The named checkpoints are distinct pretrained scientific
models, not resumable execution checkpoints.

## Outputs and scientific interpretation

Read the returned inventory. Per native unit, results are under
`data/outputs/rfantibody/<operation>-<unit>/result.json` and `native/`:

- Backbone design returns PDB or `designs.qv`, native TRB metadata and optional
  denoising trajectories. Those trajectories are algorithm steps, not MD time.
  TRB files may contain native serialized objects: do not unpickle untrusted data.
- MPNN returns the selected number of CDR sequence designs per input structure,
  retaining framework/target sequence and backbone. `allow_x` is a debugging
  capability, not a promise that unknown residues are scientifically usable.
- RF2 returns predicted structures and native scores, including interaction PAE
  and confidence/geometry metrics where defined. Optional recycle outputs are
  separately indexed. PAE is in angstrom; it is not affinity, Kd or experimental
  success probability. The correct 7Y1B complex is a software/scientific positive
  control; outputs for new designs may legitimately fail confidence filters.

The primary [RFantibody paper](https://www.nature.com/articles/s41586-025-09721-5)
explains that confidence depends strongly on hotspot information and that RF2
filtering has limitations. Do not infer a general success rate from one fixture,
or treat a reproducibility smoke test as a positive binder experiment.

## Isolation, recovery and failures

Each request has private temporary scratch, staged from and asynchronously
exported to its authenticated owner's store. Concurrent users share compute, not
request data. Model GPU allocation returns to zero when jobs finish; warm-node
placeholders belong to fleet capacity, not a customer's persistent endpoint.

Completed native backbone designs are checkpoint units with stable global IDs.
On interruption, verified completed designs are retained byte-for-byte and only
the unfinished design is recomputed. Native stochastic process boundaries do not
preserve a counterfactual uninterrupted random-number stream. Intra-design
sampling has no native checkpoint.

MPNN/RF2 default to `execution_granularity:"native-batch"`, preserving the native
one-process batch and its original seeded input stream. For long multi-input
requests, explicitly choose `execution_granularity:"input"`. Each complete
original input becomes a verified checkpoint unit; its first native order is
retained across resume, completed results are reused byte-for-byte, and only the
unfinished input is recomputed. The native engine starts independently for each
input: this opt-in mode does **not** preserve the counterfactual whole-batch RNG
stream. The chosen mode is written into every unit's downloadable `result.json`.

To try that mode on multiple public inputs, generate a separate archive with
`python3 fixture.py input-multi.tar.gz --multiple-inputs`, upload it and create its
own input reference. It adds a second MPNN input under `structures/` and two
known-complex RF2 inputs under `prediction-structures/`. Use MPNN's usual
`input_path:"structures"` or RF2's `input_path:"prediction-structures"` with
`input_format:"directory"`, and explicitly set `execution_granularity:"input"`.
For RF2 retain `prediction_checkpoint:"antibody"`, `num_recycles:10`, `seed:42`
and `hotspot_show_prop:1.0`. The duplicate fixtures test staging and checkpoint
units; they are not independent candidates or a scientific success-rate study.

One input with a huge `seqs_per_struct`, or one long RF2 forward/recycle sequence,
is still atomic. Per-input mode does not provide intra-input checkpoints; check
the live qualified envelope before a large campaign.

Resume only through the owner-scoped public contract, with the same inputs,
scientific version/settings and original deadline. Cross-region resume requires
an authorized compatible target; source execution stops before target execution.
Final-upload retries last at most five minutes, then exact temporary storage is
deleted even if upload failed. Only verified bucket checkpoints survive.

Correct structured input errors before retrying. Preserve the public run ID and
sanitized cause for terminal failures; on an ambiguous submission, reconnect with
the same idempotency key rather than launching a duplicate. Regular users cannot
read/cancel/resume another owner's request. Do not switch identities after a403.
Model code/README-referenced weights use MIT; the TCR publisher also provides
CC-BY-4.0 terms. Platform licensing/security qualification controls hosted use;
this usage guide is not a licence or production-readiness grant.
