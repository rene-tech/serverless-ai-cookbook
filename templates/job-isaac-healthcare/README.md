# Isaac for Healthcare headless simulation

Run the actual **i4h v0.9.0 scissor pick-and-place** graph with an SO-ARM 101,
surgical scissors, tray, PhysX dynamics, room/wrist RGB cameras and HDF5
trajectories. The finite job records task success, failed attempts, exact
configuration, initial states, task segments, workflow logs and preview frames.

**Qualification status (27 October 2026):** the portable runtime passed real
default 600-step-cap runs on L40S and RTX PRO 6000, including rendered RGB and
successful pick-and-place outcomes. A different seed/name with cameras explicitly
disabled also passed on L40S. These runs blocked network access for the simulator.
CPU source/import/asset checks passed as non-root UIDs 10001 and 65532. Provider
Serverless execution remains blocked by the documented image-label limitation.
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

Build and push to **your authorized registry**, then resolve the immutable image
digest. Select an available RTX-capable platform/preset in your project and a
same-region output bucket. Verify the actual host driver before qualification.
The CLI syntax below was checked with installed `nebius ai job create --help`;
it is distinct from Scientific AI's native Serverless deployment.

**Current provider limitation:** qualification encountered a backend label-length
error for the long digest-pinned image reference. The commands below are not yet
a successful provider execution claim. Retain the immutable pin and the actual
dry-run error until a supported provider path passes; do not silently replace it
with a mutable tag.

```bash
export ISAAC_IMAGE='your-registry/isaac-healthcare@sha256:YOUR_BUILT_DIGEST'
export PROJECT_ID='your-project-id'
export OUTPUT_BUCKET='your-same-region-bucket-name'
export S3_SECRET_SELECTOR='your-existing-object-storage-credential-secret'

nebius ai job create --dry-run \
  --parent-id "$PROJECT_ID" --name isaac-healthcare-run-001 \
  --image "$ISAAC_IMAGE" --platform gpu-l40s-d \
  --preset 1gpu-16vcpu-96gb --on-demand --restart-policy never \
  --timeout 2h --disk-size 250Gi --shm-size 16Gi \
  --volume "s3://$OUTPUT_BUCKET:/data:rw:default@$S3_SECRET_SELECTOR" \
  --env ACCEPT_EULA=Y --env ISAACSIM_ACCEPT_EULA=Y --env OMNI_KIT_ACCEPT_EULA=Y \
  --inject-file "$PWD/examples/scenarios.json:/inputs/scenarios.json" \
  --inject-file "$PWD/examples/parameters.json:/inputs/parameters.json" \
  --container-command /opt/i4h/arena/.venv/bin/python \
  --args '-I /opt/isaac-healthcare/scripts/run_serverless.py --input /inputs/scenarios.json --parameters /inputs/parameters.json --output-prefix /data/runs/isaac-001'
```

After reviewing the dry run, remove `--dry-run` to submit. Use a registry secret
when required; the volume uses your existing object-storage MysteryBox credential
secret/profile. Do not put passwords or cloud credentials in the recipe. Injected
files have the provider's 64 KiB limit; place larger scenario documents in an
authorized read-only input bucket mount and adjust `--input` accordingly.

HDF5 and caches are written to **local POSIX scratch**, then the wrapper copies
closed `result.json` and `simulation.tar` files to the output bucket and verifies
their checksums. `completion.json` appears only after verified delivery. A bucket
mount is not a general POSIX filesystem: do not point HDF5, logs, caches or a
virtualenv directly at it. A completed unsuccessful task still has its detailed
results; an interrupted job lacks a completed publication receipt.

Use the returned Job ID with the installed CLI's `get`/`logs` commands, and
retain that ID and the image digest with results. Cancel/delete only your exact
Job after exporting evidence. Bucket outputs remain until explicitly deleted;
delete only the run prefix you own. Local Docker output remains after `--rm`.
There is no cross-attempt simulator checkpoint resume in this first recipe.

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

Installation acceptance must also cover a deliberately short episode and
cancellation; inspect rendered RGB and recorded
task outcomes. Measure startup, elapsed simulation time, memory, output size and
failures on each GPU/region before advertising throughput or shared capacity.
Interactive WebRTC additionally needs its signaling/media transport; managed
HTTPS alone does not qualify it.

Upstream references: [i4h v0.9.0](https://github.com/isaac-for-healthcare/i4h-workflows/tree/v0.9.0),
[Isaac container setup](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/install_container.html).
