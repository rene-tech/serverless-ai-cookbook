---
name: runai-diffdock
description: Submit receptor–small-molecule docking with managed DiffDock through Scientific AI REST or MCP, retrieve ranked poses, and interpret confidence and recovery limits.
license: Apache-2.0
---

# DiffDock on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
This managed API uses the caller's supplied `SCIENTIFIC_AI_URL`, token and bound
bucket; the separate `diffdock` skill describes the older backend. Current
qualification covers a bounded docking envelope, not all native input modes,
commercial clearance or production acceptance.

## dock

Use DiffDock for candidate small-molecule poses in a supplied receptor structure.
Confidence is unitless predicted pose quality, **not binding affinity** or evidence
of experimental binding. Coordinates are in ångströms in the receptor frame.

Read `GET /v1/models/diffdock?workflow=dock` first, or call
`md_models(model="diffdock", workflow="dock", detail=true)`. Use its exact version,
input/output contracts and supported controls. The scientific release is `v1.1`
(DiffDock-L). Never infer availability or qualification from a schema field alone.

Authenticate only to the configured Scientific AI origin using the managed API
credential supplied during onboarding. Read it from `SCIENTIFIC_AI_TOKEN` or an
approved secret store. Storage uses the user's separate, existing bucket binding
and scoped storage credential. Neither credential belongs in settings or archives.

Create gzip-compressed `input.tar.gz` with relative archive-root members:

```text
settings.json
receptor.pdb
```

For the tested 1STP/biotin example, `settings.json` contains:

```json
{"complexes":[{"complex_name":"1STP biotin redocking","protein_path":"receptor.pdb","ligand_description":"O=C(O)CCCC[C@@H]1SC[C@@H]2NC(=O)N[C@@H]21"}],"num_poses":10,"time_divisions":20,"steps":18,"random_seed":1}
```

Prepare the matching receptor with Python 3 standard library in a new local
working directory. This unauthenticated public download retains the 121-residue
chain A ATOM records and removes co-crystallized biotin/waters. Stop if either
checksum differs; do not silently substitute a changed receptor.

```python
import hashlib, urllib.request
from pathlib import Path

raw = urllib.request.urlopen('https://files.rcsb.org/download/1STP.pdb', timeout=60).read()
assert hashlib.sha256(raw).hexdigest() == '6fbb3d5c324e717fe7284703426e74ea58191431720daab1b2faa0bbb6430f30'
lines = raw.decode().splitlines()
receptor = '\n'.join([line for line in lines if line.startswith('ATOM  ')] +
                     [next(line for line in lines if line.startswith('TER   ')).ljust(81), 'END   ']) + '\n'
assert hashlib.sha256(receptor.encode()).hexdigest() == '481e50967d5a880f1e5312cc8893809427d5fb118f0b6ad4009b2ebf5c037339'
Path('receptor.pdb').write_text(receptor)
```

Save the preceding JSON as `settings.json`, then run
`tar -czf input.tar.gz settings.json receptor.pdb`.
Do not pair this ligand with an unrelated receptor or silently change protonation,
chemistry or stereochemistry. This is a known-reference example, not a universal
quality guarantee. The original [RCSB PDB 1STP structure](https://www.rcsb.org/structure/1STP)
is [CC0](https://www.wwpdb.org/about/usage-policies); retain its structure citation.

Upload the archive under a new key in the authenticated owner's bound bucket
using ordinary S3 tooling. Calculate its full SHA-256 and byte length. Do not
submit public URLs, local paths, another owner's key or an implicit server example.
The archive media type is `application/gzip`; settings are `application/json`,
PDB is `chemical/x-pdb` and SDF is `chemical/x-mdl-sdfile`. The archive has no
`data/` wrapper; staging places its members in `data/inputs/`.

POST `/v1/runs` with `Authorization: Bearer $SCIENTIFIC_AI_TOKEN` and a unique
`Idempotency-Key`. The request has this shape; substitute the actual uploaded
key, checksum and size rather than sending the angle-bracket descriptions:

```json
{"model":"diffdock","workflow":"dock","version":"v1.1","parameters":{},"inputs":[{"name":"input.tar.gz","key":"<owner archive key>","sha256":"<64 lowercase hex characters>","size_bytes":12345}]}
```

Replace the illustrative `size_bytes` with your complete compressed byte count.
Use storage/output budgets from discovery appropriate for the actual workload.
Omit `region`/`gpu` for authorized platform selection, or provide
an allowed region/GPU from your platform allocation. An explicit disallowed region
is an error, not permission to run somewhere else. API `parameters` overrides the
same setting in `settings.json`; omission or null preserves settings/defaults.

For MCP call `diffdock_dock` with the same fields except `model` and `workflow`,
and provide `idempotency_key`. Use `parameters={}` to preserve archive settings.
Do not submit a second request merely because polling or a client connection
times out. Keep the returned opaque `run_id` and reuse the original idempotency
key only with identical input.

Poll `GET /v1/runs/{run_id}` or `md_run_status`. On failure, inspect the structured
error and its next action; a CPU validation failure may have diagnostic artifacts
but has no docking result. Deterministic invalid input requires correction rather
than blind retry. Stop with POST `/v1/runs/{run_id}/cancel` or `md_run_cancel`.

Retrieve `/v1/runs/{run_id}/artifacts` or `md_run_artifacts`. Verify downloaded
bytes against every returned SHA-256 and length. Use a separate unauthenticated
HTTP client for signed `download_url` values; never forward the API bearer to
storage. Treat signed URLs as temporary secrets. Scientific results remain in the
owner's bucket; the service removes temporary per-job scratch after at most
300 seconds of final upload retries, even when export fails. A reported unsynced
tail loss is not a successful export.

Results contain `complex-NNNNNN/rankR.sdf`, `poses.json` and `science.json` below
`data/outputs/`; requested trajectories add `rankR_reverseprocess.pdb`. Inspect
pose count, finite coordinates, molecular identity/stereochemistry and confidence
ordering. A top-ranked pose can be scientifically wrong despite valid files.
A successful computation is distinct from acceptable geometry and from a reference
goal. `science.json.pose_quality` reports per-pose receptor contact distances and
`severe_overlap_below_1_2_angstrom` flags, with an aggregate count of poses without
that severe-overlap flag. This conservative screen is not full physical validation:
`complete_physical_validation` is false. `reference_goal_poses` is null when no
reference structure is submitted. A high-confidence or unflagged pose can still
miss an experimental reference; assess chemistry, clashes and predefined reference
metrics independently. Do not discard poor poses or alter thresholds to imply
that the requested scientific goal passed.

Requested reverse-process PDB trajectories have `steps + 3` frames. Match each
trajectory's final heavy-atom coordinates to its ranked SDF within file-format
rounding; preserve atom correspondence and inspect all requested poses.

## Batches, controls and limits

Use either `complexes` or `protein_ligand_csv`, never both. CSV columns are
`complex_name,protein_path,protein_sequence,ligand_description`; additional CSV
metadata is ignored. Paths in settings resolve from its directory; paths inside
CSV rows resolve from the CSV's directory and must stay inside the input archive.
Labels may contain spaces and are not output filesystem paths. Give each row a
unique label. Seeds are `random_seed + complex_index` within signed int32 range.

The schema enumerates pose count, schedule/steps, batch size, trajectory, initial
noise, final-step noise, residue initialization and translation/rotation/torsion
temperature controls. Preserve requested scientific settings. `steps` cannot
exceed `time_divisions`; effective batch is `min(batch_size,num_poses)`. Native
defaults include one pose, so explicitly request ten for the reference example.
Never reduce work silently to fit a resource limit.
Pinned native sampling cannot handle a partial final pose batch: when
`num_poses > batch_size`, require `num_poses % batch_size == 0`. Counts at or below
the requested batch remain supported. Admission rejects an unsupported partial
final batch; request a supported batch explicitly rather than silently overriding
the user.

Inline SMILES and SDF are the prepared primary formats; native MOL2/PDB/PDBQT
neural workflows are not yet qualified. A multi-molecule SDF supplies only its
first molecule; use a separate complex row per molecule. Supplied receptor PDBs
are required in this release: sequence-only ESMFold is blocked by missing runtime
assets and is rejected by CPU validation before GPU admission. Arbitrary code,
serialized customer neural checkpoints, training and GNINA execution are excluded.

The current native worker has one **900-second whole-worker budget**, including
all complexes; the two-week operation expiry is not a two-week docking allowance.
Split larger campaigns into appropriately sized submissions. Resume uses only
completed, verified owner-exported complex units; an interrupted complex recomputes.
Use `md_run_resume(run_id,region,gpu)` or POST `/v1/runs/{run_id}/resume` only when
a verified restartable checkpoint is available and the target is authorized.
Cross-region recovery is still awaiting live qualification; do not promise it.
