# Training, evaluation, export and dataset tools

These entrypoints call the pinned Isaac for Healthcare `i4h_rl` and
`i4h_tools.dataset` implementations. A project supplies its own workflow,
scene/robot descriptors, RL profile/config, recordings, checkpoints and patient
twin. There is no workflow-name or example-data eligibility list.

The main recipe prepares `project.tar`: `project.json`, optional `overlay/`
merged into the SDK, and arbitrary `data/`. It passes the resulting SDK root,
extracted archive root and resolved workflow here. Checkpoint, dataset and
patient-twin paths stay relative to the archive. `training.profile` is relative
to the effective SDK; absent it, upstream `rl/profiles/<workflow>.yaml` is used.
Additional project Python source directories are passed with `--python-path`.

## Runtime build

From the parent recipe directory, use the immutable Arena image from your own
registry. NVIDIA simulator/component/asset licenses and dataset/model licenses
still apply. The existing license acceptance of an operator does not confer a
license on another user.

```bash
docker build -f training/Dockerfile \
  --build-arg ISAAC_ARENA_IMAGE="$YOUR_ARENA_DIGEST" \
  -t "$YOUR_REGISTRY/isaac-training:candidate" .
```

`upstream-locks.json` binds upstream revision
`5b430a6d8d8c9cccc547b05b5e079d22b08ade9e`. RSL-RL uses Arena's Python3.12,
Torch2.10/CUDA12.8 and RSL-RL5.0.1 plus the hash-locked lightweight RL
dependencies. It does **not** install `rl[dev]` or replace simulator Torch with
the RL test environment's CPU Torch. Packaging26.0 remains at Arena's pin;
OmegaConf intentionally changes from Arena2.3.1 to the RL package's required
2.3.0. The owning `i4h-train-rl` entrypoint is installed without dependency
resolution after these explicit pins. Other Arena dependencies remain in place.

Dataset operations use a separate Python3.11.15 environment and the upstream
`tools/dataset/uv.lock`: NumPy1.26.4 and LeRobot commit
`483be9aac217c2d8ef16982490f22b2ad091ab46`. That lock currently resolves its own
Torch2.13; it never alters Arena's environment. Conversion runs on CPU. Managed
Python is installed under `/opt/python`, accessible to the unprivileged runtime
user. Image
build/import and real training qualification are separate gates; a prepared
Dockerfile or CPU preflight is not evidence of successful GPU training.

## Invocation and parameters

```bash
python -I training/run.py --operation train \
  --input-dir /work/project --sdk-root /work/effective-sdk \
  --output-dir /work/output/training --parameters-file /work/parameters.json \
  --workflow my_authored_workflow
```

The parent runtime uses the same function through `run_operation()` and embeds
its returned summary in `result.training`. It retains all produced files in
the existing artifact flow. `--prepare-only` performs CPU input/profile
preflight and never starts a simulator/trainer. Run each request in a fresh
output directory. The platform owns cancellation and resource limits; this
wrapper creates no scheduler or detached session and performs no automatic retry.

The nested option schemas are `training.schema.json` and
`dataset-options.schema.json`. Omitted RL values retain the upstream profile
defaults. Explicit epochs, environments, evaluation episodes and overrides are
passed unchanged. Example parameters for a user-owned training profile:

```json
{"workflow":"my_authored_workflow","training":{"epochs":100,"num_envs":16}}
```

- `train`: real upstream RSL-RL PPO; preserves checkpoints, agent config,
  TensorBoard and run metadata. The result inspects finite learned tensors and
  the recorded training iteration. A valid checkpoint is not a reward guarantee.
- `evaluate`: requires outer `checkpoint`; validates the requested episode count,
  per-episode outcomes and aggregate metrics. Unsuccessful episodes remain
  unsuccessful; the wrapper never changes a task outcome to pass a gate.
- `export`: requires outer `checkpoint`; RSL-RL evaluates one episode in the
  simulator, then exports TorchScript. This is a GPU operation, not just a CPU
  format conversion. Policy tensors, manifest and evaluation output are checked.
- `dataset-inspect`: outer `dataset` is one recording or a directory. Directory
  discovery uses HDF5 signatures, not filenames. It runs upstream inspection and
  reports actual episodes, actions/states, cameras, segments and success flags.
- `dataset-convert`: uses the same inputs plus `dataset_options.robot`. It calls
  upstream HDF5-to-LeRobot conversion, preserving user-selected filters, frame
  rate, codec, task and anatomy. The result checks metadata totals, finite Parquet
  values and complete video decoding. No data is uploaded to Hugging Face.

RSL-RL resume, evaluation video and evaluation overrides are unsupported by this
upstream launcher and produce its explicit errors. Empty/filtered recordings,
incompatible descriptors, missing anatomy and invalid checkpoints fail with the
specific cause; partial outputs and the complete execution log are retained.

RLinf is dispatched through its real upstream backend when a compatible
separately provisioned model environment is supplied with
`training.runtime_python` (and, when needed, `training.sim_runtime_python`).
The Arena image does not bundle RLinf, GR00T or OpenPI model environments/weights.
The initial RLinf policy comes from outer `checkpoint`; resume and export retain
their upstream contracts. External policy runtime availability and scientific
qualification must be recorded independently. Offline supervised fine-tuning
remains the owning upstream task project's entrypoint; this RL wrapper does not
pretend PPO is a replacement for it.

The [policy-environment inventory](policy-environments.md) distinguishes
in-process RSL policy tasks from isolated GR00T/OpenPI services and records
their locks and checkpoint requirements. Explicit `training.runtime_python`
and `training.sim_runtime_python` selections must exist and be executable;
the bridge rejects invalid selections instead of silently choosing a default.
Omitted/null values retain upstream defaults.

RSL training, evaluation and export start their actual upstream script/module in
a child bootstrap that uses the same project imports and pinned local asset
mapping as simulation. A process-local Isaac Lab startup hook merges the
supported private `--portable-root` option after upstream argument parsing;
other Kit arguments and trainer settings are preserved. An explicit conflicting
Kit root fails instead of being overwritten. The portable parent supplies its
invocation directory; a standalone call without that environment receives a
private Kit directory beside its output directory. Complete child argv, asset
mapping and startup receipts remain operator diagnostics. No global subprocess
module or external RLinf environment is modified.

## Outputs and qualification

`training-result.json` records operation, source/profile hashes, exact metrics,
elapsed time and the full file inventory. `training-validation.json` contains
the domain checks; `training-execution.log` retains stdout/stderr, and
`artifacts/` contains unchanged upstream checkpoints, exports or converted data.
`operator_diagnostics` explicitly identifies raw logs, expanded requests and
full native reports. The hosted parent must retain those in operator storage,
exclude them from customer scientific archives and expose only the curated
science summary. Portable local users own and can inspect the complete directory.
Failures write `training-error.json` and, where available,
`training-engine-error.json`. No arbitrary file-size limit or fixture hash is
used; the existing platform grant/output budget still governs delivery.

The earlier finite SO-ARM simulator demonstrations do not qualify this training
or dataset surface. On 27 October 2026, actual CPU conversion passed in the frozen
dataset environment: an independently authored robot descriptor, two episodes
with different success outcomes, two camera streams, and exact action/state
preservation in Parquet. A renamed recording with explicit 24 fps, three leading
frames skipped and successful-only filtering also passed. All videos were fully
decoded and every reported artifact hash checked. Non-finite actions produced a
specific failure without a successful result or converted dataset.

A separate finite L40S provider Job subsequently executed actual RSL-RL PPO
training, two evaluation episodes and TorchScript export with one simulator
evaluation episode on image
`sha256:bd5110c3991b74ec670b2c8a20688fbad440e3108b20e24e86b2c975adc9c400`.
The final checkpoint recorded iteration 2; all eight learned parameter tensors
changed, remained finite, and matched the exported policy. Evaluation succeeded
in 0/2 episodes, and export evaluation in 0/1: execution and artifact integrity
passed, but learned task success or convergence was not demonstrated. Complete
delivery hashes and independent CPU artifact checks passed.

This RL evidence is distinct from the later marker-closure image's surgical
simulation/replay proof; RL was not rerun on that image. External policy stacks,
expanded Native REST/MCP delivery, cancellation/recovery, interactive sessions,
GPU fallback and sustained capacity remain separate qualification gates.
See [the scoped qualification record](qualification.json).
