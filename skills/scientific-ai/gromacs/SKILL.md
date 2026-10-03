---
name: gromacs
description: Prepare, submit, resume and analyze GROMACS molecular-dynamics workflows on Scientific AI. Use for NVIDIA-packaged single-GPU MD, Colvars/PLUMED enhanced sampling, separately identified single-node or multi-node multi-GPU MPI runs, independent replicas, free-energy windows, trajectory analysis and native checkpoint recovery. Check the live App's qualified capabilities; MD is not docking pose search.
license: Apache-2.0
---

# GROMACS on Scientific AI

For model execution, read `scientific-gateway`. App ID: **gromacs**. This is the NVIDIA NGC
GROMACS HPC distribution behind the existing durable scientific-batch API,
not an NVIDIA NIM HTTP API, a folding neural network, or a docking engine.
Installing this skill does not establish that a particular runtime is released.
Read its live schema and qualification limitations before promising a workflow.
The separate **gromacs-mpi** App uses an upstream external-MPI build, not the
NVIDIA engine binary. Select it for a requested multi-GPU workflow or a matched
external-MPI baseline, using a shape accepted by the caller's live schema; more
GPUs can be slower and more expensive for small systems.

## Match the current request

- For force-field recommendations or small-molecule parameterization, read
  [ligand parameterization](references/ligand-parameterization.md). An advisory
  question does not authorize parameterization or require a simulation protocol.
  For OpenFF execution, load the dedicated `openff` skill, not a generated ad-hoc script.
- For a coordinate inventory, inspect the file and report its contents; do not
  launch MD, install packages, or add an unsolicited preparation study. In the
  Scientific AI workbench, `inspect-mmcif.py` provides measured mmCIF inventory.
- Establish the full protocol below only when preparing or running a simulation.

## Establish the scientific protocol

Identify supplied files, question, system composition, force field/water model,
protonation and ligand parameters, ensemble, temperature/pressure, timestep,
duration, replica seeds and required analyses. Prefer the customer's prepared
TPR/topology/MDP. When these choices are missing, ask which scientific choices
to make; do not quietly select settings and describe them as industry standards.
Operational defaults and scientifically valid sampling are different things.

- `pdb2gmx` handles supported residues, not arbitrary ligand parameterization.
  A predicted fold or docking pose is not a fully parameterized MD system.
- Docking uses a separate App such as DiffDock. Preserve the selected pose,
  molecule identity, protonation, charges and topology provenance before MD.
- Run preparation → minimization → appropriate equilibration → production →
  analysis explicitly. Use `grompp` checks; never suppress warnings with
  `-maxwarn` merely to make a run succeed.
- Independent replicas need distinct deliberate seeds. Reusing the same
  checkpoint or process snapshot is continuation, not independent sampling.

## Submit through the existing client

1. Read `get_model_schema(model_id="gromacs", protocol="scientific-batch-v1")`.
   Use its exact typed tool, operations, parameter schema and input artifact
   contract. The initial operation is `run-workflow`, with typed tool
   `submit_gromacs_workflow`; discovery remains authoritative.
2. Put every required input in one directory: coordinates, topology plus all
   includes, MDP/TPR, index groups and optional `.cpt`. Paths inside the archive
   are relative. Do not include credentials, symlinks, another tenant's files
   or unnecessary results. Use [the bundle helper](scripts/make-input-bundle.py)
   to create a deterministic gzip tar outside the input directory. It prints
   the actual digest and byte count; never invent those values.
3. Save a parameter JSON document separately. Start with
   [prepared TPR parameters](examples/prepared-tpr.json), replacing filenames
   with inspected inputs, or [explicit preparation](references/workflows.md).
   This is the model parameters document, **not** a scientific-run envelope.
4. Use the installed scientific-batch client or the durable study executor
   from `scientific-batch`. The published source role is `gromacs-inputs`,
   semantic type `gromacs-input-bundle/v1`, media type `application/x-tar`,
   compression `gzip`. Verify these against discovery before submission.
   The client uploads the file, finalizes the canonical input manifest and
   submits once with a stable idempotency key. Do not paste archive bytes into
   a tool call or invent artifact IDs.
5. Save the operation ID and receipt directory. Queued work is not a failure
   and client disconnect is not cancellation. Resume observation of the same
   operation; do not submit duplicates. A `gromacs` campaign can contain multiple
   independent one-GPU jobs. A `gromacs-mpi` request is one simulation with
   `nodes × gpus_per_node` GPUs, not that many independent replicas. Both may
   wait for shared capacity. See [MPI shapes and interfaces](references/mpi.md).

For a direct client, the installed command shape is:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model gromacs --tool submit_gromacs_workflow --operation run-workflow \
  --source /workspace/md/input.tar.gz --parameters /workspace/md/parameters.json \
  --entry-name gromacs-inputs --semantic-type gromacs-input-bundle/v1 \
  --media-type application/x-tar --compression gzip \
  --output /workspace/md/receipt --idempotency-key md-study-replica-01 \
  --display-name 'MD study replica 01'
```

Authentication comes from the configured client environment. The legacy
`/opt/bionemo` installation path is not a separate product/server name. In
LibreChat prefer the durable study executor so observation survives disconnect.

## Parameters and native commands

The versioned parameter schema has `jobs`: independently scheduled named jobs
with ordered named `steps`. Each step selects a supported native `command`,
explicit `args`, optional `stdin` group selections, relative `directory` and
`expected_outputs`. No shell, executable path or environment injection is
accepted. Select groups by inspecting the system, not by guessing group numbers.
For multiple trajectory parts, the explicit argument `{"files":"md.part*.xtc"}`
expands files without a shell. A literal `*.xtc` string does not do that.

The `gromacs` shape is one GPU, one thread-MPI rank, up to eight CPU threads.
Native automatic offload is the default. Do not force PME/update onto the GPU
without checking algorithm compatibility and a matched-system benchmark.
For enhanced sampling or distributed execution, read
[the advanced workflow contract](references/advanced.md). PLUMED uses the typed
`plumed_input` field, not a raw `-plumed` flag. Multi-node uses its own App and
schema. The MPI contract supports `nodes` and `gpus_per_node`; `threads` remains
per rank. Discover the deployed bounds, not an old one-GPU-per-node assumption.
Do not request replica exchange, CP2K or NNPot through undocumented
flags; a compiled dependency alone is not a hosted capability.

Operational defaults: five-minute local checkpoints and remote segments,
six-hour per-job wall budget, 4 GiB output budget, and customer-bucket export.
Read the live bounds before changing `threads`, `segment_minutes`,
`checkpoint_minutes`, `max_wall_seconds`, `max_output_bytes`,
`output_destination` or `output_prefix`. Output cadence is controlled by the
customer's MDP/TPR and is not silently rewritten. Platform/bucket quotas still
apply; a larger request budget does not purchase or create storage. The 4 GiB
default can be too small for million-atom systems: inputs, repeated final
coordinates, checkpoints, trajectory parts and joined outputs all consume the
workspace budget. Estimate them before submission; see the
[large-output budget guidance](references/mpi.md#output-budget-and-failure-diagnostics).

## Restart, storage and results

Native `.cpt` continuation and CUDA/CRIU snapshots are distinct. Do not claim
GPU snapshots are enabled unless the exact runtime's evidence says so. The
runner segments finite MD, commits closed files and a manifest, and continues
with native checkpoints and `-noappend`. Failed-attempt recovery uses the last
committed generation of the same operation/job; it can replay uncommitted work.
After cancellation the final uncommitted generation may not be recoverable.

`-noappend` produces `.partNNNN` files. Preserve them all. Use `trjcat` and
`eneconv` deliberately and check frame times/overlap; never concatenate binary
files with shell `cat`. The runner exposes the latest final coordinate at the
normal `-c`/`-deffnm` path for a subsequent explicit `grompp` step.

Customer export resolves the submitting user's assigned bucket; a payload
cannot select someone else's bucket. Under the chosen prefix, operation and
job IDs identify content-addressed `objects/<sha256>` and immutable
`attempt-NNN/checkpoint-NNNNNNNN.json` manifests. The manifest maps original
names to object keys and byte hashes. These remain until customer deletion or
bucket lifecycle expiry. They are not files mounted live by the GROMACS engine.

Download the completed platform result and every promised artifact using the
verified file helpers. The native workflow result artifact records exact inputs,
runtime, commands, checkpoint generations, step outcomes, file hashes and available
performance. The outer batch client's `output-NN.artifact` names are transport
names, not native file names. The installed client materializes verified native
paths by matching hashes into `native/result-00/` and writes `native-files.json`
with per-file hashes and workspace links. Use its returned `native_outputs`;
never guess mappings by array order or rename raw transport artifacts. Existing
completed runs can be recovered with `--recover-operation-id` into a new directory.

For a timing/benchmark report in the Nebius workbench, use the installed
deterministic reporter **once after recovery** instead of writing ad-hoc Python
or repeatedly printing the result JSON. Supply the user's actual repeat count:

```sh
/opt/scientific-client/bin/python /opt/bionemo/report-native-md.py \
  --receipt-dir /workspace/md/receipt --output-dir /workspace/md/timing-report \
  --expected-repeats 3
```

It reads either normal or recovery receipts, verifies native result/log hashes,
and writes `native-timing-report.json`, `native-timings.csv` and
`native-timing-report.md`. Read its compact JSON response: `complete: false`
and exit 2 mean missing measurements/repeats, not success. A checkpoint's
absolute step number is not an executed/durably completed work count; missing
counts stay unknown. Deliver the native-MD receipt directory and these report
files with the existing result-delivery tool; do not rename/copy receipts or
rewrite a successful report. Extra scientific analysis can be a separate step.
On a client without this command, the verified native schema below is the
portable contract; this bundle alone does not install the workbench runtime.

The receipt's outer `result.json` is the **platform envelope**, not the native
GROMACS workflow result. Follow `native_outputs.results[].source_result_file`
from the verified receipt/helper response; older clients can locate the artifact
with semantic type `gromacs-workflow-result/v1` in `receipt.json.verified_artifacts`.
Inspect the native document's
actual `commands` and `completed_steps`, and check expected run/repeat counts.
Do not read nonexistent `steps` from the envelope and produce an empty table.
Follow the [benchmark evidence checklist](references/mpi.md#read-native-results-before-reporting-a-benchmark)
for native timings, missing metrics and recovered studies.
Read native command logs and result metadata, not only the outer operation state.
An inventory/budget failure may retain committed checkpoints and bounded error
logs; `inventory_complete=false` is not a complete scientific delivery.

Report simulation duration/steps, atoms, trajectories/frames, temperature and
energy sanity checks, warnings, achieved ns/day, wall and queue time separately.
For free energy report lambda schedule, estimator, equilibration discard,
overlap, uncertainty and convergence limitations. A terminal `succeeded` run
proves execution and verified outputs, not equilibration or a valid biological
conclusion. Do not treat the short tutorial fixtures as production science.

## References and tested examples

Read [workflows and source documentation](references/workflows.md) for native
command recipes, free energy, extension boundaries and official references.
When a protocol fails, preserve its operation ID, diagnostics and inputs; fix
the scientific cause instead of suppressing it or changing models silently.
