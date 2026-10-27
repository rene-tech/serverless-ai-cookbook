# Holoscan recorded endoscopy tool tracking

Run the real Holoscan 5 C++ operator graph on a recorded video. The pinned CAMMA
convolutional LSTM detects seven surgical tool classes, predicts tooltip
locations, and returns seven mask channels per frame. It preserves recurrent
state across the selected frames. Python handles video preparation and artifact
delivery; inference executes in Holoscan/TensorRT.

This finite workflow targets an NVIDIA Linux host without Scientific AI, a private
application, or a cloud account. Exact GPU qualification is recorded separately.
The provider Job path currently hits a backend label-validation error for the
reviewed immutable image; see the Serverless section and `provider/README.md`. Live camera/capture-card acquisition, persistent streams, clinical control,
and real-time network latency are separate, unqualified workflows.

## Exact implementation

- Holoscan SDK **5.0.0**, CUDA **13.2.51**, TensorRT **10.16.0.72**, Ubuntu 24.04.
- [Official reference application](https://github.com/nvidia-holoscan/holoscan-applications/tree/7d2e3b3c2b5d48bf0bc5caeba4d715b797ae3031/applications/endoscopy_tool_tracking)
  at `7d2e3b3c2b5d48bf0bc5caeba4d715b797ae3031`. The Dockerfile pins the
  source-archive checksum and AMD64 base manifest, and compiles SM89/90/100/120.
- The small reviewed patch records aligned native outputs from the upstream
  postprocessor. It does not replace the model or alter its recurrence.
- [CAMMA sample/model resource](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/clara-holoscan/resources/holoscan_endoscopy_sample_data)
  version `20230222`; ONNX SHA256
  `d05733d49187f10975eafd762001f4535f5029fd071ca39779f953c7886a3c18`.
- FP32, matching upstream's default. Upstream observed FP16 NaNs on a tested
  device; this recipe does not silently substitute reduced precision.

The source is Apache-2.0. The separately downloaded model and video have the
included NVIDIA Clara SDK license, including research/development and healthcare
testing terms. The image does not redistribute those assets. This software
contains source code provided by NVIDIA Corporation. Model/sample attribution:
Research Group CAMMA, IHU Strasbourg, and the University of Strasbourg.

## Build and run on premises

Use an AMD64 Linux host with Docker, NVIDIA Container Toolkit, and a driver
compatible with this exact CUDA 13.2 runtime. Check `nvidia-smi` and real container
execution. A CUDA major number alone does not prove compatibility: the target
fleet uses driver `580.173.02`, and exact-image GPU qualification is tracked in
`QUALIFICATION.md`. Building or running Python CPU tests does not qualify GPU
inference. ARM64 requires a separate build and qualification.
The launcher retains the pinned NVIDIA image's `/etc/shinit_v2` compatibility
probe. It activates bundled compatibility libraries only after the official
device probe succeeds, otherwise preserving the host driver path. No host driver
is changed. Keep this launcher when overriding a container command.

From this directory:

```bash
docker build -t holoscan-video:5.0.0 .
python3 src/prepare_sample.py --output sample
mkdir -p results/run-001
docker run --rm --gpus all --user "$(id -u):$(id -g)" \
  -v "$PWD/sample:/inputs:ro" -v "$PWD/results:/outputs" \
  holoscan-video:5.0.0 \
  --input-video /inputs/surgical_video.264 \
  --model /inputs/tool_loc_convlstm.onnx \
  --output-dir /outputs/run-001 \
  --parameters-json '{"video_file":"surgical_video.264","frame_count":30}'
```

For your own recording, mount its directory read-only and change `--input-video`.
Inputs are ordinary MP4, MKV/WebM, AVI, H.264, HEVC or MPEG recordings. The model
uses RGB 854×480; preparation explicitly stretches frames with bicubic scaling,
records original dimensions, and retains that transformation in `result.json`.
It processes encoded pixels without autorotation. Source display rotation/matrix
are recorded separately; coordinates and annotated MP4 use the encoded-pixel
orientation. Apply that recorded display transform explicitly when comparing
with a viewer that rotates the source automatically.
Only the pinned model is accepted. This is a specific trained tool tracker,
not an arbitrary uploaded-ONNX execution service.

`--parameters-json` accepts:

| Field | Default | Meaning |
| --- | --- | --- |
| `video_file` | `video.mp4` | Relative input identity; Scientific AI uses it to select a tar member. |
| `frame_count` | `0` | All remaining selected frames; a positive count must be fully available. |
| `start_frame` | `0` | First source frame, zero based. Recurrent state starts at zero there. |
| `frame_stride` | `1` | Every Nth frame; changes temporal context explicitly. |
| `probability_threshold` | `0.5` | Annotated overlay threshold; numerical outputs remain complete. |
| `annotated_video` | `true` | Also generate an MP4 overlay. |

Integral JSON numbers such as `3`, `3.0` and `3e0` are equivalent frame settings;
booleans and fractional values are rejected.

The graph processes frames in order with bounded queue depth and backpressure.
Each container/run has independent recurrent state, scratch and engine cache.
Concurrent Jobs require separate output directories. The platform schedules and
limits Jobs; the recipe starts no competing scheduler or singleton service.

The native application replays a contiguous RGB file, so local scratch includes
`854 × 480 × 3 × selected_frames` bytes plus engine, masks and encoded artifacts.
At 30 fps, RGB alone is about 2.2 GB/minute. Size scratch for the recording; no
implicit frame cap is used. `--scratch-dir` selects a sufficiently large local
filesystem. Keep scratch/engine cache off object-storage mounts.

## Outputs and scientific meaning

- `tracking.csv`: seven rows per frame, tool index, probability, normalized
  x/y tooltip coordinates. Encoded source pixel coordinates are x×encoded width
  and y×encoded height, before any display rotation. Values are native model predictions, not calibrated clinical
  confidence or validated surgical measurements.
- `masks.npy`: float32 `[frames, 7, 60, 107]`, preserving native channels and
  overlap; load with `numpy.load(..., allow_pickle=False)`.
- `annotated.mp4`: optional mask overlays, 854×480 at source fps / frame stride.
- `result.json`: input/model/source identity, completed frame count, preprocessing,
  class order, timing, limitations, and artifact sizes/checksums. It is written
  last, after complete files are copied to durable output.

Class order is grasper, bipolar, hook, scissors, clipper, irrigator, specimen bag.
The initial TensorRT engine build is included in graph time. A single run does
not establish sustained capacity, clinical accuracy, or real-time latency.

## Nebius Serverless Job

Observed on 27 October 2026: the provider rejects the reviewed full digest with
`metadata.labels: label value length (...) exceeds maximum value (64)`.
The CLI request contains no labels, so changing clients is not an established
fix. Preserve immutable references. The commands below describe the intended
Job contract; stop if its dry-run reports this defect. The scoped transfer and
once-only Endpoint diagnostic in [provider/README.md](provider/README.md) is
also blocked by the same error in an actual SDK dry-run. No provider GPU
execution is qualified. The portable on-premises build remains independent.

Build and push the portable image to **your registry**, using your usual registry
login; no Scientific AI credentials are required. Do not put passwords in the
Dockerfile or command arguments. Record the returned immutable digest.

```bash
export IMAGE="YOUR_REGISTRY/holoscan-video:5.0.0"
docker tag holoscan-video:5.0.0 "$IMAGE"
docker push "$IMAGE"
docker image inspect "$IMAGE" --format '{{json .RepoDigests}}'
export IMAGE="YOUR_REGISTRY/holoscan-video@sha256:RETURNED_DIGEST"
```

Use an existing project and regional input/output bucket with authorized access.
Upload `surgical_video.264`, `tool_loc_convlstm.onnx`, and the included asset
license to the input bucket. Also upload `parameters.json` containing
`{"frame_count":30}`. Keep credentials in the provider's secret store or
normal CLI profile; do not embed them in the image or JSON parameters. Bucket
mount access uses your project/service identity; cross-account S3 mounts can use
the CLI's `PROFILE@SECRET_SELECTOR` volume syntax.

Check your installed `nebius ai job create --help` and available platform/presets.
Set the project, qualified GPU preset, immutable image and both bucket IDs:

```bash
nebius ai job create \
  --parent-id "$NEBIUS_PROJECT_ID" --name holoscan-recording-001 \
  --image "$IMAGE" --platform "$HOLOSCAN_PLATFORM" --preset "$HOLOSCAN_PRESET" \
  --on-demand --disk-size 128Gi --timeout 1h --restart-policy never \
  --volume "$INPUT_BUCKET_ID:/inputs:ro" \
  --volume "$OUTPUT_BUCKET_ID:/outputs:rw" \
  --container-command /opt/holoscan-video/launch.sh \
  --args 'python3 /opt/holoscan-video/holoscan_video.py --input-video /inputs/surgical_video.264 --model /inputs/tool_loc_convlstm.onnx --output-dir /outputs/run-001 --parameters-file /inputs/parameters.json' \
  --dry-run
```

Review the dry-run projection, especially the argument array. Run the same
command without `--dry-run` when ready to create your Job. Use a new output
prefix for each execution. Initial deterministic errors should be corrected,
not retried indefinitely. If using spot capacity, interruption restarts the
recurrent clip from the beginning; no checkpoint-resume claim is made.

```bash
nebius ai job get "$JOB_ID" --format json
nebius ai job logs "$JOB_ID" --tail 100 --timestamps
# If needed:
nebius ai job cancel "$JOB_ID"
# After verifying and downloading durable outputs:
nebius ai job delete "$JOB_ID"
```

Deleting the Job does not delete separately mounted bucket objects. Retain or
remove only the run prefix you own. Compute, image pulls and storage may be
billed. No HTTP port, public endpoint, application bearer token or persistent
stream is needed for this finite Job.

## Kubernetes on premises

Use the [finite Kubernetes Job recipe](kubernetes/README.md) on your own NVIDIA
cluster. It retains the same portable image/CLI, read-only script and capability
mounts, separate scratch and durable outputs, and explicit no-retry Job policy.
GPU/driver qualification and resource sizing still apply. This path does not use
the provider Job/Endpoint APIs that currently reject the reviewed digest.

## Verification and troubleshooting

```bash
docker run --rm --entrypoint python3 -v "$PWD:/recipe:ro" holoscan-video:5.0.0 \
  -m unittest discover -s /recipe/tests -v
```

These CPU tests use a newly generated video and verify temporal selection,
malformed input, parameter validation and numerical artifact integrity. The
separate GPU test must use the real model/sample and inspect all four outputs.
Never label upstream's `--synthetic true --inference false` CI mode as inference.

- Missing `libcuda.so.1`: verify NVIDIA Container Toolkit and GPU assignment.
- Engine initialization/build failure: inspect exact driver/runtime compatibility
  and memory; do not remove the pretrained model or disable inference to pass.
- No selected frames: correct the start/count/stride; positive count requests
  fail if the recording is shorter, instead of returning silent partial results.
- Object storage write errors: durable outputs use whole-file copies. Scratch,
  append-only graph tables and temporary encoder files stay on local disk.
- Job completed but outputs missing: check the output mount/prefix and complete
  `result.json` inventory. A terminal container status alone is insufficient.
