---
name: runai-openmm
description: Run the reviewed OpenMM CUDA molecular-dynamics workflow through the managed Scientific AI Run:ai REST API and typed MCP, with prepared topology/coordinate inputs, reviewed physical controls, verified artifacts and checkpoint recovery.
license: Apache-2.0
---

# OpenMM on Scientific AI Run:ai

Scientific version: `8.6.1.dev-b399af4`. Confirm the live authorized model/schema
before submitting. Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md)
and [portable REST/MCP procedure](../runai-scientific-gateway/references/client.md)
for supplied `SCIENTIFIC_AI_URL`/token, discovery, owner-bucket upload, idempotent
submission, polling, errors, cancellation and verified downloads. No local OpenMM
installation or workbench helper is required. This skill documents the current
contract; it does not certify every system, GPU, format or commercial-use gate.

## Prepare scientific inputs

Use one `input.tar.gz` (`application/gzip`), with relative archive-root scientific
files and no `data/` wrapper. Members stage below logical `data/`. Follow the
gateway to upload into your existing bound bucket and supply exact
`name/key/sha256/size_bytes` through `inputs`. Hash the complete compressed object;
`size_bytes` bounds its compressed length. Do not include links, escaping paths,
credentials, runtime state or unreviewed executable code. This service executes reviewed
platform workflows, not customer Python or uploaded System/State/force-field XML.

### hecbiosim-20k

MCP: `openmm_hecbiosim_20k`. This existing finite 19,605-atom benchmark requires
archive-root `benchmark.top` (AMBER topology), `benchmark.crd` (matching coordinates
and box) and the published reviewed `benchmark.py`. Preserve that control's bytes
(SHA-256 `9a28df64b8f1f87d06503e8aacd24edf5977110f6c1368b4f789f9c11bba27f7`).
Read the exact example key/hash from discovery; use it only if it exists in your
own bound bucket. Caller topology and coordinates must describe the same system.

The workflow builds a PME AMBER System, minimizes, then runs Langevin-middle
NPT dynamics with a Monte Carlo barostat. The controls below preserve its default
protocol when omitted; `pressure_bar` does not select NVT here. Unknown controls,
explicit nulls, nonfinite numbers, fractional integers and boolean integer values
are invalid.

| Public parameter | Default and allowed values | Native meaning |
|---|---|---|
| `steps` | `50000`; integer 100–50000000 | Total production integration steps |
| `threads` | `8`; integer 1–8 | Retained interface field; this CUDA workflow does not map it to native CPU/PME threads |
| `precision` | `"mixed"`; `single`, `mixed`, `double` | CUDA `Precision` |
| `random_seed` | `2026`; integer 1–2147483647 | Requested seed for phase-specific integrator/barostat seeds; recovery semantics below |
| `temperature_k` | `300`; finite number >0 K | Langevin-middle temperature and barostat temperature |
| `friction_per_ps` | `1`; finite number ≥0 ps⁻¹ | Langevin-middle friction |
| `timestep_ps` | `0.002`; finite number >0 ps | Integration timestep |
| `pressure_bar` | `1`; finite number >0 bar | Monte Carlo barostat pressure; this field does not select NVT |
| `barostat_interval` | `25`; integer ≥1 | Barostat attempt interval in integration steps |
| `report_interval` | `25000`; integer ≥1 | State table and trajectory reporting cadence in steps |
| `checkpoint_interval_steps` | `50000`; integer ≥1 | Closed production-segment/checkpoint cadence in steps |
| `minimize_max_iterations` | `10`; integer ≥0 | Native minimization `maxIterations`; `0` means no fixed iteration limit |
| `nonbonded_cutoff_nm` | `1.2`; finite number >0 nm | System `nonbondedCutoff`, with PME retained |
| `constraints` | `"HBonds"`; `none`, `HBonds`, `AllBonds`, `HAngles` | System constraint selection |
| `rigid_water` | `true`; boolean | System `rigidWater` |
| `ewald_error_tolerance` | `0.0005`; finite number strictly between 0 and 1 | System `ewaldErrorTolerance` |

### reviewed-simulation

Bounded H100 tests in EU-North1 passed for prepared AMBER NPT, PDB NVT,
mmCIF NVT-to-NVE and GROMACS NVE, plus four input-validation negatives rejected
before GPU execution. These cases do not qualify every control, system or GPU,
or establish production throughput. Use the workflow only when authorized
discovery advertises it. It owns one native job per managed run, with an ordered
list of `minimize`, `equilibrate` and `production` phases. It accepts typed JSON
controls and scientific files; it does not execute customer code or uploaded
State/System/force-field XML/plugins.

| Input system | Typed fields and archive-root members |
|---|---|
| Prepared AMBER | `format:"amber"`, `coordinates` names INPCRD/RST7 and `topology` names PRMTOP |
| PDB or mmCIF | `format:"pdb"`; `coordinates` names a `.pdb`, `.cif` or `.mmcif` file; omit `topology` |
| Prepared GROMACS | `format:"gromacs"`; `coordinates` names GRO, `topology` names TOP; bundle every referenced include; `include_directory` defaults to `.` and `defines` are typed strings |

PDB/mmCIF preparation uses only the advertised installed
`amber14-all.xml` and `amber14/tip3pfb.xml`. These are names, never uploaded paths.
The schema also describes hydrogen addition/pH, solvent/ions, constraints and
explicit hydrogen-mass repartitioning. Native topology inputs already carry their
parameters. Do not infer compatible force fields or parameterize an unknown
ligand silently.

Choose phase physics explicitly: Langevin-middle without `pressure_bar` is NVT;
with positive pressure it is periodic NPT; Verlet without pressure is NVE.
Preserve velocities across phases unless an intentional `reset_velocities:true`
is part of the protocol. `steps`, `timestep_ps`, `report_interval` and
`checkpoint_interval_steps` are scientific choices, not speed presets. Select
qualified versions/precision from live discovery. Neither a short smoke test nor
successful minimization establishes equilibration or convergence.

The following portable six-atom toy demonstrates PDB staging and NVT only. It is
synthetic and is not a production force field benchmark or a solvated study.
It illustrates the public PDB contract; ordinary customer systems need their
own scientific preparation and appropriate parameter rights.

```bash
mkdir -p prepared-inputs
cat > prepared-inputs/water.pdb <<'PDB'
HETATM    1  O   HOH A   1       0.000   0.000   0.000  1.00  0.00           O
HETATM    2  H1  HOH A   1       0.957   0.000   0.000  1.00  0.00           H
HETATM    3  H2  HOH A   1      -0.240   0.927   0.000  1.00  0.00           H
TER
HETATM    4  O   HOH A   2      10.000   0.000   0.000  1.00  0.00           O
HETATM    5  H1  HOH A   2      10.957   0.000   0.000  1.00  0.00           H
HETATM    6  H2  HOH A   2       9.760   0.927   0.000  1.00  0.00           H
TER
END
PDB
tar -czf input.tar.gz -C prepared-inputs water.pdb
: "${SCIENTIFIC_DATA_ENDPOINT:?Use your bound bucket endpoint}"
: "${SCIENTIFIC_DATA_BUCKET:?Use your bound private bucket}"
: "${SCIENTIFIC_DATA_REGION:?Use your bound bucket region}"
: "${INPUT_KEY:?Choose a new object key in your bound bucket}"
# AWS CLI credentials/profile must already be supplied securely for this bucket.
aws --endpoint-url "$SCIENTIFIC_DATA_ENDPOINT" --region "$SCIENTIFIC_DATA_REGION" \
  s3 cp input.tar.gz "s3://$SCIENTIFIC_DATA_BUCKET/$INPUT_KEY"
export INPUT_KEY
python3 - <<'PYTHON'
import hashlib,json,os,pathlib
raw=pathlib.Path('input.tar.gz').read_bytes()
request={"model":"openmm","workflow":"reviewed-simulation","version":"8.6.1.dev-b399af4",
 "parameters":{"precision":"mixed","threads":8,"random_seed":73,"deterministic_forces":False,
 "jobs":[{"id":"water-nvt","system":{"format":"pdb","coordinates":"water.pdb",
 "forcefields":["amber14-all.xml","amber14/tip3pfb.xml"],"nonbonded_method":"NoCutoff",
 "constraints":"HBonds","rigid_water":True},"steps":[{"id":"minimize","kind":"minimize","max_iterations":10},
 {"id":"dynamics","kind":"production","steps":2000,"integrator":"langevin-middle",
 "temperature_k":300,"friction_per_ps":1,"pressure_bar":None,"timestep_ps":0.001,
 "report_interval":100,"checkpoint_interval_steps":500}]}]},
 "inputs":[{"name":"input.tar.gz","key":os.environ['INPUT_KEY'],
 "sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw)}]}
pathlib.Path('request.json').write_text(json.dumps(request)+'\n')
PYTHON
```

Submit `request.json` once with the authenticated gateway procedure.
Typed MCP uses `openmm_reviewed_simulation`: pass the exact `parameters`, `inputs`
and `version` fields from that request plus the saved `idempotency_key`; omit
REST `model`/`workflow`. Use the same run ID for status/artifacts across REST/MCP.
A CPU-only validation stage checks scientific files before GPU admission;
invalid inputs return a structured error and consume no model GPU attempt.
Do not repeatedly submit a deterministic input error.

The live `output_contract.native_declared_files` lists exact dynamic patterns and
media types; HTTP downloads may use `application/octet-stream`.
`data/openmm-output/prepared/` holds System/topology/initial-State provenance.
`data/openmm-output/<phase-id>/segment-<number>/` holds closed `segment.json`,
`state.xml`, `checkpoint.chk`, `structure.cif`, dynamics `state.csv`, and requested
DCD/frame-index files when frames were recorded. PDB is optional when
`pdb_exported=true`. Read actual manifest paths and metadata, verify hashes and
inspect scientific results. OpenMM binary checkpoints require compatible native
execution and should be resumed through the managed run API; they are not a
portable arbitrary file upload. This workflow uses the same private per-run
scratch, owner-bucket delivery, cumulative deadline and bounded deletion policy
as described below.

## Submit and inspect the same run

The existing minimal REST request remains:

```json
{"model":"openmm","workflow":"hecbiosim-20k","version":"8.6.1.dev-b399af4","parameters":{}}
```

For an explicit archive, add its owned `inputs` reference. Typed MCP uses
`openmm_hecbiosim_20k` with the same `parameters`, `version`, `inputs` and saved
`idempotency_key`, omitting REST `model`/`workflow`. Follow the gateway for
`POST /v1/runs`, bounded polling and `md_run_status`; keep the original run ID and
key after a disconnect or uncertain response. Queued/cold loading is not a
scientific failure. Inspect terminal errors rather than blindly retrying an
invalid system or treating transport success as completed dynamics.

Fetch `/v1/runs/{run_id}/artifacts` or `md_run_artifacts`. The actual inventory
is authoritative; verify complete SHA-256 and length for selected downloads.
Use a separate unauthenticated download client; never forward the scientific
bearer to signed storage URLs. Keep signed links private and renew them by
fetching the same owned inventory. In `reviewed-simulation`, phase IDs come from
the requested step IDs; segment numbers start at `000001` within each phase.
A phase may have several segments. Select actual `segment.json` entries rather
than assuming `result.json`, a single directory or optional trajectory files.

Inspect `segment.json`, dynamics `state.csv`, `state.xml`, `checkpoint.chk`,
`structure.cif`, optional `structure.pdb`, and requested `trajectory.dcd` plus
`trajectory-frames.jsonl`. Check backend/precision/version, requested versus final
steps/time, finite energies/positions/velocities, particle/system identity and
trajectory frame-step provenance. Periodic DCD frames may be imaged into the box
while State XML positions are unwrapped; compare using the recorded periodic box.
Kinetic energy follows the native integrator's velocity-time convention, so raw
`m*v²/2` from serialized velocities need not reproduce reported kinetic energy.
Coordinates and physical units follow the
native file/metadata: timestep is ps, cutoff nm, temperature K and pressure bar.
A minimized or serialized System is not completed dynamics; finite results do not
establish a valid force field, equilibrated ensemble or converged study.

## Cancellation and checkpoint recovery

Cancel with `POST /v1/runs/{run_id}/cancel` or `md_run_cancel`. Resume with
`POST /v1/runs/{run_id}/resume` or `md_run_resume`, selecting only authorized,
compatible regions/GPUs. Use verified owner-bucket checkpoints after the source
writer stops; preserve owner, version, settings and the original cumulative
1,209,600-second deadline across attempts. A new submission is not continuation.

Compatible native binary checkpoint loading preserves stochastic state when it
succeeds. Portable State recovery restores positions, velocities, box, time and
step, without the previous RNG stream. Its deterministic fresh seed derives from
verified checkpoint/State/phase/step lineage; metadata reports
`recovery:"portable-state"`, `random_seed_mode:"portable-lineage-stream"`, actual
seed/lineage and `stochastic_state_preserved:false`. The requested seed is unchanged.
A subsequent compatible binary checkpoint retains that derived stream. Do not
promise cross-GPU bitwise equivalence or globally collision-free seeds.

After completion, cancellation, failure or timeout, writers stop and final upload
is retried for at most 300 seconds. Exact owned scratch/backing storage is then
deleted even if export failed. Report unsynced tail loss and continue only from
the last verified bucket checkpoint; stopped scratch is not retained indefinitely.

## Scientific and use-rights limits

Use the pinned [OpenMM scientific source](https://github.com/openmm/openmm/tree/b399af4725573963b46d6c1083fdcf7a37615857)
for native meanings. Commercial service clearance remains pending dependency/
notice and HECBioSim source-parameter rights reconciliation. OpenMM core licences
do not clear every input dataset; an example path is not a data licence. Use only
inputs/parameters you are authorized to provide. This skill grants no licences,
extra resources, access to another owner or blanket scientific validity.
