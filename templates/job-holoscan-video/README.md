# Holoscan recorded endoscopy tool tracking

Run the real Holoscan 5 C++ operator graph on a recorded video. The pinned CAMMA
convolutional LSTM detects seven surgical tool classes, predicts tooltip
locations, and returns seven mask channels per frame. It preserves recurrent
state across the selected frames. Python handles video preparation and artifact
delivery; inference executes in Holoscan/TensorRT.

This finite workflow runs on an NVIDIA Linux host without Scientific AI, a private
application, or a cloud account. The exact portable image passed finite Kubernetes
executions on L40S, H100, H200 and RTX PRO 6000 Blackwell; see
[QUALIFICATION.md](QUALIFICATION.md) for the driver, workload and measured scope.
The provider Job path also passed a finite L40S execution with actual image
identity, scientific outputs and full requested-output delivery verified. See the Serverless section and
[provider/README.md](provider/README.md). Live camera/capture-card acquisition,
persistent streams, clinical control,
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

Follow [the finite provider Job recipe](provider/README.md). Build/push to your
own short registry repository, retain the **complete immutable digest**, and
supply one scoped input GET and one scoped output PUT for a fresh prefix in your
existing bucket. The offline builder retains the exact portable launcher,
unchanged transfer/bundle scripts, zero restart attempts and a finite timeout.
It supports ordinary filenames and the same video/frame parameters as Docker.
No Scientific AI account, application token or private source is required.

A 119-character short full-digest reference passed a real provider SDK dry-run
on 27 October 2026 with byte-identical manifest/config/layers. A separately
observed verification Job passed actual manifest/config/RootFS identity, all
30-frame scientific checks, full output hashes and physical resource closeout
on L40S. The earlier run's missing image observation remains recorded separately
in [QUALIFICATION.md](QUALIFICATION.md). This is finite execution evidence, not
shared-capacity, streaming or clinical qualification.
Earlier longer references failed Job and Endpoint dry-runs with a Compute
label-length error. Preserve that failure and dry-run your own exact reference;
shortening the repository is not a guarantee for every registry configuration.
Never truncate the digest or substitute an unverified mutable tag.

The scoped transfer path uses local scratch and whole-object export. Provider
bucket mounts and persistent Endpoint execution remain separate, unqualified
paths. The on-premises image continues to run without either provider API.

## Kubernetes on premises

Use the [finite Kubernetes Job recipe](kubernetes/README.md) on your own NVIDIA
cluster. It retains the same portable image/CLI, read-only script and capability
mounts, separate scratch and durable outputs, and explicit no-retry Job policy.
GPU/driver qualification and resource sizing still apply. This path does not use
provider Job/Endpoint APIs; its qualification is independent of provider dry-runs.

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
- Job completed but outputs missing: check the exact output prefix, scoped PUT
  expiry/permissions, upload receipt and complete `result.json` inventory. A
  terminal container status alone is insufficient.
