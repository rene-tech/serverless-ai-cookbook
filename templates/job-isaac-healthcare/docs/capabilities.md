# Capability ownership at pinned i4h v0.9.0

This is a source/environment assessment, not a workflow allowlist. Every new image
and workload needs its own scientific and lifecycle qualification.

The source is pinned to [5b430a6d](https://github.com/isaac-for-healthcare/i4h-workflows/tree/5b430a6d8d8c9cccc547b05b5e079d22b08ade9e).
`DESIGN.md`, `run.sh`, `arena/i4h_arena/cli.py`, the loader/registry and per-project
`pyproject.toml`/`uv.lock` are authoritative. CPU discovery found these 16 authored
modules with no registry errors; customers may add arbitrary specialties/names.

| Workflow | Authored modes | Scene cap / Hz |
|---|---|---|
| `assemble_trocar` | `idle`, `policy`, `replay` | 250 / 30.0 |
| `endoluminal_navigation` | `demo`, `idle`, `policy_n17`, `replay`, `teleop`, `validate_fluoroscopy` | 600 / 30.0 |
| `endoluminal_navigation_arm` | `demo`, `idle`, `policy_n17`, `replay`, `teleop` | 600 / 30.0 |
| `locomanip_push_cart` | `idle`, `policy`, `replay`, `teleop` | 1800 / 30.0 |
| `locomanip_tray_pick_and_place` | `idle`, `policy`, `replay`, `teleop` | 1500 / 30.0 |
| `scissor_pick_and_place` | `idle`, `policy`, `policy_n17`, `replay`, `rule-based`, `teleop` | 600 / 60.0 |
| `spread_tablecloth_g1` | `idle`, `replay`, `teleop` | 3600 / 30.0 |
| `spread_tablecloth_h2` | `idle`, `replay`, `teleop` | 9000 / 30.0 |
| `surgical_lift_block` | `idle`, `replay`, `rule-based` | 250 / 50.0 |
| `surgical_lift_needle` | `idle`, `replay`, `rule-based` | 250 / 50.0 |
| `surgical_lift_needle_organs` | `idle`, `replay`, `rule-based` | 250 / 50.0 |
| `surgical_reach_dual_psm` | `idle`, `replay`, `rule-based` | 150 / 30.0 |
| `surgical_reach_psm` | `idle`, `replay`, `rule-based` | 150 / 30.0 |
| `surgical_reach_star` | `idle`, `replay`, `rule-based` | 150 / 30.0 |
| `ultrasound_liver_scan` | `idle`, `policy`, `replay`, `rule-based`, `teleop` | 250 / 30.0 |
| `ultrasound_probe_reach` | `idle`, `policy` | 250 / 50.0 |

Caps above are base scene values; mode overrides remain authoritative. See
[machine-readable source audit](upstream-capabilities.json) for exact manifests.
The upstream default mode is idle. Mode names are authored, not restricted to
the familiar policy/rule-based/replay/teleop names.

| Capability | Owning entrypoint / environment | Current boundary |
|---|---|---|
| Scene/Task/Workflow discovery and lint | `i4h_engine.cli`; installed Arena Python3.12 | General v2 source and actual CPU project tests; no simulator claim |
| Simulation and demonstration recording | `i4h_arena.cli`; full Arena/Isaac6.0.1 env | General dispatch; new real scene/mode/image qualification pending |
| Replay | `i4h_arena.cli --mode replay`; original HDF5 | Only modes authored by a selected workflow; every requested recording index dispatched explicitly |
| RSL-RL train/evaluate/export | `i4h_rl.cli`, `rl/profiles/*.yaml`; Arena dependency environment | Source implementation in `training/`; trainer/project profile remains authoritative |
| RLinf online training | `i4h_rl.cli` + isolated RLinf trainer/simulator environments | Separate environment/checkpoints required; no import into incompatible Arena dependency stack |
| GR00T N1.5/N1.6/N1.7 inference and supervised training | `i4h_tasks.gr00t_n15/n16/n17.server:main` and `.train:main`; separate Python3.11 locks | Source present in original image, backend envs/weights were not installed there; build and qualify selected policy stack |
| OpenPI PI0 inference/training | `i4h_tasks.openpi_pi0.server:main` / `.train:main`; own Python3.11/JAX/Torch environment | Separate environment and checkpoint, graph-derived backend supervision |
| Dataset inspection/conversion | `i4h_tools.dataset.cli:main`; Python3.11/NumPy<2/LeRobot | General dispatch in `training/`; own locked environment and output validation |
| Demonstration augmentation | `i4h_tools.mimic.cli:main`; own `tools/mimic` env | Source/tool owner identified; dedicated invocation and real transformation qualification still required |
| Vision annotation/filtering | `i4h_tools.annotator.cli:main`; own env + user-owned OpenAI-compatible VLM service | External service/network/auth lifecycle must be explicit; not provided by simulation IPC |
| Cosmos export/import | `i4h_tools.cosmos.cli:main`; own environment + external Cosmos generation | Source/tool exists; generation service and transformed-data qualification remain separate |
| Patient digital twin preparation | `i4h_tools.patient_twin.cli:main`; Python3.12/nibabel/scipy/trimesh/USD dependencies | Source/tool exists; caller-owned medical data and generated geometry need their own validation |
| GUI/video and teleoperation | Isaac6.0.1 WebRTC + authored teleop tasks, `interactive/` | User requested authenticated GUI/teleop; live session/network/relay qualification pending |

The original portable image contains the complete pinned source tree and the
Arena environment, not every source subproject environment or checkpoint. The
old asset closure covered one scissor scene. The general build expands pinned
asset references; source presence alone is not offline asset availability.
The CPU USD composition gate proves selected asset values, variants, time samples
and pinned file/package bytes. It does not compile MDL or establish complete
material resource resolution. MDL dependency closure and real offline rendered
execution are separate gates; the earlier USD-only proof must not be promoted
to a complete renderer-closure claim.

The runner owns reset/step/render/record sequencing. Workflow modes build graphs;
Scene owns geometry/physics/sensors; Tasks own reusable behavior. Online RL has
its own trainer-owned vectorized stepping. Training must not be implemented as
a fake simulation mode. No blanket 600-step limit, six-joint shape or two-camera
assumption applies to the general interface.

Upstream simulator warnings observed in the old scissor proof included TGS,
unapplied mass/collision overrides, ScaleOrientation and muted USD diagnostics.
They remain limitations of that evidence, not proof of new scenes or physical
accuracy. Seed is applied at recorded reset/randomization; construction and
cross-GPU trajectories are not promised deterministic.

Local graph policy IPC uses Unix Zenoh router/client transport. An actual CPU
publish/receive probe succeeded while IPv4/IPv6/packet/vsock socket creation was
blocked by the retained offline filter. The first peer-mode probe did not receive
its message and was preserved; this is transport proof, not policy-model proof.
An operator may set `I4H_BUS_ROOT` to a short, private session directory. Each
invocation creates and removes only its own socket directory beneath that root;
the batch default remains `/tmp`.
Zenoh documents the transport in its [official implementation tests](https://github.com/eclipse-zenoh/zenoh/blob/main/io/zenoh-transport/tests/endpoints.rs).
