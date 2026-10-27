# MONAI Job with scoped object transfer

This route runs the general pretrained NIfTI engine with `provider_driver.py`.
It requires your own Nebius project/profile, registry, existing object-storage
bucket and ordinary S3 credentials. It needs no Scientific AI account, private
registry, application token, SSH key or bucket mount. Results persist in your
bucket after the Job stops. Local preparation/verification uses Python 3.11+.

The current qualification has passed the complete request dry-run with a short
repository name and a **full image digest**. Provider scientific execution is
still pending. The earlier long-reference label failure is retained; shortening
the repository path does not alter image bytes. The bucket-mounted example in
README.md is a separate unqualified transport.

## Prepare your image and input

Build/push the image as described in README.md, using a short repository such as
`$MY_REGISTRY/ms`. Set `MONAI_DIGEST` to that repository's full `@sha256:…`
reference from the push. Check the repository and all 64 digest characters;
do not substitute a mutable tag. Your project must be able to pull the image.
For an external private registry, use the CLI's `--registry-secret` with your
existing MysteryBox registry credentials.

Configure your existing Nebius CLI and S3 credential profiles without changing
their defaults. Set the following values for your own resources. The example
shape is one L40S with 16 vCPUs and 96 GiB RAM; choose an available compatible
shape with enough host memory for your volume.

```bash
export NEBIUS_PROFILE=your-existing-profile
export NEBIUS_PROJECT_ID=your-project-id
export MONAI_BUCKET=your-existing-bucket
export NEBIUS_S3_ENDPOINT=https://your-region-object-storage-endpoint
export AWS_DEFAULT_REGION=your-bucket-region
export MONAI_INPUT=/absolute/path/to/your-volume.nii.gz
export MONAI_PLATFORM=gpu-l40s-d
export MONAI_PRESET=1gpu-16vcpu-96gb
export MONAI_PARAMETERS_JSON='{}'
export MONAI_RUN="monai-$(date -u +%Y%m%dT%H%M%SZ)"
export MONAI_TRANSFER_DIR="$PWD/provider-runs/$MONAI_RUN"
python3 -m venv .provider-venv
.provider-venv/bin/pip install 'boto3==1.40.47'
```

The normal Boto3 credential chain supplies your existing S3 identity; set
`AWS_PROFILE` if needed. Never put access keys or signed URLs in source control,
shell tracing or shared logs. The following preparation uploads one archive to
a fresh prefix and creates a private configuration with object-scoped GET/PUT
capabilities lasting four hours. Adjust expiry to cover expected queue/startup
and the planned Job timeout. It makes no provider Job request.

```bash
.provider-venv/bin/python - <<'PY'
import hashlib, json, os, tarfile
from pathlib import Path
import boto3
from botocore.config import Config

os.umask(0o077)
source = Path(os.environ['MONAI_INPUT']).resolve()
if not source.is_file() or not source.name.lower().endswith(('.nii', '.nii.gz')):
    raise ValueError('Select one existing .nii or .nii.gz CT volume')
out = Path(os.environ['MONAI_TRANSFER_DIR'])
out.mkdir(parents=True, exist_ok=False)
archive = out / 'input.tar'
with tarfile.open(archive, 'w') as target:
    target.add(source, arcname=source.name, recursive=False)
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
bucket = os.environ['MONAI_BUCKET']
prefix = 'monai/' + os.environ['MONAI_RUN'] + '/'
s3 = boto3.client('s3', endpoint_url=os.environ['NEBIUS_S3_ENDPOINT'],
    region_name=os.environ['AWS_DEFAULT_REGION'],
    config=Config(signature_version='s3v4', retries={'max_attempts': 0}))
if s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1).get('Contents'):
    raise ValueError('Prefix already exists; retain it and choose a new run name')
identity = {'sha256': digest(archive), 'size_bytes': archive.stat().st_size}
(out / 'upload-intent.json').write_text(json.dumps({'bucket': bucket,
    'prefix': prefix, 'input': identity}, indent=2) + '\n')
with archive.open('rb') as body:
    s3.put_object(Bucket=bucket, Key=prefix+'input.tar', Body=body,
        ContentType='application/x-tar', IfNoneMatch='*')
response = s3.get_object(Bucket=bucket, Key=prefix+'input.tar')
check, size = hashlib.sha256(), 0
with response['Body'] as body:
    for block in iter(lambda: body.read(4*1024**2), b''):
        check.update(block); size += len(block)
if check.hexdigest() != identity['sha256'] or size != identity['size_bytes']:
    raise ValueError('Staged input integrity check failed; do not submit')
ttl = 14400
config = {'input': dict(identity, url=s3.generate_presigned_url('get_object',
    Params={'Bucket': bucket, 'Key': prefix+'input.tar'}, ExpiresIn=ttl)),
    'output': {'url': s3.generate_presigned_url('put_object', Params={
        'Bucket': bucket, 'Key': prefix+'output.tar',
        'ContentType': 'application/x-tar'}, ExpiresIn=ttl)},
    'command_sha256': digest(Path('provider-command.json'))}
(out / 'transfer.private.json').write_text(json.dumps(config, indent=2)+'\n')
print('Prepared private transfer files; no provider Job created.')
PY
```

`provider-command.json` accepts the single supplied volume at its original
basename inside the archive. It uses the ordinary engine and the requested
`MONAI_PARAMETERS_JSON` (defaults: float32, window batch 4, overlap 0.5, header
units). No reference label, filename identity or Dice gate is applied to customer
volumes. The fixed validation example uses the separate
`provider-qualification-command.json` and its documented regression gate.

## Dry-run and submit one finite Job

Use the current CLI's `ai job create --help` to verify available flags. Keep its
dry-run output private because injected file content can contain signed URLs.
No ports, public IP, SSH access or mounted volumes are needed for this route.

```bash
nebius --profile "$NEBIUS_PROFILE" --no-check-update --retries 1 --format json \
  ai job create --parent-id "$NEBIUS_PROJECT_ID" --name "$MONAI_RUN" \
  --image "$MONAI_DIGEST" --platform "$MONAI_PLATFORM" --preset "$MONAI_PRESET" \
  --on-demand --restart-policy never --timeout 30m --disk-size 100Gi \
  --env 'MONAI_CPU_THREADS=8' --env "MONAI_PARAMETERS_JSON=$MONAI_PARAMETERS_JSON" \
  --inject-file "$PWD/provider_driver.py:/run/provider_driver.py" \
  --inject-file "$PWD/provider-command.json:/run/command.json" \
  --inject-file "$MONAI_TRANSFER_DIR/transfer.private.json:/run/transfer.json" \
  --container-command /opt/conda/bin/python \
  --args '-I /run/provider_driver.py --config /run/transfer.json --command /run/command.json' \
  --dry-run > "$MONAI_TRANSFER_DIR/dry-run.private.json"
```

Inspect the exact image, GPU shape, timeout, zero retries and injected-file
paths. After approval, run the same command **once**, replacing `--dry-run` with
`--async` and writing its response to `create.private.json`. Retain the returned
operation and Job resource IDs. If creation has an unknown outcome, reconcile
the existing operation/resources before doing anything else; do not blindly
resubmit. A request dry-run does not prove image startup or scientific success.

## Retrieve and verify complete results

Use `nebius --profile "$NEBIUS_PROFILE" ai job get JOB_ID --format json` and
`nebius --profile "$NEBIUS_PROFILE" ai job logs JOB_ID --timestamps --tail 1000000`.
Retain full logs and check any truncation. Success requires terminal `COMPLETED`,
the driver's `execution_exit_code: 0` and `uploaded: true`, and independent byte
and semantic validation below. A successful diagnostic upload can accompany a
failed scientific command; it does not make the science successful.

Download exactly `monai/$MONAI_RUN/output.tar` from your bucket using the same
ordinary S3 identity, as below. Compare its complete SHA-256 and byte size to the
driver's actual final JSON record before extracting it. The expected general-command
archive contains exactly four regular files:

```text
segmentation.nii.gz  result.json  execution.log  transfer-result.json
```

Reject paths, links, duplicate entries or unexpected files. Verify every
scientific/log file against `transfer-result.json`; then run the existing
geometry/provenance validator with your original input. These commands assume
you have set `MONAI_OUTPUT_SHA` and `MONAI_OUTPUT_BYTES` from the actual driver
record. They download once to a new local archive and never overwrite it:

```bash
export MONAI_OUTPUT_SHA MONAI_OUTPUT_BYTES
.provider-venv/bin/python - <<'PY'
import hashlib, json, os, shutil, tarfile
from pathlib import Path
import boto3
from botocore.config import Config
root = Path(os.environ['MONAI_TRANSFER_DIR']); archive = root/'output.tar'
staged = json.loads((root/'upload-intent.json').read_bytes())
s3 = boto3.client('s3', endpoint_url=os.environ['NEBIUS_S3_ENDPOINT'],
    region_name=os.environ['AWS_DEFAULT_REGION'],
    config=Config(signature_version='s3v4', retries={'max_attempts': 0}))
response = s3.get_object(Bucket=staged['bucket'], Key=staged['prefix']+'output.tar')
assert response['ContentLength'] == int(os.environ['MONAI_OUTPUT_BYTES'])
with response['Body'] as body, archive.open('xb') as target:
    shutil.copyfileobj(body, target)
with archive.open('rb') as stream:
    checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
assert checksum == os.environ['MONAI_OUTPUT_SHA']
assert archive.stat().st_size == int(os.environ['MONAI_OUTPUT_BYTES'])
out = root/'result'; out.mkdir(exist_ok=False)
expected = {'segmentation.nii.gz','result.json','execution.log','transfer-result.json'}
with tarfile.open(archive) as source:
    entries = source.getmembers()
    assert len(entries) == 4 and {v.name for v in entries} == expected
    assert all(v.isfile() for v in entries)
    for entry in entries:
        with source.extractfile(entry) as body, (out/entry.name).open('xb') as target:
            shutil.copyfileobj(body, target)
receipt = json.loads((out/'transfer-result.json').read_bytes())
assert receipt['execution_exit_code'] == 0
assert receipt['input_sha256'] == staged['input']['sha256']
assert receipt['command_sha256'] == hashlib.sha256(Path('provider-command.json').read_bytes()).hexdigest()
assert set(receipt['files']) == expected-{'transfer-result.json'}
for name, identity in receipt['files'].items():
    path = out/name
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == identity['sha256']
    assert path.stat().st_size == identity['size_bytes']
print('Complete archive and per-file integrity verified.')
PY
docker run --rm --runtime=runc --network none \
  --entrypoint /opt/conda/bin/python \
  -v "$(dirname "$MONAI_INPUT"):/input:ro" \
  -v "$MONAI_TRANSFER_DIR/result:/output:ro" \
  -v "$PWD/validate.py:/validate.py:ro" "$MONAI_DIGEST" \
  -I /validate.py --input "/input/$(basename "$MONAI_INPUT")" --output-dir /output
```

The validator checks original shape, affine/forms/units, uint8 labels, source and
checkpoint provenance. Add a ground-truth label only when it is applicable to
your data; no guessed Dice threshold is imposed on arbitrary volumes.

If transfer fails after computation, retain the Job and inspect its exact owned
output/diagnostics before deciding whether a new scientific execution is needed.
Local `/tmp` is scratch, not durable storage; after provider shutdown those files
may be unavailable. An interrupted run has no inference checkpoint/resume claim.

## Cleanup and qualification boundary

Retain the accepted Job ID, terminal/accounting evidence, logs, archive and hashes
before deleting the exact finished Job with `nebius --profile "$NEBIUS_PROFILE"
ai job delete JOB_ID`. Verify that its owned compute and disk resources are gone;
terminal Job status alone is not proof that every billed resource was removed.
Delete only the two objects in your exact `monai/$MONAI_RUN/` prefix when no
longer needed. Preserve the bucket, credentials and unrelated runs. Protect or
remove the local private transfer file after its capabilities expire.

This finite route does not establish sustainable capacity, native GPU fallback,
owner cancellation during execution, or a speed/cost order. Qualification of a
fixed example remains separate from the general customer input contract.
