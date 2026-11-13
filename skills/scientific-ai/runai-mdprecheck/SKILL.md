---
name: runai-mdprecheck
description: Inspect molecular-dynamics inputs with CPU-only MDPrecheck on the managed Scientific AI Run:ai service. Use for prepared GROMACS TPR intake, source topology/coordinate/MDP checks and bounded probes, or geometry comparison across coordinate stages.
license: Apache-2.0
---

# mdprecheck on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `mdprecheck`. Scientific version: `0.1.0+git.1ab41dd`, with GROMACS
`2026.4` for CPU checks/probes; confirm live supported versions and workflow
schemas before submitting. Use the managed scientific API and ordinary MCP.

## Prepare scientific inputs

| Workflow | Default archive members | Purpose and MCP tool |
|---|---|---|
| `hecbiosim-20k` | `benchmark.tpr` | Prepared-system static intake; `mdprecheck_hecbiosim_20k` |
| `alanine-source` | `system.gro`, `system.top`, `production.mdp`, all referenced topology includes | Source checks and optional bounded probes; `mdprecheck_alanine_source` |
| `coordinate-stages` | `system.top`, `stage0.gro`, `stage1.gro`, all referenced topology includes | Static intake/geometry per coordinate stage; `mdprecheck_coordinate_stages` |

Upload one regular gzip-compressed tar archive named `input.tar.gz`, with its
SHA-256, compressed size and exact key in the caller's bound bucket, using the
portable procedure. Members and scientific file selectors are relative to the
archive root: no `data/` wrapper or selector prefix. Members stage below logical
`data/`. Preserve topology includes and matching atom order, identifiers and units.
Absolute paths, traversal, links and executable controls are rejected. A TPR does
not supply reconstructable source topology/MDP; source checks need those files.

This service is CPU-only; leave GPU selection unset. A requested region must be
authorized for the caller. Inputs and results use the caller's existing bound
bucket. Direct uploads need that bucket's approved object-write permission;
retrieval needs approved read access. A model request cannot select a different
bucket or supply storage credentials. Use only data and force fields the caller
is entitled to use; this skill does not grant dataset or software rights.

## Choose checks and controls

`hecbiosim-20k` and `alanine-source` run the native intake, geometry, sequence,
chemistry, environment, MDP and site diagnostics where the supplied data permits.
Inspect skipped checks and their reasons rather than treating them as passes.

| Scope | Typed parameters and defaults |
|---|---|
| Both check workflows | `threads`: integer 1–2, default 2. `intent`: array of `NAME`/`NAME=VALUE` scientific annotations. `define`: array of topology preprocessor definitions. `chain_names`: label mapping such as `PRO_A=Target,PRO_B=Partner`. Optional uploaded `fasta` selector. |
| Prepared TPR | `tpr` selects the prepared file. `probes` must be empty; this workflow cannot execute diagnostic dynamics. |
| Source check | `coords`, `top`, `mdp`, optional `ndx`, and optional `workflow` JSON select files. `probes` accepts unique `grompp`, `energy`, `minimize`, `stability`; default is `energy`, `minimize`, `stability`, and `[]` requests static checks. `nsteps`: integer 1–100,000, default 1,000, for bounded minimization/stability probes. Optional positive `dt` in ps and positive `hmr` mass-repartition factor override stability-probe settings. `force`: optional boolean native busy-host override within the existing CPU job limits. |
| Coordinate stages | `files`: nonempty unique `.gro`/`.pdb` paths, default `['stage0.gro','stage1.gro']`; `top`: default `system.top`. Optional `mdp`, `ndx`, `define`, `intent`. No selectable probes, FASTA or dynamics; execution uses two CPU threads. |

`intent` annotates the intended protocol; it does not rewrite an MDP. `define`
retains native static topology-preprocessor behavior and does not promise to
rewrite the MDP's own definitions. Probe settings do not modify uploaded source
files or establish a production simulation protocol. Do not silently reduce work,
change force fields, repair stereochemistry or relax findings to obtain a pass.
MDPrecheck does not support the generic native `output_budget_bytes` control.

The optional source `workflow` JSON supplies file selection only. The first
`grompp` step's `-c`, `-p`, `-f`, `-n` arguments select archive-root-relative
files; explicit `coords`/`top`/`mdp`/`ndx` parameters override the corresponding
selection. Its command strings are never executed. For example:

```json
{"command":"grompp","args":["-c","prepared/system.gro","-p","prepared/system.top","-f","prepared/production.mdp","-n","prepared/groups.ndx"]}
```

An uploaded matching source bundle can then use these parameters:

```json
{"workflow":"selection.json","fasta":"reference.fasta","chain_names":"PRO_A=Target","intent":["stage=production","dt=0.002"],"define":["POSRES"],"probes":["grompp","energy","minimize","stability"],"threads":2,"nsteps":1000,"dt":0.002,"hmr":1,"force":false}
```

FASTA comparison needs an identifiable multi-residue protein chain. A single
alanine residue may yield no protein-chain comparison; absence of a match is not
proof of sequence identity. Inspect sequence coverage and reported substitutions
against the uploaded reference. No network UniProt retrieval is exposed.

## Submit the selected workflow

REST requests use the following bodies; discover the live owner's example
reference before relying on omitted `inputs`. Templates must already exist in
that caller's bound bucket. For custom data, attach the uploaded archive reference.
Named MCP tools take the same typed fields without REST `model`/`workflow`, plus
the saved `idempotency_key`. Reuse the same key and unchanged body after an
uncertain submission; inspect the existing run rather than creating duplicate work.

### hecbiosim-20k

```json
{"model":"mdprecheck","workflow":"hecbiosim-20k","version":"0.1.0+git.1ab41dd","parameters":{}}
```

### alanine-source

```json
{"model":"mdprecheck","workflow":"alanine-source","version":"0.1.0+git.1ab41dd","parameters":{}}
```

### coordinate-stages

```json
{"model":"mdprecheck","workflow":"coordinate-stages","version":"0.1.0+git.1ab41dd","parameters":{}}
```

## Worked coordinate-stage comparison

Discover the model using the configured API URL/token and save the selected
example as in the portable client procedure:

```sh
MODEL=mdprecheck
WORKFLOW=coordinate-stages
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/$MODEL" > model.json
jq --arg w "$WORKFLOW" '.workflows[$w].example +
  {version:"0.1.0+git.1ab41dd",parameters:{}}' model.json > request.json
```

Inspect that workflow's `input_contract` and verify the example exists in the
bound bucket. The synthetic example has six residues in chain `PRO_A` and 71
atoms per coordinate file: `stage0.gro` is geometrically clean, while `stage1.gro`
introduces D-alanine at `PRO_A ALA3`. Those are expected fixture findings, not
expectations for caller data. This skill includes no fixture files or engine code.

For caller data, put the matching coordinates/topology and their includes in
`prepared-inputs/`. With the three default names and no additional includes:

```sh
tar -czf input.tar.gz -C prepared-inputs system.top stage0.gro stage1.gro
```

Include all additional topology files when required. Reuse the portable client's
checksum-reference and upload steps to set `request.json.inputs`. Different names
require matching `parameters.files`/`parameters.top`; preserve scientific contents.
Reuse its submit-once and poll procedure, then its artifact-inventory and verified
download procedure. MCP equivalent: `mdprecheck_coordinate_stages` with
`{"parameters":{},"version":"0.1.0+git.1ab41dd","idempotency_key":"saved-request-key"}`,
adding the same uploaded `inputs` when applicable.

Native filename/stage-number heuristics determine stage order; reversing the
`files` array does not override it. Selected paths must map to distinct output
stems: separators become underscores, extensions are removed, and `input`
becomes `input-stage`. For example, `a/b.gro` and `a_b.pdb` collide. The exact
case-sensitive `THIRD_PARTY_LICENSES.txt` and `summary.json` output names are reserved. These
collisions fail admission before allocation; choose distinct scientific names.

Confirm the live output contract advertises `data/mdprecheck-output/summary.json`
and its `summary_schema` before relying on the combined comparison. Select that
exact inventory path with the portable client's checksum-verified download
procedure (`RESULT_PATH='data/mdprecheck-output/summary.json'`), then inspect:

```sh
jq '{stages,defects,text}' result.bin
```

`stages` contains native-ordered file/status/`n_fail` rows; `defects` contains
tracked finding `id`, `where` and `present_in` lists. Use the ordered rows and
`text` to identify the first observed stage; a defect's `present_in` list itself
is sorted by filename. An older schema without this summary contract needs a
supported service release; do not guess a hidden result path.

Also inspect `data/mdprecheck-output/<stage-stem>/steps/intake.json` and
`steps/geometry.json`, plus each stage's `manifest.json`. For the example, stage0
has zero failed geometry findings; stage1 has a failed
`geometry.d_amino_acid` finding at `PRO_A ALA3`, first in `stage1.gro`.
The computation can succeed while this scientific defect is correctly reported. Retain
`data/mdprecheck-output/THIRD_PARTY_LICENSES.txt`. This operation produces no
HTML report or MD trajectories.

## Interpret and retain results

Poll the same owned run through public status/MCP. `QUEUED`, `SUBMITTED`,
`PENDING`, `INITIALIZING` and `RUNNING` describe execution progress; short jobs
may finish between polls. Terminal `SUCCEEDED` means computation completed,
including when a stage has scientific `fail` findings. An unreadable/error stage
fails computation and must never be called checked or clean. Warnings and skipped
checks remain findings, even after successful execution.

Check workflows export `data/mdprecheck-output/report.html`, `manifest.json`
and `steps/*.json`; requested probes add their diagnostic files. Read structured
findings, counts, errors and metrics alongside the self-contained HTML report.
Its bundled third-party notices are embedded in the HTML and also supplied as
`THIRD_PARTY_LICENSES.txt`; retain them with exported reports. A diagnostic pass,
minimized coordinates or a short stability probe does not prove equilibration,
convergence, correct biology or experimental validity.

Verify downloaded sizes/SHA-256 against the returned inventory and retain input,
version and scientific provenance in the owner's store. These finite checks are
normally restarted after interruption, not continued from an MD checkpoint.
Preserve the logical request and cumulative deadline; explicit cancellation does
not authorize automatic resubmission. Final upload retries last at most 300
seconds, after which unsynced scratch is deleted and loss reported; only verified
owner-bucket results survive as recovery evidence.

Use the gateway's public error procedure: `401` needs the approved token,
`403` needs an access/region/bucket-binding correction, `409` needs conflict or
delivery inspection, `422` needs the reported input/field correction, and `429`
needs bounded queue backoff. Do not retry deterministic errors or bypass access
denials. Keep secrets, signed links and private deployment identifiers out of
shared logs. This skill documents supported use, not blanket production,
commercial-rights or every-input scientific qualification.
