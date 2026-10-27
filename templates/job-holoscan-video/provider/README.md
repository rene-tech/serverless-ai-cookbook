# Finite provider Job with scoped object transfer

Use your own registry, project, existing S3-compatible bucket and credentials.
The portable Holoscan image, `transfer.py` and `run_bundle.py` are independent of
Scientific AI. The same files also run on premises.

On 27 October 2026 a **119-character short repository reference with the complete
SHA-256 digest** passed an actual provider Job SDK dry-run. Its manifest, config
and all layers matched the previously qualified portable image. A real provider
Job has been accepted; runtime, outputs and resource closeout remain pending.
A dry-run or accepted ID is not GPU execution qualification.

The longer immutable reference previously failed both Job and Endpoint dry-runs
with `metadata.labels: label value length (...) exceeds maximum value (64)`.
Captured requests contained no metadata labels. Provider-side label generation
is an inference from those requests/errors, not a confirmed implementation fact.
A short repository path worked for this exact dry-run; it is not a universal
length guarantee. Keep the **entire digest** and validate your own exact request.
Do not replace it with a mutable tag or silently retry a failed create.

## Image and input

Build the image as described in the [main recipe](../README.md). Push it to a
short repository in your own registry, using your normal registry login:

```bash
export IMAGE_TAG="YOUR_REGISTRY/hv:holoscan-5.0.0"
docker tag holoscan-video:5.0.0 "$IMAGE_TAG"
docker push "$IMAGE_TAG"
docker image inspect "$IMAGE_TAG" --format '{{json .RepoDigests}}'
export IMAGE="YOUR_REGISTRY/hv@sha256:FULL_RETURNED_DIGEST"
```

When copying an existing immutable image to a shorter repository, preserve the
manifest and verify its returned digest, config and layers. A rebuilt image has
its own digest and needs its own runtime check. Keep registry passwords outside
commands, image layers and request JSON. Grant the provider read access using
your registry's supported identity integration.

Create one uncompressed tar containing `parameters.json`, the pinned
`tool_loc_convlstm.onnx`, its license and your recording. `video_file` selects an
ordinary relative tar member; names and parameter variations are not fixture
eligibility checks. For the optional downloaded research sample:

```bash
python3 src/prepare_sample.py --output sample
python3 - <<'PY'
import json
from pathlib import Path
Path('sample/parameters.json').write_text(json.dumps({
    'video_file': 'surgical_video.264', 'frame_count': 30
}) + '\n')
PY
tar -C sample -cf input.tar parameters.json surgical_video.264 \
  tool_loc_convlstm.onnx NVIDIA-Clara-Holoscan-SDK-EULA.pdf
```

For your own supported recording, replace the video and set `video_file` and the
frame options accordingly. Nested relative filenames are supported. Tar links,
duplicate members and paths outside the archive are rejected. Model validation,
encoded/display geometry and scientific outputs are described in the main recipe.

## Scoped input GET and output PUT

Use a **new owned object prefix for each intended execution**. Upload `input.tar`
once, then create a read URL for that exact object and a write URL for its exact
`output.tar`. Keep broad account credentials on your workstation or secret store;
the workload receives only these two temporary capabilities. Choose URL expiry
long enough for image pull, execution and export. Size scratch and the output
budget for your own frame count; the example values below are not product limits.

This example uses your normal boto3 credential chain, an existing bucket and a
fresh UUID prefix. Install boto3 in your own environment if needed. Set
`S3_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, `S3_BUCKET`, `INPUT_TAR`,
`PRIVATE_TRANSFER_JSON`, `TRANSFER_TTL_SECONDS`, `OUTPUT_MAX_BYTES` and
`EXECUTION_TIMEOUT_SECONDS`; keep the private JSON outside version control.

```python
import hashlib, json, os, uuid
from pathlib import Path
import boto3
from botocore.config import Config

os.umask(0o077)
archive = Path(os.environ['INPUT_TAR'])
with archive.open('rb') as source:
    checksum = hashlib.file_digest(source, 'sha256').hexdigest()
bucket = os.environ['S3_BUCKET']
prefix = 'holoscan/' + uuid.uuid4().hex + '/'
s3 = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT_URL'],
                  region_name=os.environ['AWS_DEFAULT_REGION'],
                  config=Config(signature_version='s3v4'))
s3.upload_file(str(archive), bucket, prefix + 'input.tar')
ttl = int(os.environ['TRANSFER_TTL_SECONDS'])
transfer = {
    'input': {
        'url': s3.generate_presigned_url('get_object', Params={
            'Bucket': bucket, 'Key': prefix + 'input.tar'}, ExpiresIn=ttl),
        'sha256': checksum, 'size_bytes': archive.stat().st_size,
    },
    'output': {
        'url': s3.generate_presigned_url('put_object', Params={
            'Bucket': bucket, 'Key': prefix + 'output.tar',
            'ContentType': 'application/x-tar'}, ExpiresIn=ttl),
        'max_bytes': int(os.environ['OUTPUT_MAX_BYTES']),
        'headers': {'Content-Type': 'application/x-tar'},
    },
    'execution_timeout_s': int(os.environ['EXECUTION_TIMEOUT_SECONDS']),
}
with Path(os.environ['PRIVATE_TRANSFER_JSON']).open('x') as target:
    json.dump(transfer, target, indent=2)
print(json.dumps({'bucket': bucket, 'prefix': prefix,
                  'input_sha256': checksum, 'input_size_bytes': archive.stat().st_size}))
```

The transfer helper verifies the complete downloaded bytes before starting
science, rejects redirects, runs a finite subprocess group and uploads closed
outputs plus logs and inventory. Its errors omit capability URLs. A science
timeout exports diagnostics with exit code 124. Local scratch and engine cache
stay off object storage. Finite Job mode needs no Endpoint start marker or idle
loop. Bucket-mounted transport is a separate, **untested** provider path.

## Prepare, dry-run and create once

Choose an available platform/preset compatible with the exact image; four GPU
architectures have portable execution evidence in [QUALIFICATION.md](../QUALIFICATION.md).
The current provider trial uses one L40S, eight CPUs, 32 GiB RAM, 100 GiB disk and
16 GiB shared memory, with a 1,800-second science timeout inside a 2,400-second
Job deadline. This is a finite trial envelope, not a capacity claim.

```bash
python3 provider/prepare_job.py \
  --image "$IMAGE" --project "$NEBIUS_PROJECT_ID" --name "$RUN_NAME" \
  --platform "$HOLOSCAN_PLATFORM" --preset "$HOLOSCAN_PRESET" \
  --transfer-config "$PRIVATE_TRANSFER_JSON" --output "$PRIVATE_REQUEST_JSON" \
  --disk-gib 100 --shm-gib 16 --timeout-seconds 2400
```

This offline builder injects the unchanged transfer and bundle scripts plus an
exec-form command protected by SHA-256. Both outer and science launch retain the
official compatibility wrapper and isolated Python mode. It sets zero restart
attempts, on-demand pricing, no workload ports and no bucket mounts. By default
it requests no public IP. If you need authorized host diagnostics, pass
`--ssh-public-key /path/to/YOUR_EXISTING_KEY.pub`; this adds only that public key
and a public IP, without a workload port. The current provider trial includes
this diagnostic option. Network reachability and registry/object egress remain
requirements of your selected platform.

Use an isolated environment with the reviewed official `nebius==0.6.29` SDK and
your own existing Nebius CLI profile. The generated request has `dry_run: true`.
The following is **one API call**; save the returned operation without printing
or sharing the private request containing capability URLs:

```python
import hashlib, json, os
from pathlib import Path
from nebius.aio.cli_config import Config
from nebius.sdk import SDK
from nebius.api.nebius.ai.v1 import CreateJobRequest, JobServiceClient

os.umask(0o077)
request_bytes = Path(os.environ['PRIVATE_REQUEST_JSON']).read_bytes()
request = CreateJobRequest.from_json(request_bytes.decode())
assert request.spec.restart_attempts == 0
output = Path(os.environ['PRIVATE_OPERATION_JSON'])
if output.exists():
    raise RuntimeError('Preserve the prior operation; reconcile it instead of resubmitting')
with Path(str(output) + '.intent').open('x') as intent:
    json.dump({'request_sha256': hashlib.sha256(request_bytes).hexdigest(),
               'dry_run': request.dry_run, 'maximum_create_calls': 1}, intent)
sdk = SDK(config_reader=Config(profile=os.environ['NEBIUS_PROFILE'], max_retries=1),
          federation_invitation_no_browser_open=True)
try:
    operation = JobServiceClient(sdk).create(request, retries=1,
                                            timeout=60, per_retry_timeout=60).wait()
    with output.open('x') as target:
        target.write(operation.raw().to_json())
    print(json.dumps({'operation_id': operation.id, 'resource_id': operation.resource_id,
                      'done': operation.done(), 'successful': operation.successful()}))
finally:
    sdk.sync_close()
```

The retained successful SDK dry-run returned operation ID `dry-run` with an
empty resource ID; it created no Job. Check the completed successful operation
and absence of a resource, then review its exact image, command, resources and
transfer configuration. For the intended
execution, make a private copy changing **only** `dry_run` to `false`, select a
new operation-output filename, record that you are about to submit, then run the
same SDK block **once**. If the response is uncertain, reconcile the saved
operation/name through GET/list; do not repeat create. Protobuf JSON may omit the
zero restart field when serializing; its typed value must still be zero.

## Results, actual identity and closeout

Retain the returned Job ID and inspect it and its logs using your CLI profile:

```bash
nebius ai job get --id "$JOB_ID" --format json
nebius ai job logs "$JOB_ID" --timestamps
```

The transfer log reports `output_sha256`, `output_size_bytes`,
`execution_exit_code` and `uploaded`. Download the exact output object using your
normal object-storage client, compare its **full** size/SHA with that record,
and inspect every file listed by `result.json`. A terminal Job status alone does
not establish output delivery or scientific success. Extract only into a new
owned directory, then run the unchanged portable semantic validator without a GPU:

```bash
docker run --rm --runtime=runc --network=none --read-only \
  -v "$PWD/downloaded-output:/output:ro" --entrypoint python3 "$IMAGE" \
  -I -c 'import sys; from pathlib import Path; sys.path.insert(0,"/opt/holoscan-video"); from holoscan_video import validate_result; print(validate_result(Path("/output")))'
```

Check selected frame count and cadence, seven ordered tool rows per frame,
finite mask channels, encoded/display coordinate metadata and optional video
size/frame count. Model predictions are research outputs, not clinical accuracy.
The provider Job's requested image field is **not** an observed runtime digest.
For an identity audit, join the exact Job's returned VM to its authoritative
Compute IP, then use your authorized host access to read Docker `.Image` and
image `RepoDigests`, plus the actual GPU and driver. Preserve errors as unknown;
do not inspect unrelated hosts or infer actual bytes from a mutable tag.

After exporting logs, full output hashes and scientific validation, confirm the
Job is terminal and its exact Compute instance is stopped/absent. Use your
installed CLI's help to cancel only that ID if required, and to delete that exact
Job after retention requirements are met. Keep an uncertain operation reserved
until reconciled. Delete only its owned input/output prefix when no longer needed;
Job deletion does not remove those objects or the image. Compute, storage and
image pulls may be billed. There is no persistent stream or HTTP inference server.

The older [Endpoint preparation helper](prepare_endpoint.py) is retained for the
recorded diagnostic. Its long-reference dry-run failed; Endpoint execution and
bucket mounts remain unqualified. Do not treat it as the preferred finite path.
