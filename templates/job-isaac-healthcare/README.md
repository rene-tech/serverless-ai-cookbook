# Isaac for Healthcare headless simulation

Run the actual **i4h v0.9.0 scissor pick-and-place** graph with an SO-ARM 101,
surgical scissors, tray, PhysX dynamics, room/wrist RGB cameras and HDF5
trajectories. The finite job records task success, failed attempts, exact
configuration, initial states, task segments, workflow logs and preview frames.

**Qualification status (27 October 2026):** the portable runtime passed real
default 600-step-cap runs on L40S and RTX PRO 6000, including rendered RGB and
successful pick-and-place outcomes. A different seed/name with cameras explicitly
disabled also passed on L40S. These runs blocked network access for the simulator.
Two ordinary hosted REST/MCP cohorts using the same portable runtime passed
scientific and full artifact/custom/default-bucket checksum checks. These covered
two default rendered tasks, a different seed/name with cameras disabled, and an
explicit 73-step run that correctly recorded `task_complete=false`. Separate
malformed-JSON requests through REST and MCP preserved the native parser error
on both status/result surfaces without advertising successful output. One
camera-off case retained complete scientific outputs but missed capture of its
full raw operator log after main termination; that diagnostic gap remains
recorded. A separate 28-check Isaac audit passed same-request replay,
changed-parameter/destination conflicts and foreign status/result/artifact/cancel
denial between two principals in one tenant (84 controls across all three Apps).
Shared capacity, owner cancellation/recovery, cross-tenant isolation, client
integration and native regional fallback remain unqualified.
CPU source/import/asset checks passed as non-root UIDs 10001 and 65532. Provider
Serverless also passed one default 600-step-cap/cameras-on run on L40S using a
short full-digest image reference: successful task completion, 533 samples,
dual RGB streams and full requested-bucket/independent CPU checks. Its initial
VM scheduling capacity failure remains retained. See the provider recipe for
the exact measured allocation and diagnostic networking.
This recipe covers one rule-based simulation workflow. Other
i4h policies, ultrasound, training, interactive WebRTC and physical robot/device
integration have separate runtime requirements.

## Runtime and licenses

- i4h `5b430a6d8d8c9cccc547b05b5e079d22b08ade9e` (v0.9.0), Isaac Sim
  `6.0.1.0`, and the upstream `arena/uv.lock`; x86-64 Linux image.
- RTX-capable GPU: L40S and RTX PRO 6000 were exercised with driver `580.173.02`;
  i4h lists 16 GB minimum and 48 GB recommended device memory. Verify the driver
  requirements of the pinned simulator release on your host. Headless rendering
  still needs RT cores; H100/H200 are unsuitable for this workflow.
- Plan at least 100 GB for build/cache and 250 GB local job disk initially.
  Recorded output grows with scenarios × episodes × attempts × steps; measure
  the actual workload before reducing disk. No duration or camera reduction is
  applied implicitly.
- The workflow code is Apache-2.0. NVIDIA Isaac Sim and its components/assets
  have their own terms. Review the [Isaac license](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/)
  and the bundled Omniverse Kit terms before setting the three EULA variables
  below. `OMNI_KIT_ACCEPT_EULA=Y` is independently required by Kit in Isaac Sim 6.0.1 startup.
  This source recipe grants
  no simulator/asset redistribution rights. Publish a derived image only to a
  registry where your license permits it; there is no public prebuilt image.

The exact [Isaac Sim 6.0.1 license FAQ](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/common/license-faq.html)
permits internal R&D without an Enterprise license, but requires NVIDIA AI
Enterprise licensing for third-party hosted service delivery or turnkey
redistribution of Isaac Sim with Kit. Supplying source instructions for a
customer's own environment and selling only internally generated outputs are
distinct cases in that FAQ. Confirm the applicable entitlement before offering
this as a hosted customer service; setting an EULA environment variable does
not establish that entitlement.

The exact twelve source assets, including tray textures and the default Isaac 6.0
ground environment with its textures, are
pinned in `asset-sources.json` and baked into the image. Build-time USD rewriting
only localizes asset references and the IsaacLab asset-root settings; source and
materialized hashes are retained in
`/opt/i4h-assets/v0.9.0-7cf86a1/manifest.json`. Workflow physics/control code is
unchanged. A reviewed five-line upstream patch makes explicit `cameras=false`
disable both SOARM camera construction and image observation terms; the default
camera path is unchanged. Exact patch and source hashes are recorded in
`upstream-patches.json` and included in every scientific archive. The selected
rule-based workflow has no policy weights. The CPU gate
checks the complete identified USD reference closure and packaged MDL material.
The measured runs completed with simulator network sockets blocked; repeat the
offline check for your own built image and installation.

## Build and run on premises

From this directory, with Docker and the NVIDIA Container Toolkit installed:

```bash
docker build --platform linux/amd64 -t isaac-healthcare:local .
mkdir -p output/run-001
docker run --rm --gpus all --shm-size 16g \
  --memory=48g --memory-reservation=32g \
  --user "$(id -u):$(id -g)" \
  -e ACCEPT_EULA=Y -e ISAACSIM_ACCEPT_EULA=Y -e OMNI_KIT_ACCEPT_EULA=Y \
  -v "$PWD/examples:/inputs:ro" -v "$PWD/output/run-001:/output" \
  isaac-healthcare:local \
  --input /inputs/scenarios.json --parameters-json '{}' --output-dir /output
```

The same portable Python package is the Scientific AI worker's execution path;
it has no private `scientific_ai` imports or platform-token requirement.
Inspect `output/run-001/result.json`, then extract `simulation.tar` for HDF5,
configuration, workflow outcome logs and PNG previews. Full simulator/device
diagnostics remain in process stdout and the local `.operator/` directory;
they are excluded from the public result archive. Each execution must use an empty output
directory; concurrent jobs have independent directories and simulator processes.
Kit uses its supported `--portable-root` under each scenario’s private scratch,
so arbitrary non-root UIDs never write caches into the installed simulator.
The container exposes no network listener. Stop the exact container to cancel;
its termination signal is forwarded to the simulator process group.

## Inputs and outcomes

`examples/scenarios.json` is a JSON document with schema
`isaac-healthcare-scenarios/v1` and a nonempty `scenarios` array. Each row has a
unique arbitrary `name` and optional nonnegative 32-bit `seed`; null keeps
upstream random initialization. Labels are never filesystem paths. Add scenarios
or change seeds without changing eligibility or execution defaults.
A supplied seed is applied before the first recorded reset and scissors/tray
randomization; later episodes/attempts continue the RNG stream. Upstream scene
construction happens earlier and can warn that its configuration seed is unset.
The seed does not promise deterministic construction or identical trajectories
across GPU architectures.

`parameters.schema.json` defines the typed controls: workflow, positive
`episodes` and `attempts`, optional `episode_steps`, `physics`, and `cameras`.
The default scene cap is **600 steps at 60 Hz**, taken from upstream
`arena/i4h_arena/scenes/manifest/soarm_scissors.yaml`. An explicit lower step cap
is preserved and may yield an unfinished task. This runtime exposes the scene's
supported PhysX backend; no silent Newton substitution occurs.

`task_complete` means the upstream success predicate was met for every requested
episode. `scientific_validation=passed` means recordings and terminal summaries
are structurally consistent; it does not turn a timeout/failed grasp into
success. Malformed input, simulator crashes, missing samples, mismatched counts,
non-finite trajectories and empty camera images fail the job with an explanation.
The HDF5 v1 format intentionally omits the terminating reset sample, so the last
frame alone cannot establish the terminal task outcome.

## Kubernetes on premises

Use the standalone Job template in `kubernetes/`; it creates no Scientific AI
account, service or platform dependency. Your cluster needs the NVIDIA device
plugin/runtime with graphics driver libraries available and an RTX-capable node.
Provision your own input/output PVCs first. Put `scenarios.json` and
`parameters.json` at the input PVC root; ensure the output PVC permits the chosen
UID/GID. Use existing image-pull credentials for your authorized registry.

```bash
export ISAAC_IMAGE='your-registry/isaac-healthcare@sha256:YOUR_BUILT_DIGEST'
python kubernetes/render_job.py \
  --image "$ISAAC_IMAGE" --name isaac-healthcare-run-001 --namespace simulations \
  --input-pvc isaac-inputs --output-pvc isaac-results \
  --gpu-node-selector nvidia.com/gpu.product=NVIDIA-L40S \
  --image-pull-secret your-existing-registry-secret --accept-eula > isaac-job.json
kubectl create --dry-run=server -f isaac-job.json
kubectl create -f isaac-job.json
kubectl -n simulations logs -f job/isaac-healthcare-run-001
kubectl -n simulations get job isaac-healthcare-run-001
```

The renderer requires a manifest digest and explicit license acceptance. Change
the GPU label/value to your cluster's compatible RTX nodes, for example its RTX
PRO 6000 labels; this selector is placement configuration, not an exclusive
hardware support claim. The initial envelope is one GPU, CPU request 8/limit 24,
RAM request 32 GiB/limit 48 GiB, 128 GiB local scratch and 16 GiB shared memory.
It is an allocation, not measured capacity. Review available node disk/memory
and expected output size before scheduling. The default deadline is two hours;
`--deadline-seconds` preserves an explicit operator choice.

The Job runs as non-root with a read-only root filesystem, no added capabilities
or API token, read-only inputs, writable local scratch and persistent outputs.
The device plugin selects the allocated GPU; the manifest does not force device
IDs. Files appear under `isaac-healthcare-run-001/` on the output PVC, with
`completion.json` only after checksum-verified delivery. The initial finite
workflow's result can honestly report `task_complete=false` even when the Job
completed. Export logs/results before deleting only this Job; PVC outputs remain.
Use a new Job name/output prefix for another run. Local scratch is removed with
the Pod. For the Docker offline-asset check, add `--network none` to the Docker
command and retain its actual invocation and outputs.

## Nebius provider Serverless Job

Use the [scoped-transfer provider recipe](provider/README.md). It prepares a
finite Job using your own project, immutable image, existing object-storage
credentials and arbitrary supported scenario/parameter files. It invokes the
same portable launcher, with local POSIX scratch, simulator network blocking,
full input/output SHA checks and independent scientific validation. No private
Scientific AI account, package or token is required.

A short repository name with the **complete immutable digest** passed the
provider's image-label validation; the earlier long-reference failure remains
recorded. One actual Job used the same portable manifest and unchanged default
600-step-cap/seed-17/cameras-on request on L40S, 16 vCPU and 96 GiB RAM. It
completed the task at step 534, recording 533 samples and both 640×480 cameras.
Actual container image/GPU/driver identity, the offline simulator filter, all
eight delivered file hashes and independent CPU science validation passed.
The first VM attempt failed capacity scheduling, then the provider progressed
the same accepted Job without a manual restart or duplicate scientific request.
The [provider README](provider/README.md) preserves this measured scope, including
the opt-in public-IP/SSH diagnostics used for actual image verification.

The supported recipe transfers closed archives with scoped HTTPS capabilities.
Provider bucket mounts, an always-running Endpoint and WebRTC networking have
not been qualified by this path. Export all outputs and diagnostics before
cleaning only your returned Job and its verified dependent VM/disk/IP resources.

## Verification

```bash
PYTHONPATH=src python -m pytest tests
docker run --rm --entrypoint /opt/i4h/arena/.venv/bin/python \
  isaac-healthcare:local /opt/isaac-healthcare/scripts/verify_runtime.py
```

CPU checks establish source/import/schema and output-validation behavior only.
The measured portable manifest was
`sha256:4f2df56ae870971063dc84b6d699630f55bdc0a9d2d7b4213c741f0f5e6df60c`;
builds in your registry need their own immutable digest and installation checks.
Its default runs recorded 549 samples on L40S and 533 on RTX, with both 640×480
camera streams and successful task outcomes. The camera-off seed-731 case recorded
533 samples and no images. The common allocation was 32 GiB requested / 48 GiB
limited RAM; sampled cgroup high-water values were 13.50 and 16.24 GiB for the
two rendered baselines. These are workload observations, not final peak or
shared-capacity guarantees; no memory sample was captured for the camera-off run.

The unchanged upstream scene emits physics warnings: its tray mass override and
robot collision overrides do not apply, its nonuniform tray scale triggers an
unsupported ScaleOrientation warning, and its TGS/external-force setting may
produce noisy velocities. Rendered runs also warn about Fabric geometry
streaming and mute some USD diagnostics. Successful rendering and offline task
completion do not establish warning-free USD composition or quantitative
physical accuracy. Full warnings remain in operator stdout/logs.

For your own installation, repeat the short unfinished-task and malformed-input
checks and qualify cancellation; inspect rendered RGB and recorded task outcomes. Measure startup, elapsed simulation time, memory, output size and
failures on each GPU/region before advertising throughput or shared capacity.
Interactive WebRTC additionally needs its signaling/media transport; managed
HTTPS alone does not qualify it.

Upstream references: [i4h v0.9.0](https://github.com/isaac-for-healthcare/i4h-workflows/tree/v0.9.0),
[Isaac container setup](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/install_container.html).
