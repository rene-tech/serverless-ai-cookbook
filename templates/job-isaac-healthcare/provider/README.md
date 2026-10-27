# Finite Nebius Serverless Job with scoped object transfers

This runs the same portable Isaac launcher as Docker and Kubernetes, using your
project, image registry and object storage. It needs no Scientific AI account,
token or private Python package. The simulator uses local POSIX scratch; a
separate parent downloads an input archive and uploads the closed result archive.
The simulator child blocks Internet sockets, so it must use the image's assets.

**Qualification status (27 October 2026):** one real provider Job passed the
unchanged default 600-step-cap, seed-17, cameras-on workflow on L40S using the
short full-digest image. The task succeeded at step 534 and recorded 533 samples
with both 640×480 camera streams. Actual container manifest/config and NVIDIA
device/driver were observed; driver 580.173.02 provided Vulkan rendering.
All eight delivered files and the 302,612,480-byte outer archive passed full
requested-bucket SHA checks, followed by independent CPU scientific validation.
The simulator child's network-socket filter passed. This qualifies that finite
request and allocation, not shared capacity, other workflows or all SDK modes.

The first VM scheduling attempt reported `NotEnoughResources`; the provider
subsequently provisioned the same accepted Job. That first capacity failure is
retained separately from the successful simulation. No manual science replay,
restart or fallback Job was used. Docker/Kubernetes qualification is described
in the [main recipe](../README.md).

Long immutable references previously failed the provider's image-derived label
validation. Copying the same manifest and blobs into a short repository preserves
the full digest and passed that validation. The observed short reference was
119 characters. This is an observed workaround, not a universal length limit.
Keep the original failure if your reference is rejected; never shorten the
digest or execute through a mutable tag.

## Image and input

Build the [source image](../README.md#build-and-run-on-premises), review NVIDIA's
simulator, Kit and asset terms, and publish only to a registry permitted by your
license. Use an existing registry credential supported by your provider project.
There is no public prebuilt image in this recipe. If your built image already
has a long immutable repository reference, create an immutable short alias:

```bash
export BUILT_IMAGE='your-existing-registry/your-built-repository@sha256:YOUR_FULL_64_HEX_DIGEST'
export SHORT_REPOSITORY='cr.eu-north1.nebius.cloud/YOUR_REGISTRY_ID/ih'
export ISAAC_IMAGE="$SHORT_REPOSITORY@${BUILT_IMAGE##*@}"
crane copy --no-clobber "$BUILT_IMAGE" "$ISAAC_IMAGE"
test "$(crane digest "$BUILT_IMAGE")" = "$(crane digest "$ISAAC_IMAGE")"
```

Run the following from `templates/job-isaac-healthcare`. Export an installation
inventory from **your own exact image**. This is a CPU source/asset/import check;
it does not launch simulation or use a GPU. Its file hashes verify installation
integrity, not whether a scenario is allowed to execute.

```bash
umask 077
mkdir -p provider-run
docker run --rm --network none \
  --entrypoint /opt/i4h/arena/.venv/bin/python \
  -v "$PWD/provider:/run/provider:ro" \
  "$ISAAC_IMAGE" -I /run/provider/inspect_installation.py \
  --image "$ISAAC_IMAGE" > provider-run/installation.json

python provider/prepare_job.py bundle \
  --scenarios examples/scenarios.json --parameters examples/parameters.json \
  --output provider-run/input.tar
```

Use your own scenario and parameter file paths. The archive preserves their
bytes under the runtime's `scenarios.json` and `parameters.json` names. Add
scenarios, change names/seeds or request supported physics, camera, episode and
attempt settings normally. The default episode cap remains 600; an explicit
shorter cap can produce `task_complete=false`. Large scenario documents travel
in the archive and are not subject to the provider's injected-file size limit.

## Scoped object capabilities

Use an existing bucket and your existing object-storage credential profile.
Choose a new prefix for this execution. The example below conditionally uploads
one input, reads it back completely, then stores only run-scoped HTTPS URLs in
private files. It creates no bucket, tenant, API key or credential.

```bash
python -m venv provider-run/client-env
provider-run/client-env/bin/pip install 'nebius==0.6.29' boto3
export PROJECT_ID='YOUR_PROJECT_ID'
export S3_ENDPOINT='https://YOUR_OBJECT_STORAGE_ENDPOINT'
export AWS_DEFAULT_REGION='YOUR_BUCKET_REGION'
export BUCKET='YOUR_EXISTING_BUCKET'
export RUN_PREFIX='your-owned-prefix/isaac-run-001/'
export SSH_PUBLIC_KEY='/path/to/your/existing-key.pub'
# Authenticate with your existing AWS/object-storage profile or credential chain.

provider-run/client-env/bin/python - <<'PY'
import hashlib, json, os
from pathlib import Path
import boto3
from botocore.config import Config

root = Path('provider-run/capabilities')
root.mkdir(mode=0o700, exist_ok=False)  # Do not replay an uncertain upload.
source = Path('provider-run/input.tar')
digest = hashlib.sha256(source.read_bytes()).hexdigest()
client = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT'],
    region_name=os.environ['AWS_DEFAULT_REGION'],
    config=Config(signature_version='s3v4', retries={'max_attempts': 0}))
bucket, prefix = os.environ['BUCKET'], os.environ['RUN_PREFIX']
assert prefix and prefix.endswith('/')
assert not client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1).get('Contents')
(root/'upload-intent.json').write_text(json.dumps({'bucket': bucket,
    'key': prefix+'input.tar', 'sha256': digest})+'\n')
with source.open('rb') as stream:
    client.put_object(Bucket=bucket, Key=prefix+'input.tar', Body=stream,
        ContentType='application/x-tar', IfNoneMatch='*', Metadata={'sha256': digest})
body = client.get_object(Bucket=bucket, Key=prefix+'input.tar')['Body']
actual, size = hashlib.sha256(), 0
try:
    for block in iter(lambda: body.read(4*1024**2), b''):
        actual.update(block); size += len(block)
finally:
    body.close()
assert actual.hexdigest() == digest and size == source.stat().st_size
for filename, operation, params in [
    ('input-url', 'get_object', {'Bucket': bucket, 'Key': prefix+'input.tar'}),
    ('output-url', 'put_object', {'Bucket': bucket, 'Key': prefix+'output.tar',
                                'ContentType': 'application/x-tar'}),
    ('claim-url', 'put_object', {'Bucket': bucket, 'Key': prefix+'started.json',
                               'ContentType': 'application/json', 'IfNoneMatch': '*'})]:
    url = client.generate_presigned_url(operation, Params=params, ExpiresIn=14400)
    (root/filename).write_text(url+'\n')
PY
```

Keep these URL files and rendered request JSON private: each URL is a temporary
capability. Do not print or commit them. Select a lifetime covering queue/startup,
the declared job timeout and delivery; expired URLs must not trigger a blind
simulation replay. The conditional start marker also prevents the same request
from rerunning science after an uncertain launch.

## Render, dry-run, then create once

The initial shape is L40S, 16 vCPU, 96 GB RAM, 250 GiB network disk and 16 GiB
shared memory, with a 7200-second Job deadline and a 6600-second science timeout.
These are explicit allocations, not a throughput or capacity guarantee. The
renderer exposes corresponding options and preserves your choices. Select an
available compatible RTX platform in your project; H100/H200 lack the required
rendering RT cores. The 32 GiB output export budget is configurable with
`--output-max-bytes`; exceeding it fails without truncating completed output.

```bash
python provider/prepare_job.py render \
  --image "$ISAAC_IMAGE" --project-id "$PROJECT_ID" --name isaac-run-001 \
  --input provider-run/input.tar --installation provider-run/installation.json \
  --input-url-file provider-run/capabilities/input-url \
  --output-url-file provider-run/capabilities/output-url \
  --claim-url-file provider-run/capabilities/claim-url \
  --output provider-run/request --accept-eula \
  --diagnostics-public-ip --ssh-public-key "$SSH_PUBLIC_KEY"

provider-run/client-env/bin/python provider/submit_job.py \
  --request provider-run/request/job-dry-run.private.json \
  --request-sha256 "$(sha256sum provider-run/request/job-dry-run.private.json | cut -d' ' -f1)" \
  --output provider-run/dry-run
```

Review the actual dry-run response and the full request before the separate
billable create command. The helper requires the exact successful dry-run
request; it makes one SDK create attempt and retains uncertain outcomes. It has
no automatic retry, restart, next-job scheduler or cleanup action.

```bash
provider-run/client-env/bin/python provider/submit_job.py \
  --request provider-run/request/job-create.private.json \
  --request-sha256 "$(sha256sum provider-run/request/job-create.private.json | cut -d' ' -f1)" \
  --successful-dry-run provider-run/dry-run/receipt.json \
  --output provider-run/create-once --execute
```

The command above matches the measured diagnostic shape: a public IP and only
your existing SSH public key, with no workload HTTP ports or bucket mount. The
renderer can omit both diagnostic options for a request without a public IP;
that network variant was not separately executed in this qualification. Bind the returned Job
to its reported compute instance and authoritative IP before SSH; use a
run-specific known-hosts file and your existing key. A provider `spec.image`
field proves the requested reference, not the observed container image. Docker's
actual config ID/RepoDigests and `nvidia-smi` supply the separate runtime proof.

## Results and cleanup

Retain the returned Job/operation ID immediately. If create or observation
disconnects, read that same Job; do not submit it again.

```bash
export JOB_ID='ID_RETURNED_BY_YOUR_CREATE'
nebius ai job get --id "$JOB_ID"
nebius ai job logs "$JOB_ID" --timestamps --tail 1000
```

The provider log API accepts at most 1000 lines per request; preserve earlier
snapshots and use the installed CLI's time filters to retrieve longer histories.
Automatic provider provisioning retries can occur before workload execution even
with `restartAttempts=0`; they do not establish that science ran again. Preserve
the Job and its operation errors while determining capacity or startup failures.

The transfer log reports `uploaded`, `execution_exit_code`, `output_sha256` and
`output_size_bytes`. Read **your exact `RUN_PREFIX/output.tar`** back from the
bucket in full and verify both digest and byte length against that receipt.
Safely extract regular files only, rejecting absolute/traversal paths, links and
duplicate entries. Check every `transfer-result.json.files` size/hash and run
`validate_artifacts.py` against your original JSON documents plus
`science/result.json` and `science/simulation.tar`, using the same portable
image's Python in a CPU-only Docker container. The delivered
`semantic-validation.json` records the in-job check; independent verification
should retain its own report.

For example, set the two expected values from your retained transfer log, then:

```bash
export OUTPUT_SHA256='SHA256_REPORTED_BY_YOUR_TRANSFER_LOG'
export OUTPUT_SIZE_BYTES='BYTE_LENGTH_REPORTED_BY_YOUR_TRANSFER_LOG'
aws --endpoint-url "$S3_ENDPOINT" s3api get-object \
  --bucket "$BUCKET" --key "${RUN_PREFIX}output.tar" provider-run/output.tar \
  > provider-run/output-object.private.json
python - <<'PY'
import hashlib, json, os, tarfile
from pathlib import Path, PurePosixPath

root = Path('provider-run')
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
assert digest(root/'output.tar') == os.environ['OUTPUT_SHA256']
assert (root/'output.tar').stat().st_size == int(os.environ['OUTPUT_SIZE_BYTES'])
for source, destination in [('input.tar', 'input'), ('output.tar', 'delivered')]:
    target = root/destination; target.mkdir(exist_ok=False)
    with tarfile.open(root/source, 'r:') as archive:
        seen = set()
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            assert '\\' not in member.name and member.name not in seen
            seen.add(member.name)
        archive.extractall(target, filter='data')
data = root/'delivered'
transfer = json.loads((data/'transfer-result.json').read_bytes())
assert transfer['input_sha256'] == digest(root/'input.tar')
files = {str(p.relative_to(data)): p for p in data.rglob('*') if p.is_file()}
assert set(files) == set(transfer['files']) | {'transfer-result.json'}
for name, expected in transfer['files'].items():
    assert digest(files[name]) == expected['sha256']
    assert files[name].stat().st_size == expected['size_bytes']
print(json.dumps({'delivery_sha256_verified': True,
                  'execution_exit_code': transfer['execution_exit_code']}))
PY
docker run --rm --network none \
  --entrypoint /opt/i4h/arena/.venv/bin/python \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/provider:/run/provider:ro" -v "$PWD/provider-run:/case" \
  "$ISAAC_IMAGE" -I /run/provider/validate_artifacts.py \
  --input /case/input/scenarios.json --parameters /case/input/parameters.json \
  --result /case/delivered/science/result.json \
  --archive /case/delivered/science/simulation.tar \
  --output /case/independent-semantic-validation.json
```

If the execution failed before science produced those files, retain the transfer
receipt and full diagnostic log as failure evidence; do not manufacture a
scientific validation result or repeat the accepted Job.

Inspect task outcomes, trajectories and RGB frames. Successful transfer or Job
completion does not imply a successful grasp, warning-free USD composition or
quantitative physical accuracy. Keep the full `execution.log`, upstream warnings,
installed source check and offline-execution receipt. Device diagnostics belong
in your operator evidence, separate from the public scientific archive.

If upload fails, preserve the original Job/VM and export the closed local output
before cleanup. After results/logs are exported and verified, delete only your
returned Job using the installed CLI's `job delete` command, then verify its
associated compute instance, runtime disk and diagnostic public IP are gone.
Treat an uncertain deletion as a GET-only reconciliation task. Do not delete
existing endpoints or shared storage. Bucket objects remain until you explicitly
remove only your owned run prefix. Cross-attempt simulator checkpoint resume is
not implemented.

This scoped-transfer Job does not qualify provider bucket-mount POSIX behavior,
an always-running Endpoint, WebRTC transport, other SDK policies or arbitrary
GPU architectures. Those remain separate contracts and tests.
