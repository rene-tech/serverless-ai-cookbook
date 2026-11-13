# One caller-owned CT volume, from upload to verified mask

Use Bash in a fresh private working directory; run the blocks in the same shell.
Requires Python 3, `tar`, AWS CLI v2,
`curl`, `jq` and `sha256sum`; it does not install a scientific engine. Obtain the
API token and scoped bucket credentials through normal onboarding/secret storage.
Keep them out of files, examples and chat. The service's commercial-use restrictions
still apply. Use data you are entitled to process; do not download a clinical case
merely to fill an example.

Set the configured scientific API and existing storage binding. Prepare your
compressed 3D Hounsfield CT as `prepared/image.nii.gz`:

```sh
set -euo pipefail
umask 077
: "${SCIENTIFIC_AI_URL:?Set your scientific API origin}"
: "${SCIENTIFIC_AI_TOKEN:?Load your individual API token securely}"
: "${SCIENTIFIC_DATA_ENDPOINT:?Set your bound HTTPS S3 endpoint}"
: "${SCIENTIFIC_DATA_BUCKET:?Set your existing bound bucket}"
: "${SCIENTIFIC_DATA_REGION:?Set its storage signing region}"
: "${INPUT_KEY:?Choose a fresh object key in your bound bucket}"
export INPUT_KEY
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/monai-spleen-ct?workflow=segment" > model.json
jq '{model,default_version,versions,workflow:.workflows.segment}' model.json

tar -czf input.tar.gz -C prepared image.nii.gz
aws s3 cp input.tar.gz "s3://$SCIENTIFIC_DATA_BUCKET/$INPUT_KEY" \
  --endpoint-url "$SCIENTIFIC_DATA_ENDPOINT" --region "$SCIENTIFIC_DATA_REGION"
python3 - <<'PY' > request.json
import hashlib, json, os
from pathlib import Path
p = Path('input.tar.gz')
h = hashlib.sha256()
with p.open('rb') as source:
    for chunk in iter(lambda: source.read(4 << 20), b''):
        h.update(chunk)
request = {'model': 'monai-spleen-ct', 'workflow': 'segment', 'version': 'bundle-0.6.1',
    'parameters': {'precision': 'float32', 'sw_batch_size': 4, 'overlap': 0.5,
                   'spatial_units': 'header', 'image_path': 'data/inputs/image.nii.gz'},
    'inputs': [{'name': 'input.tar.gz', 'key': os.environ['INPUT_KEY'],
                'sha256': h.hexdigest(), 'size_bytes': p.stat().st_size}]}
for field in ('region', 'gpu'):
    if os.environ.get('SCIENTIFIC_AI_' + field.upper()):
        request[field] = os.environ['SCIENTIFIC_AI_' + field.upper()]
print(json.dumps(request))
PY
```

Storage credentials are the caller's existing AWS environment/profile/session;
they are **not** request parameters. The input key is in that identity's bound
bucket, even if another bucket contains an object with the same key. Have the
platform configure an approved alternative binding before using another bucket.
Optional `SCIENTIFIC_AI_REGION`/`SCIENTIFIC_AI_GPU` must name allowed choices.

Save one logical request key. Choose REST **or** MCP submission; switching clients
does not justify a new key or a second job:

```sh
test -f request-key.txt || python3 -c 'import uuid; print(uuid.uuid4())' > request-key.txt
REQUEST_KEY=$(cat request-key.txt)
```

For REST, submit once:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  -H 'Content-Type: application/json' -H "Idempotency-Key: $REQUEST_KEY" \
  --data-binary @request.json "$SCIENTIFIC_AI_URL/v1/runs" > submitted.json
RUN_ID=$(jq -er '.run_id' submitted.json)
```

For MCP, connect your ordinary client to `$SCIENTIFIC_AI_URL/mcp` with its secure
authentication configuration. Call `monai-spleen-ct_segment` with the JSON produced
by this command; these are typed arguments, not a JSON string:

```sh
jq --rawfile key request-key.txt \
  'del(.model,.workflow)+{idempotency_key:($key|rtrimstr("\n"))}' \
  request.json > mcp-arguments.json
```

Retain the returned `run_id`. Poll the same run, for example every 15 seconds;
client disconnection does not stop durable work. Do not blindly repeat an uncertain
POST: keep the identical request/key and reconcile it using the
[shared client procedure](../../runai-scientific-gateway/references/client.md).

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/runs/$RUN_ID" > status.json
jq '{run_id,model,workflow,version,phase,error}' status.json
```

Continue until a terminal phase. `SUCCEEDED` permits result retrieval; on failure,
inspect the public error and any diagnostic artifacts rather than claiming a mask
exists. MCP equivalents are `md_run_status` and `md_run_artifacts` with `run_id`.
After success:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/runs/$RUN_ID/artifacts" > artifacts.json
for name in segmentation.nii.gz result.json; do
  path="data/outputs/segment/$name"
  url=$(jq -er --arg p "$path" '.files[]|select(.path==$p)|.download_url' artifacts.json)
  sha=$(jq -er --arg p "$path" '.files[]|select(.path==$p)|.sha256' artifacts.json)
  bytes=$(jq -er --arg p "$path" '.files[]|select(.path==$p)|.size_bytes' artifacts.json)
  curl --fail-with-body --silent --show-error --output "$name" -- "$url"
  printf '%s  %s\n' "$sha" "$name" | sha256sum --check
  test "$(wc -c < "$name")" -eq "$bytes"
done
jq '{status,bundle,bundle_version,parameters,validation,timings_s}' result.json
```

The storage download command deliberately has **no API bearer header**. Signed
links and `artifacts.json` are temporary credentials; keep them private and refresh
expired links through the same run. Results remain in the owner's bucket after job
scratch deletion. Inspect the binary mask/physical geometry as described by the
model skill; a successful transfer is not an anatomical accuracy guarantee.
