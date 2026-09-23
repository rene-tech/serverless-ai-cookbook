---
name: namd
description: Prepare, submit, resume and analyze NVIDIA-packaged NAMD molecular-dynamics workflows on Scientific AI. Use for psfgen preparation, native Tcl protocols, finite GPU-resident or GPU-offload dynamics, independent replicas, trajectories, native checkpoint and Colvars state handling. Verify exact-runtime feature and restart qualification before promising enhanced sampling or free-energy workflows.
license: Apache-2.0
---

# NAMD on Scientific AI

Read `scientific-gateway`, then the [shared MD transport](../scientific-batch/references/native-md.md).
App ID: **namd**. The selected engine is NVIDIA's NGC NAMD 3.0.2 HPC container,
not an NVIDIA NIM HTTP API. A skill does not grant model access or establish
that the App or a particular workflow has passed customer qualification.

## Select the protocol deliberately

Identify the system, topology/coordinate and parameter files, protonation,
force field, water model, periodic cell, ensemble, thermostat/barostat, timestep,
constraints, run duration, seeds and required analysis. Ask about missing
scientific choices. A predicted structure or docking pose still needs compatible
MD parameters; do not assume `psfgen` invents arbitrary ligand force fields.

GPU-resident and GPU-offload modes have different feature/performance support.
Choose `gpu_mode` explicitly and keep it consistent with native `GPUresident`
configuration. More CPU threads or a forced GPU mode are not automatically faster.
Each job currently uses one GPU on one node. Independent jobs do not constitute
a multi-node simulation, replica exchange or an MPS deployment.

The current pinned binary predates upstream NAMD 3.0.3 correctness fixes.
GBIS and Colvars `spinAngle` are not qualified and are rejected by the current
App. Do not remove them from a customer's experiment to make it run. Request a
qualified runtime for those workflows. Other advanced functionality still needs
its own evidence; compilation alone is insufficient.

## Submit native files through the typed App

Discover `get_model_schema(model_id="namd", protocol="scientific-batch-v1")`.
Initially the operation is `run-workflow` and tool `submit_namd_workflow`.
Bundle complete relative-path inputs and use `namd-inputs` /
`namd-input-bundle/v1`, gzip `application/x-tar`. Follow the shared upload/client
workflow. Never pass a LibreChat filesystem path as a remote artifact ID.

[Managed-dynamics parameters](examples/managed-dynamics.json) illustrate the
parameter object only. They require the scientist's complete configuration and
inputs; duration and segment size are illustrative, not scientific defaults.
Each job has ordered steps with `id`, `config`, `directory` and `mode`:

- `prepare`: bundled `psfgen` executes the supplied preparation Tcl script.
  Provide explicit expected topology/coordinate outputs and inspect its warnings.
- `native`: execute a complete native NAMD Tcl protocol, including minimization
  or staged run control. Explicit expected outputs are required. Recovery is at
  completed step boundaries, not arbitrary Tcl interpreter state.
- `dynamics`: configuration-only Tcl plus finite `steps`, `segment_steps` and
  `output_prefix`. The runner owns run control and closes/commits each segment.
  Keep all scientific settings and output cadence in the supplied configuration.

`config` is a filename inside `directory`; NAMD changes into the configuration
directory. In managed dynamics omit native `run`, `minimize`, `startup`,
`numsteps`, `benchmarkTime`, `firsttimestep`, `outputName`, `restartName`, and
explicit DCD/XST filenames, because the runner sets these. For complete native
run control choose `native`, not a malformed managed configuration.

## Continue without losing scientific state

Native `.coor`, `.vel` and `.xsc` must describe the same checkpoint. For external
managed continuation, `first_step` must match the XSC timestep. Use
`if {!$fs2_restart}` around fresh temperature/velocity and cell initialization.
Enabled Colvars also needs the matching bias state; never reset it just because
a run restarted. `initialize_colvars: true` deliberately starts a new bias from
an unbiased checkpoint, not a workaround for a missing biased state.

Preserve every `prefix.partNNNNNN.*` trajectory/log/bias segment and final native
aliases. Validate frame times and boundaries before combining trajectories.
Stochastic thermostat restart is not promised bitwise: native coordinate/cell
files do not serialize every RNG. Seeds are retained and recorded, not silently
rewritten. Independent replicas need deliberately distinct sampling seeds.

Colvars continuation must verify the actual complete bias state, not only its
timestep. Earlier qualification found missing explicit hill history, and the
successor wrapper corrects recognition of native gridded-state syntax. Exact-r5
qualification now includes ungridded and gridded `keepHills` trajectories plus
fresh-pod continuation with preserved hills. Confirm the deployed image and
published workflow evidence before using this capability; those tests do not
qualify every Colvars method. Switching between gridded and ungridded protocols
is a scientific change, never an automatic recovery workaround.

## Results and advanced work

Return verified trajectories, native restart/bias state, logs, manifests and
links to an interpretable report. Check atom count, every expected frame,
finite energy/temperature/pressure, simulation duration, drift appropriate to
the ensemble and continuation consistency. Quantify ns/day for a single
trajectory separately from aggregate replicas and queue/export overhead.

For Colvars, ABF, metadynamics, umbrella sampling, FEP/TI or Tcl extensions,
first verify the chosen engine mode and published capability matrix. Retain
all bias/derivative histories and analyze sampling, overlap and uncertainty.
Successful execution is not a free-energy convergence claim. Native restart
does not establish persistent CUDA process snapshot support.

Read [version-specific source documentation](references/sources.md). Preserve
failed evidence and ask before changing the customer's scientific protocol.
