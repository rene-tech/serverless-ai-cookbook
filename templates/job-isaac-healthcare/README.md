# Isaac for Healthcare projects

This recipe exposes the pinned Isaac for Healthcare framework: discover and lint
workflows, execute finite simulations, record demonstrations, replay recordings,
and dispatch upstream RL and dataset operations. A project archive can add or
replace Scene, Task and Workflow source, manifests, configuration and assets.
Workflow names and modes are discovered from the project, not an example list.
The portable package has no private Scientific AI dependency or platform token.

**Generalization status:** this v2 source is under qualification. CPU tests have
exercised actual upstream discovery/lint with unseen authored workflows and
modified package source. A new immutable image and real multi-workflow GPU,
training, dataset and interactive qualification are still required. The earlier
published scissor image does **not** implement this v2 interface. Its retained
L40S/RTX, REST/MCP and provider passes apply only to that earlier finite workflow.
See [capabilities and owning entrypoints](docs/capabilities.md),
[training and datasets](training/README.md), and [interactive sessions](interactive/README.md).

## Runtime and licenses

The base is upstream commit `5b430a6d8d8c9cccc547b05b5e079d22b08ade9e`
(v0.9.0), Isaac Sim 6.0.1, and the pinned Arena dependency lock. Core simulation
uses Python 3.12. GR00T, OpenPI and dataset tools have separate dependency
environments; the runtime never silently installs packages or downloads weights
inside a customer invocation. Build the environments and local assets your
workflow needs, and supply owned checkpoints/data in the project archive.

Reviewed source patches preserve explicit camera control in both scene builders
and the simulator launcher. `cameras: false` disables scene camera capture; it
does not force the renderer on to hide a configuration mismatch. The build
records original and patched source hashes in `upstream-patches.json` and checks
inherited patch bytes before extending an existing image.

Rendering requires an RTX-capable GPU and the graphics/Vulkan driver libraries.
The previous image ran on L40S and RTX PRO 6000 with driver 580.173.02. H100/H200
lack the RT cores required by the renderer; pure training/data compatibility is
a separate question. Those observations are not qualification of every scene or
future driver. Check the pinned simulator's host requirements. Allocate disk for
the simulator, assets, checkpoints and complete recordings; recording cost grows
with the actual scenes, sensors, dimensions, episodes and attempts.

The workflow source is Apache-2.0. Isaac Sim, Kit, robot assets, checkpoints and
other components retain their respective terms. Review the
[Isaac Sim 6.0.1 licensing FAQ](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/common/license-faq.html)
and your entitlement before building, redistributing or hosting derived images.
Hosted/turnkey delivery has additional NVIDIA AI Enterprise requirements.
Setting acceptance variables does not establish entitlement. This source recipe
does not grant redistribution rights or provide a public simulator image.

## Build and inspect

From this directory, build into your own authorized registry. Training and
interactive build additions are documented in their owning directories; use the
combined qualified Dockerfile for the operations you need.

```bash
docker build --platform linux/amd64 -t isaac-healthcare:local .
mkdir -p output/catalog
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD/output/catalog:/output" isaac-healthcare:local \
  --operation inspect --parameters-json '{}' --output-dir /output
```

`inspect` lists the actual registry without starting Isaac or a policy backend.
A selected workflow also reports its authored modes, scene/mode cap, cameras,
control cadence, controller-source hashes, lint issues and graph-declared policy
environments. Missing backend environments are reported as missing dependencies,
not as unsupported workflow names. Discovery is not scientific execution proof.
`lint` resolves the selected graph and fails on upstream lint errors. It requires
an input artifact (scenarios or project), as do execution operations.

## Run a built-in workflow

The upstream default mode is normally `idle`. Select a controller explicitly
when desired; the runtime does not replace an unspecified mode with rule-based.

```bash
mkdir -p output/run-001
docker run --rm --gpus all --network none --shm-size 16g \
  --memory=48g --memory-reservation=32g --user "$(id -u):$(id -g)" \
  -e ACCEPT_EULA=Y -e ISAACSIM_ACCEPT_EULA=Y -e OMNI_KIT_ACCEPT_EULA=YES \
  -v "$PWD/examples:/inputs:ro" -v "$PWD/output/run-001:/output" \
  isaac-healthcare:local --operation simulate --input /inputs/scenarios.json \
  --parameters-json '{"workflow":"ultrasound_liver_scan","mode":"rule-based"}' \
  --output-dir /output
```

This is an example invocation, not a claimed new GPU pass. Choose memory/disk for
the real workload; the shown envelope comes from the prior scissor baseline.
Explicit physics (`physx` or `newton`), environment count, camera choice, attempts
and duration are preserved. Null settings retain upstream scene defaults. An
explicit `episode_steps` can only lower that **scene/mode's authored cap**; there
is no global 600-step ceiling. A project author controls its own scene manifest.

## Author a project

A TAR archive contains an optional `project.json`, an `overlay/` SDK-layout tree,
and arbitrary local data. It may contain only regular files/directories: absolute
paths, traversal, links, duplicate paths and special files are rejected. Project
Python is executable customer code and must run within the job's tenant/process
isolation; archive validation is not a Python sandbox.

```text
project.json
overlay/workflows/i4h_workflows/my_specialty/my_workflow.py
overlay/arena/i4h_arena/scenes/my_scene.py
overlay/arena/i4h_arena/scenes/manifest/my_scene.yaml
overlay/tasks/my_tasks/i4h_tasks/my_tasks/manifest/my_task.yaml
overlay/tasks/my_tasks/i4h_tasks/my_tasks/controller.py
data/recording.hdf5
data/checkpoint.pt
```

`project.json` uses `isaac-healthcare-project/v2`, with optional
`default_workflow`, `default_mode`, `python_paths` and `asset_root`. Extra Python
paths and asset_root are relative to the extracted archive. The runtime merges
SDK overlay directories with the pinned base, prepends their import paths even
under Python `-I`, and sets `I4H_WORKFLOWS` to that invocation's effective root.
`I4H_PROJECT_ROOT` points to the extracted archive for custom code reading data.
It does not modify the installed SDK. Request parameters override project
workflow/mode defaults. `workflow_args` passes JSON kwargs to the authored mode
builder. They may override upstream defaults such as teleop sensitivity or port.
Conflicts with outer-owned inputs and controls (including dataset, replay indices
and idle_seconds) fail clearly instead of changing the outer request.

The included project demonstrates a separately named ultrasound scene, a custom
registered task and an `observe` mode, reusing upstream geometry/physics. Its
1,200-step authored cap illustrates that longer projects are not blocked by the
old example's cap. The observation task does not claim clinical success.

```bash
tar -C examples/project -cf examples/project.tar .
mkdir -p output/project-lint
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD/examples:/inputs:ro" -v "$PWD/output/project-lint:/output" \
  isaac-healthcare:local --operation lint --project /inputs/project.tar \
  --parameters-json '{"episode_steps":1000,"workflow_args":{"seconds":5.0}}' \
  --output-dir /output
```

Use `--operation simulate` and the GPU/license flags above for actual execution.
Optional scenarios JSON accepts schema `isaac-healthcare-scenarios/v1` or `/v2`,
with unique arbitrary labels and optional seeds. An omitted case seed uses
`parameters.seed`; an explicit null preserves upstream random initialization.
Labels are never paths. With
only a project, one default case uses `parameters.seed`. Each case has independent
scratch and a fresh simulator process. A supplied seed reaches the upstream
recorded-reset/randomization scope; it does not guarantee deterministic scene
construction or identical trajectories across GPU architectures.

## Replay and policy execution

Set `--operation replay`, include the original HDF5 under project `data/`, and
set `dataset` to its relative path. `replay_episodes` defaults to `[0]`. Batch
execution retains separate results for every requested index. Interactive replay
selects each index in order within one Kit session, retaining `episodes`
repetitions and the requested attempt budget for each index. This corrects the
pinned CLI's first-index-only comma parsing. Upstream reads the recorded initial
state/actions and owns stepping; `replay-sequence.json` records sequence outcomes.
Replay does not infer a new task-success predicate. Real replay rendering remains
part of the new image's qualification.
An explicit replay operation selects replay even when the project's default mode
is different; an explicitly conflicting request mode fails. Custom teleop kwargs
use the same authored workflow construction as batch modes. CPU tests cover that
construction and replay sequencing, not interactive device or rendering quality.

Policy modes resolve graph-declared backends. Each backend runs its own installed
`.venv` and imports the effective project source. Checkpoints are project-relative
paths; the simulator and backends communicate through a private Unix Zenoh
transport. No Internet socket or unauthenticated network listener is required
for this IPC. Startup retains upstream's 600-second **backend readiness** budget,
which is distinct from simulation steps; missing environments or checkpoints
produce actionable failures. Remote backends are joined on termination.

## Outputs and scientific meaning

Every successful operation produces `result.json` (`isaac-healthcare-result/v2`)
and `simulation.tar`. The result binds raw input/project SHA-256, normalized
parameters, base revision, project/selected-controller source inventory, scene
caps/cadence, and all archive file hashes. Simulation/replay includes HDF5,
per-case workflow outcomes and dynamic sensor previews. No joint count, camera
name, resolution or workflow name is hardcoded in validation.
The archive retains supplied scenarios byte-for-byte at `request/scenarios.json`.
This lets a completed-output audit reconstruct all cases and replay indices from
the original input SHA, including after the input files are no longer present.
The project SHA stays bound to the request; the complete project is not duplicated
into the results. Restoring completed outputs does not execute project code.

`scientific_validation=passed` means structural integrity and terminal evidence
agree; it does not turn an unfinished task into success or establish physical
accuracy. `task_complete` preserves upstream outcome and can be false for a valid
finite job. Inspect/lint report `not_applicable` and null task completion. The
upstream recorder captures environment 0 of vectorized batches and omits the
termination/reset sample; empty immediate attempts can be absent from HDF5.
Diagnostics with absent per-frame measurements retain their NaN counts.

Full simulator/device/error logs remain on stdout and in `.operator/`, outside
the public scientific archive. Preserve them for diagnosis. Use a fresh output
directory for every run. Signals are forwarded to task-owned child processes;
installed source, other jobs and previous results are untouched.

## Kubernetes and provider Serverless

`kubernetes/render_job.py` renders a standalone Job against your own PVCs and
immutable image. It does not create resources or depend on Scientific AI. The
project and scenarios paths are configurable relative to the input PVC:

```bash
python kubernetes/render_job.py --operation simulate \
  --image 'your-registry/ih@sha256:YOUR_COMPLETE_64_HEX_DIGEST' \
  --name isaac-project-001 --namespace simulations \
  --input-pvc isaac-inputs --output-pvc isaac-results \
  --project project.tar --scenarios '' --parameters project-parameters.json \
  --gpu-node-selector nvidia.com/gpu.product=NVIDIA-L40S --accept-eula > job.json
kubectl create --dry-run=server -f job.json
kubectl create -f job.json
```

The template supplies non-root execution, read-only inputs/root filesystem,
local scratch/shared memory and persistent outputs. Resource requests are a
starting envelope, not measured general-framework capacity. Export result and
operator logs before deleting only the owned Job; PVCs remain.

The [provider recipe](provider/README.md) uses your project, registry, existing
object storage and scoped HTTPS transfers around the same portable launcher.
A short repository with the full immutable digest avoids an observed provider
image-derived-label failure; do not truncate digests or use mutable tags. The
prior provider pass used the old scissor image, L40S/16 vCPU/96 GiB, full object
hashes and actual host/container identity. Its initial capacity failure is
retained. The new generalized provider path requires its own qualification.
Provider bucket mounts and persistent interactive endpoints are separate paths.
GUI/teleoperation requires authenticated signaling/media and owned session
lifecycle; see `interactive/`, not an exposed raw Kit port.

## CPU verification

```bash
PYTHONPATH=src python -m pytest tests
# Inside your built image:
/opt/i4h/arena/.venv/bin/python -I /opt/isaac-healthcare/scripts/verify_runtime.py
/opt/i4h/arena/.venv/bin/python -I -m isaac_healthcare_runtime.audit \
  --operation simulate --input scenarios.json --parameters parameters.json \
  --result result.json --archive simulation.tar --output validation.json
```

Add `--project project.tar` to the audit for project-backed requests. CPU checks
cannot substitute for real scene, policy, training or interactive execution on
the exact resulting image.
For output-only recovery, `--input-identity identity.json` accepts the trusted
original `input_sha256` and `project_sha256` (each a full SHA-256 or null). Obtain
these from the authorized request, not the result being audited. The Scientific AI
collector invokes this audit in the Arena interpreter; its logs and report remain
operator-only, and repeated collection leaves both delivered artifacts unchanged.

### Verified asset cache for overlay builds

`Dockerfile.general-overlay` normally downloads the pinned public asset URLs.
Operators may put the complete raw manifest tree in `.asset-cache/` in the build
context and use `--build-arg USE_VERIFIED_ASSET_CACHE=1`. The build mount is
read-only and is not retained; every source file still must match its recorded
size and SHA256 before localization/composition. This changes transport only,
not workflow eligibility or runtime assets. Do not substitute a localized tree
for the original pinned source bytes.
