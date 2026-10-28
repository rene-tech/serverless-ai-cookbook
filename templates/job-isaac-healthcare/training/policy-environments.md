# Policy environments and checkpoint requirements

This inventory covers the graph-declared task projects in
[Isaac for Healthcare revision `5b430a6d8d8c9cccc547b05b5e079d22b08ade9e`](https://github.com/isaac-for-healthcare/i4h-workflows/tree/5b430a6d8d8c9cccc547b05b5e079d22b08ade9e).
Discovery, an installed interpreter, and successful learned-policy execution are
separate facts. Authored workflows can declare additional task projects; the
table is an inventory of this SDK revision, not an execution allowlist.

The 27 October 2026 CPU inspection used the built general-runtime image with
local OCI configuration ID
`sha256:a1e28e9f6be0d68266faa7ee30834667b1f05db08f9a41ff88349b8a4db390ed`.
This is an image ID, not a published registry manifest reference. Inspection ran
as UID 10001 with a read-only root, no network, and no GPU devices. All eight
task pyprojects, eight locks, and 31 task manifests matched the pinned source.
These checks did not start a policy server, train a policy, or run a simulator.

## Installed and missing environments

Upstream determines task execution from the manifest: an `impl` class runs in
the simulator process; a remote task has a `BackendSpec` and its own interpreter.
The recipe preserves this distinction. Missing remote environments produce an
explicit error rather than falling back to Arena or another policy generation.

| SDK project | Declared tasks | Runtime and interpreter | Inspected image |
| --- | ---: | --- | --- |
| `tasks/basic` | 16 | In-process, `/opt/i4h/arena/.venv/bin/python` | Installed in Arena |
| `tasks/ik` | 4 | In-process, Arena | Installed in Arena |
| `tasks/teleop` | 2 | In-process, Arena | Installed in Arena; device/stream readiness is separate |
| `tasks/rsl_rl` | 1 | In-process, Arena | Installed; exported-policy module imports |
| `tasks/gr00t_n15` | 2 | `/opt/i4h/tasks/gr00t_n15/.venv/bin/python` | Environment and GR00T source absent |
| `tasks/gr00t_n16` | 2 | `/opt/i4h/tasks/gr00t_n16/.venv/bin/python` | Environment and GR00T source absent |
| `tasks/gr00t_n17` | 3 | `/opt/i4h/tasks/gr00t_n17/.venv/bin/python` | Environment and GR00T source absent |
| `tasks/openpi_pi0` | 1 | `/opt/i4h/tasks/openpi_pi0/.venv/bin/python` | Environment and OpenPI source absent |

The inspected Arena interpreter is Python 3.12.13 with Torch 2.10.0+cu128,
NumPy 2.5.1, RSL-RL 5.0.1, and Zenoh 1.9.0. It imports the actual
`i4h_tasks.rsl_rl.ultrasound_probe_reach` module. The recipe's installed
inspection of `ultrasound_probe_reach` in `policy` mode produced a valid graph,
the RSL controller, and **no remote backends**. An absent
`tasks/rsl_rl/.venv` is therefore expected. No interpreter alias or fallback is
needed for this task. An actual compatible exported checkpoint is still needed.

The lightweight `i4h-workflows-rl` package and its `i4h-train-rl` entrypoint are
installed in Arena. `train`, `evaluate`, and `export` use that package's owning
RSL-RL backend; these operations are distinct from graph policy inference.
The `rl/uv.lock` development extras must not replace Arena's simulator Torch.

## Isolated remote dependencies

Each remote project owns its `pyproject.toml` and `uv.lock`. All four require
Python 3.11 and NumPy 1.26.4 in this lock generation. Their differences are
material; installing them into Arena, or substituting one GR00T generation for
another, does not provide the requested environment.

| Project | Locked compute stack | Required third-party source |
| --- | --- | --- |
| `gr00t_n15` | Torch 2.9.0+cu130, Transformers 4.51.3 | `Isaac-GR00T-1.5` at `17a77ebf646cf13460cdbc8f49f9ec7d0d63bcb1` |
| `gr00t_n16` | Torch 2.9.0+cu130, Transformers 4.51.3 | `Isaac-GR00T-1.6` at `e8e625f4f21898c506a1d8f7d20a289c97a52acf`; pinned IsaacLab-Arena configuration sources |
| `gr00t_n17` | Torch 2.9.0+cu130, Transformers 4.57.3 | `Isaac-GR00T-1.7` at `4b1dca9d88d2a0b9ea5a65aa61c82ff89f5c4f0e` |
| `openpi_pi0` | Torch 2.12.1+cu126, JAX/JAXlib 0.5.3, Transformers 4.48.1 | `openpi-581e07d` at `581e07d73af36d336cef1ec9d7172553b2332193`; LeRobot at `6674e368249472c91382eb54bb8501c94c7f0c56` |

Use the pinned SDK's `third_party/setup.sh` for the chosen project: it applies
the corresponding upstream patches as well as checking out source. A build
extension for N1.7, for example, has this shape:

```dockerfile
RUN /opt/i4h/third_party/setup.sh tasks/gr00t_n17 \
    && UV_PROJECT_ENVIRONMENT=/opt/i4h/tasks/gr00t_n17/.venv \
       uv sync --frozen --no-dev --python 3.11.15 \
         --project /opt/i4h/tasks/gr00t_n17
```

This is an optional build pattern, not an installed or GPU-qualified extension
of the inspected image. Build it into your own immutable image and verify its
actual imports, source, dependencies, checkpoint loading, and GPU behavior.
N1.5 and N1.7 include a default `rl` dependency group; `--no-dev` preserves it.
An inference-only `--no-group rl` build must not be described as an RLinf host.
Project-local `.venv` paths must remain available in the merged SDK used for
execution. A user-authored remote project follows the same graph declaration,
installed interpreter, entrypoint, and dependency-lock contract.

## Weights and auxiliary assets

The general-runtime recipe does not install the remote policy checkpoints.
Simulator assets are separate from learned weights. Supply a complete local
checkpoint through the project's `checkpoint` parameter or localize an exact,
licensed snapshot during image preparation. Record its revision and file
hashes; a model repository name alone is not an immutable checkpoint.
Keep any required download credentials in your preparation environment, not in
project archives, public examples, or runtime arguments.

| Task | Required policy content |
| --- | --- |
| `rsl_rl/ultrasound_probe_reach` | User-trained/exported TorchScript actor; 34 observation values and 6 actions. A checkpoint directory resolves to `policy.pt`; a supplied file may have another name. No default checkpoint is declared. |
| `gr00t_n15/scissor_pick_and_place` | Complete `nvidia/SO_ARM_Starter_Gr00t` snapshot or compatible local checkpoint, with its room/wrist camera metadata. The task manifest does not pin a revision. |
| `gr00t_n15/assemble_trocar` | `nvidia/GR00T-N1.5-RL-Rheo-AssembleTrocar` at `b54e14286ed3f8392d614741748739e09c7fefe4`, or a compatible local checkpoint; retain G1 preprocessing/configuration assets. |
| `gr00t_n16/locomanip_push_cart` | `nvidia/GR00T-N1.6-Rheo-Sim-PushCart` at `0e24b9b225da4a2cff53049eb8b6e57f435814ec`, or a compatible local checkpoint. |
| `gr00t_n16/locomanip_tray_pick_and_place` | `nvidia/GR00T-N1.6-Rheo-PickNPlaceTray` at `76a205040fc8489de91487c82e51eecb82f7d250`, or a compatible local checkpoint. |
| `gr00t_n17/scissor_pick_and_place` | Complete `nvidia/SO_ARM_Starter_Gr00tN17` snapshot or compatible local checkpoint; no revision is pinned in the manifest. |
| `gr00t_n17/catheter_navigation` and `catheter_navigation_arm` | Caller-provided compatible catheter checkpoint. Upstream explicitly declares no published checkpoint; preserve its catheter/C-arm action space and embodiment metadata. |
| `openpi_pi0/ultrasound_liver_scan` | Complete `nvidia/Liver_Scan_Pi0_Cosmos_Rel` snapshot or compatible local checkpoint. Include exactly one `assets/<asset_id>/norm_stats.json` normalization asset for the explicit-checkpoint path and the `robotic_ultrasound` configuration. No revision is pinned in the task manifest. |

G1 locomotion and whole-body-controller assets, joint maps, processor/tokenizer
files, normalization statistics, and any checkpoint-referenced base-model
assets must be retained with the selected workflow. An existing simulator asset
cache does not prove those policy-specific assets are complete. Upstream remote
loaders contain download paths; the recipe's offline execution requires local
content and does not treat a blocked download as a valid policy run.

## RLinf, dataset tools, and explicit interpreters

RLinf is not a graph backend installed by the general image. The pinned SDK's
`assemble_trocar` RL profile selects the N1.5 model environment; both
endoluminal RL profiles select N1.7. These additionally need the patched
`RLinf-a4b6abe` checkout at
`a4b6abe205d7942f45cf3e8843c3e72ce818729d`, compatible RL dependencies, the
simulator environment, and the initial policy checkpoint. The inspected image
has no RLinf checkout or importable module. An arbitrary Python executable
does not satisfy those dependencies; upstream preflight remains authoritative.

The dataset environment is separately installed at
`/opt/i4h/tools/dataset/.venv/bin/python`: Python 3.11.15, NumPy 1.26.4,
Torch 2.13.0, and the dataset lock's LeRobot source. It is not a substitute for
Arena, GR00T, or OpenPI. See [the training and dataset contract](README.md).

Explicit `training.runtime_python` and `training.sim_runtime_python` must name
existing executable interpreters. The bridge rejects a missing or
non-executable selection before upstream dispatch instead of allowing the
upstream candidate search to choose another environment. It preserves the
virtualenv executable's symlink path. `null` retains the owning upstream
defaults; validation does not install packages or broaden a backend's support.
This strict-selection source change was CPU-checked against the inspected
image's dependencies; it requires inclusion in a successor image.

## Task lock identities

These SHA-256 values bind the actual inspected `tasks/<project>/uv.lock` files:

| Project | SHA-256 |
| --- | --- |
| `basic` | `d9cfff2429ebd6aa5f6b6ef44c6e3f0125f2fd4ccd8651a0199cf01fa3061ea3` |
| `ik` | `b82f1384c1c65f056cb69a74b935997cf8640f40b2210e7093db84727781fef5` |
| `teleop` | `18dd000b7aa1c258bfc2a52d42e55d988d2110f5d11d1fb40207004da71382cc` |
| `rsl_rl` | `3016ed83656ba0c6ba934433d7fbf55f763319f73bb9f7c3ddd6a4ffb1dd7477` |
| `gr00t_n15` | `c14d182ad1241eefc53ad48005ca7f74ec5b2f3b073db3e36e4eb57c7b14a999` |
| `gr00t_n16` | `2266406c2c950c32f2f1e2b41beba901222acfcdcb700107e88a14f82210e4ae` |
| `gr00t_n17` | `df9a8c6b4026357fecc30bb1d9ad3bfb0a25a806eae516536b32e4614535a8b3` |
| `openpi_pi0` | `1f97e94cbe86f39db8a211cdfe1e2fdc778819b516dd5c009dc1df386d9663a2` |

The Arena, lightweight RL, and dataset lock identities remain in
[`upstream-locks.json`](upstream-locks.json). CPU discovery/import checks do not
establish learned-policy accuracy, GPU compatibility, training convergence,
interactive media readiness, sustainable capacity, or hosted availability.
