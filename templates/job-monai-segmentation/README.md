# MONAI pretrained CT segmentation Job

Run a real, pretrained MONAI bundle on a supplied 3D CT NIfTI volume, locally or
as a finite Nebius Serverless Job. No Scientific AI account, endpoint, or token
is needed for the standalone recipe. The same engine is used by Scientific AI's
`monai-spleen-ct` App; that App has its own authenticated artifact/Job interface.

This first workflow segments the spleen. It does not claim qualification of all
MONAI models. Training, MONAI Label, DICOM/PACS integration, DICOM SEG, and other
bundles require their own dependency, scientific, and service qualification.
The installed MONAI framework remains available to extend the image with other
trusted workflows; qualify those separately before publishing them.

## Exact implementation

- MONAI **1.6.1**, PyTorch **2.9.1**, CUDA **12.8**, Python **3.11**.
- Public base: `pytorch/pytorch@sha256:7b324d212a4450795b49edba9949b7cdc72429148a64e974334bfe5774d51385`.
- Bundle: [`MONAI/spleen_ct_segmentation` 0.6.1](https://huggingface.co/MONAI/spleen_ct_segmentation/tree/8c4da75225ff7cb30292729dd704cceccae5413c), revision `8c4da75225ff7cb30292729dd704cceccae5413c`.
- Pretrained `model.pt`: SHA-256 `502c312893994ec071a85c4f2e7d83a43f7789969faa73dae62f1291177f50fe`.
- Added dependencies are hash-locked in `requirements.txt`; framework and NumPy
  are supplied by the immutable base. Weights and configs are verified during
  build and execution. Inference requires no internet connection.

The model uses its published 3D residual UNet, orientation/intensity/spacing
transforms, 96×96×96 sliding windows, probability inversion and argmax. Full
volume stitching happens in host memory, so accelerator memory follows the
patch batch. The output retains input shape, affine, qform, sform, and spatial
and temporal units. Meter/micron coordinates are converted to millimeters for
the network and restored in the output. Labels are **0 background, 1 spleen**.

## Build and run on premises

Use an x86-64 Docker host. GPU execution additionally needs a compatible NVIDIA
driver and NVIDIA Container Toolkit. CUDA 12.8 runtime code covers Ada, Hopper,
and Blackwell; see `qualification.json` for measured cases rather than treating
architecture coverage as a completed GPU qualification.

```bash
cd templates/job-monai-segmentation
docker build -t monai-spleen-ct:0.6.1-r3 .
python3 fetch_example.py --output data
mkdir -p output/example
docker run --rm --gpus all --network none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/data:/data:ro" -v "$PWD/output/example:/output" \
  monai-spleen-ct:0.6.1-r3 \
  --input /data/image.nii.gz --output-dir /output
```

For CPU execution omit `--gpus all` and append `--device cpu`. A CPU run is an
explicit choice; a CUDA run fails clearly if no CUDA device is assigned.
The public example download is the official 1.6 GB archive, then extracts only
the ~10 MB image/label pair. Reuse an existing archive with
`--archive /path/Task09_Spleen.tar`. `spleen_56` belongs to the bundle's published
validation subset: sorted `imagesTr` filenames `[-9:]`. This is a regression
case, not independent clinical accuracy validation.

Bring your own `.nii` or `.nii.gz` by mounting it and changing `--input`. Inputs
must be one 3D CT volume with Hounsfield-unit intensities and valid geometry.
Every finite voxel is processed; filenames and checksums do not select an
optimized or alternate inference path. If the header omits spatial units,
verify the units and pass, for example,
`--parameters-json '{"spatial_units":"mm"}'`.

Parameters are `precision` (`float32` default, `float16`, `bfloat16`),
`sw_batch_size` (4 default), `overlap` (0.5 default, 0 inclusive to 1 exclusive),
and `spatial_units` (`header` default, `mm`, `meter`, `micron`). Precision and
overlap change computation and are recorded. Lower `sw_batch_size` to reduce
peak memory. CPU float16 is explicitly unsupported. Memory requirements grow
with volume dimensions; there is no artificial fixed dimension cutoff.

Each run writes:

```text
segmentation.nii.gz  uint8 mask in the input image's geometry
result.json         input/model/config hashes, labels, geometry, counts, timings
```

Use a new output directory per operation. Existing outputs are rejected, so a
retry cannot silently replace earlier scientific results. Terminating the
container stops the computation; an interrupted run restarts from its input,
without a claim of partial-inference checkpoint recovery.

## Validate a result

```bash
docker run --rm --network none --entrypoint /opt/conda/bin/python \
  -v "$PWD/data:/data:ro" -v "$PWD/output/example:/output:ro" \
  -v "$PWD/validate.py:/validate.py:ro" monai-spleen-ct:0.6.1-r3 \
  -I /validate.py --input /data/image.nii.gz --output-dir /output \
  --label /data/label.nii.gz --minimum-dice 0.90
docker run --rm --network none --entrypoint /opt/conda/bin/python \
  -v "$PWD/tests:/tests:ro" monai-spleen-ct:0.6.1-r3 \
  -I /tests/test_geometry.py
```

The 0.90 gate is predeclared for this pinned upstream validation case only;
arbitrary customer volumes are not required to contain a spleen or exceed a
guessed Dice score. Empty foreground can be a valid model output. Inspect the
mask with an appropriate NIfTI viewer before using it in further research.

## Nebius Serverless

Qualification status on 27 October 2026: the tested provider Job and Endpoint
services rejected immutable image digest references during image-label length
validation, before starting the container. The provider launch path below remains
unqualified pending that service correction. Docker and Kubernetes use the same
immutable image directly; do not replace its digest with a mutable tag to claim
equivalent qualification.

Build and push to **your** registry. This repository does not require access to
our private image registry. Preserve the image digest returned by the push.

```bash
MONAI_IMAGE="$MY_REGISTRY/monai-spleen-ct:0.6.1-r3"
docker build -t "$MONAI_IMAGE" .
docker push "$MONAI_IMAGE"
MONAI_DIGEST=$(docker image inspect --format '{{index .RepoDigests 0}}' "$MONAI_IMAGE")
```

Upload `data/image.nii.gz` to `inputs/image.nii.gz` in your existing bucket in
the same project and region as the Job. Configure your normal Nebius CLI
identity and set `NEBIUS_PROJECT_ID`, `MONAI_BUCKET`, `MONAI_PLATFORM`, and
`MONAI_PRESET` from that project's available inventory. A one-GPU L40S/RTX PRO
6000/H100/H200 candidate with at least 8 CPU cores and 32 GiB host RAM is a
starting shape, subject to the exact qualification matrix. The driver and
memory bound must fit your volume. The recipe does not expose an HTTP listener.

```bash
MONAI_RUN="monai-$(date -u +%Y%m%dT%H%M%SZ)"
nebius ai job create \
  --parent-id "$NEBIUS_PROJECT_ID" --name "$MONAI_RUN" \
  --image "$MONAI_DIGEST" --platform "$MONAI_PLATFORM" --preset "$MONAI_PRESET" \
  --on-demand --restart-policy never --timeout 1h --disk-size 100Gi \
  --volume "s3://$MONAI_BUCKET:/data:rw" \
  --container-command /opt/conda/bin/python \
  --args "-I -m monai_workflow.runtime --input /data/inputs/image.nii.gz --output-dir /data/results/$MONAI_RUN" \
  --dry-run
```

Review the generated plan, then repeat without `--dry-run` to launch. For a
private registry, add `--registry-secret "$REGISTRY_SECRET"` using a MysteryBox
secret with `REGISTRY_USERNAME` and `REGISTRY_PASSWORD`; do not put credentials
in source, the command string, or logs. Keep bucket access scoped to your data.
The Job's IAM identity and mounted storage provide authentication; no demo
bearer token or Scientific AI key is involved.

Use `nebius ai job logs JOB_ID --follow` and `nebius ai job get JOB_ID --format
json`. Success requires exit zero **and** the expected mask and result under
`results/$MONAI_RUN/` in the mounted bucket. Download them and run `validate.py`.
The runtime keeps temporary normalized images on local `/tmp` and writes
closed output files directly to the bucket mount; no append/rename semantics
are required. A failed run may leave incomplete files: retain its diagnostic
evidence and retry into a new run prefix after addressing the error.

Cancel only the intended running Job with `nebius ai job cancel JOB_ID`.
After collecting results, delete that finished Job with `nebius ai job delete
JOB_ID`; separately delete only its `results/$MONAI_RUN/` prefix when no longer
needed. Job deletion does not delete your bucket. Local `--rm` removes the
container; explicitly retain or remove your mounted `output/example` directory.

## Provider qualification with scoped object URLs

`provider_driver.py` is an optional finite transfer shim for a Job without a
bucket mount. Its local injected configuration contains one HTTPS GET URL for
`input.tar`, the archive SHA-256/size, one scoped HTTPS PUT URL for `output.tar`,
and the SHA-256 of an injected exec-form command file. No URLs or credentials
are baked into the image, passed in command arguments, or printed by the driver.
Use short-lived URLs covering the planned Job startup/runtime and download the
export before retiring the exact task-owned object prefix.

`provider-qualification-command.json` runs the **same pinned pretrained engine**
and geometry checks on the documented `spleen_56` example, with its predeclared
Dice gate. It is explicitly a regression command, not the general customer
input contract. Put only `image.nii.gz` and `label.nii.gz` from `fetch_example.py`
in `input.tar`. `provider-transfer.example.json` supplies the expected archive
identity for the retained deterministic archive; update SHA-256/size for your
actual tar packaging, while preserving the two individual file checksums in the
qualification command. For arbitrary CT volumes, use the normal recipe above;
do not apply the example's Dice or file-identity checks to customer data.

After creating scoped URLs with your normal object-storage credentials, create
an owner-readable configuration file from the example (mode0600), then inject:

```bash
--inject-file "$PWD/provider_driver.py:/run/provider_driver.py" \
--inject-file "$PWD/provider-qualification-command.json:/run/command.json" \
--inject-file "$TRANSFER_CONFIG:/run/transfer.json" \
--container-command /opt/conda/bin/python \
--args '-I /run/provider_driver.py --config /run/transfer.json --command /run/command.json'
```

Use these arguments in the finite Job command above without its volume/normal
inference arguments. The driver uses writable local temporary directories,
verifies input bytes before execution, and uploads closed scientific outputs,
`execution.log`, `qualification.json` and `transfer-result.json` in one tar.
Its final log records the exported tar SHA-256 and byte count; verify both after
download. A successful PUT is transfer evidence, not a claim that an independent
download has already been verified. Nonzero science exits remain failures even
when diagnostics upload succeeds. Do not retry inference after an upload
failure without first recovering or accounting for the completed output.

## Kubernetes on premises

`kubernetes-job.yaml` runs the general NIfTI CLI as one finite GPU Job. It uses
the image you built and pushed above, existing persistent volumes, a non-root
process, read-only input and root filesystem, and 32 GiB of local scratch. It
does not require the Scientific AI service or provider Serverless API.

On 27 October 2026 the same portable image passed a finite Kubernetes run on
one NVIDIA L40S in `eu-north1`, with 8 CPUs and 32 GiB RAM. The scoped-URL
qualification command processed held-out `spleen_56` in float32: independent
download validation measured Dice **0.936098**, above the predeclared 0.90 gate,
with exactly preserved affine, qform, sform, units, shape and uint8 labels.
Inference took 0.410 seconds and the engine 3.532 seconds; the whole Job took
38 seconds, including a reported 26.629-second image pull. These are one-run
measurements, not capacity estimates. The general PVC template passed client
validation; that storage route was not exercised by the scoped-URL run.

The same pinned image and command also passed separate H100 and H200 runs in
`eu-north1` and an RTX PRO 6000 Blackwell run in `eu-south1`. Independent checks
found identical masks on all four GPU types, with Dice 0.936098. Each GPU mask
differed from the CPU mask at 2 of 8,650,752 voxels. Full timings and image-pull
durations are retained in `qualification.json`; one run per GPU does not justify
a speed or cost preference, and native availability fallback remains untested.

Use an existing namespace with ordinary batch admission, an NVIDIA device
plugin, and a compatible GPU/driver. Prepare two existing PVCs: put the example
`data/image.nii.gz` (or your CT volume) on the input PVC using your storage's
normal upload client, and use a separate output PVC for retained results. The
volumes must permit UID/GID10001 access; the pod sets `fsGroup:10001`. Both PVCs
must be usable from the selected GPU node. For a private registry, add your
namespace's existing `imagePullSecrets` reference to the pod spec.

```bash
export MONAI_KUBE_CONTEXT=your-context
export MONAI_NAMESPACE=research
export MONAI_RUN="monai-$(date -u +%Y%m%dT%H%M%SZ)"
export MONAI_INPUT_PVC=medical-inputs
export MONAI_OUTPUT_PVC=medical-results
export MONAI_INPUT_FILE=image.nii.gz
export MONAI_DIGEST  # repository@sha256:... from your image push above
envsubst '${MONAI_NAMESPACE} ${MONAI_RUN} ${MONAI_INPUT_PVC} ${MONAI_OUTPUT_PVC} ${MONAI_INPUT_FILE} ${MONAI_DIGEST}' \
  < kubernetes-job.yaml > monai-job.rendered.yaml
kubectl --context "$MONAI_KUBE_CONTEXT" create --dry-run=client -f monai-job.rendered.yaml
```

Review the manifest and add your existing queue/admission labels if required.
The default requests one GPU, 8 CPUs and 32 GiB RAM; adjust host memory and
scratch for your volume. This is a resource envelope, not a maximum supported
image size. Hardware-specific selectors or tolerations belong to your cluster
configuration; the template does not claim that untested GPU types are
incompatible. To change inference parameters, append `--parameters-json` and a
JSON object to the container's `args`.

```bash
kubectl --context "$MONAI_KUBE_CONTEXT" create -f monai-job.rendered.yaml
kubectl --context "$MONAI_KUBE_CONTEXT" -n "$MONAI_NAMESPACE" logs -f "job/$MONAI_RUN"
kubectl --context "$MONAI_KUBE_CONTEXT" -n "$MONAI_NAMESPACE" get "job/$MONAI_RUN"
```

There is no retry after failure (`backoffLimit:0`), and the Job has an 1800-second
active deadline. A successful container must also produce `segmentation.nii.gz`
and `result.json` under the output PVC's `$MONAI_RUN/` directory. Retrieve them
with your storage client and run the validator above against the original CT.
Preserve the Job/Pod status, logs, actual image digest and validation result.
Cancel or clean up only this Job with `kubectl --context "$MONAI_KUBE_CONTEXT"
-n "$MONAI_NAMESPACE" delete job "$MONAI_RUN"`. Its PVC results remain; remove
only that run's output directory separately when it is no longer needed.

The scoped-URL driver above can also be mounted into Kubernetes from an
immutable ConfigMap, with the capability JSON in a read-only Secret. That is
the retained qualification route for the fixed example; its Dice and checksum
gates do not apply to this general PVC-based input path. Kubernetes qualification
does not establish provider Serverless or Scientific AI REST/MCP readiness.

## License and scope

MONAI and the selected bundle/weights are Apache-2.0; the bundle's full license
is retained at `bundle/LICENSE`. The example CT/label data is **CC-BY-SA-4.0**,
attributed to Medical Segmentation Decathlon and Memorial Sloan Kettering
Cancer Center; `fetch_example.py` writes the attribution beside the data.
See [the dataset publication](https://doi.org/10.1038/s41467-022-30695-9).
The pretrained bundle explicitly describes itself as an example, not intended
for diagnostic purposes. Framework licensing is not clinical certification.

This finite Job supports independent concurrent operations through the hosting
platform's admission, isolation and cancellation. It is not a shared HTTP
inference service with measured session capacity. GPU portability, provider
Serverless execution, and Scientific AI public-path evidence are reported
separately in `qualification.json`; no test of one implies the others.
