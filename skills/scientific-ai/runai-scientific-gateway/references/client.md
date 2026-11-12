# Portable Scientific AI Run:ai client

Use `curl`, `jq`, Python 3 standard library and, for direct bucket transfers,
AWS CLI v2. An ordinary configured MCP client can call the named tools below;
no LibreChat-only helper or native Run:ai administration client is needed.

Read the individual model skill before preparing scientific data. Commands use
existing credentials from environment/approved secret storage. Never paste keys
into chat or save them in request JSON.

## Discover an authorized workflow

Set `SCIENTIFIC_AI_URL` and `SCIENTIFIC_AI_TOKEN` through the approved client
configuration. The URL is the supplied scientific API base without a trailing
slash. A token must be valid for this service and the caller's approved grant.

```sh
: "${SCIENTIFIC_AI_URL:?Set the scientific API base URL}"
: "${SCIENTIFIC_AI_TOKEN:?Load your access token securely}"
MODEL=gromacs
WORKFLOW=hecbiosim-20k
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/$MODEL" > model.json
jq --arg w "$WORKFLOW" '.workflows[$w]' model.json
jq --arg w "$WORKFLOW" '.workflows[$w].example' model.json > request.json
```

The example is usable only when its referenced template exists in **your own**
bound bucket. Inspect its input contract and scientific settings; do not assume a
template is a scientifically appropriate production protocol. REST model detail
is a direct object containing `model` and `workflows`. In MCP use `md_models`
with `{"model":"gromacs","detail":true}` and select its `gromacs` entry, then
the exact workflow tool in its skill. Compact listing uses `detail:false` with `limit`/`offset`;
do not load every model's detailed schema into an agent context at once.

## Prepare and upload caller-owned data

Input is one regular gzip-compressed tar archive, identified as `input.tar.gz`,
with its SHA-256 and compressed byte count. The API uses bucket object references;
it does not require the other backend's artifact manifest or upload handles.
Archive members are relative scientific filenames. No absolute paths, parent
traversal, symlinks, hidden runtime state or unreviewed executable files.

For binder workflows, archive members such as `target.pdb` and `settings.json`
stage below the logical `data/inputs/` directory. MD archive members stage below
logical `data/`. These are public workflow-relative names, not host paths. Follow
the specific model's required member tree and preserve declared trusted controls.

Example for a workflow requiring exactly these two prepared binder files:

```sh
: "${INPUT_KEY:?Choose a new object key in your bound bucket}"
export INPUT_KEY
tar -czf input.tar.gz -C prepared-inputs target.pdb settings.json
python3 - <<'PY' > input-reference.json
import hashlib, json, os
from pathlib import Path
p = Path('input.tar.gz')
h = hashlib.sha256()
with p.open('rb') as source:
    for chunk in iter(lambda: source.read(4 << 20), b''):
        h.update(chunk)
print(json.dumps({'name': 'input.tar.gz', 'key': os.environ['INPUT_KEY'],
                  'sha256': h.hexdigest(), 'size_bytes': p.stat().st_size}))
PY
```

Set `INPUT_KEY` to a new authorized object key before running that command.
For example, use `work/your-campaign/input.tar.gz` in your existing bucket.
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and any required session token must
come from the caller's approved bucket credential source. The endpoint, region
and bucket below must match the data source bound to this scientific identity.

```sh
aws s3 cp input.tar.gz "s3://$SCIENTIFIC_DATA_BUCKET/$INPUT_KEY" \
  --endpoint-url "$SCIENTIFIC_DATA_ENDPOINT" --region "$SCIENTIFIC_DATA_REGION"
jq --slurpfile input input-reference.json '.inputs=[$input[0]]' \
  request.json > request-with-input.json
mv request-with-input.json request.json
```

For a different bucket, arrange the approved owner binding first. Passing an
endpoint or cloud key inside `parameters` does not change authorization.

## Submit once, then poll the same run

Select the exact supported scientific `version` if reproducibility requires it.
Set `region` only when an authorized region is requested; otherwise qualified
placement chooses eligible compute. Optional `gpu`, `pvc_gib` and output budgets
must follow the live schema and actual workload size. Do not raise budgets or
shorten the science merely to make a test pass.

```sh
test -f request-key.txt || python3 -c 'import uuid; print(uuid.uuid4())' > request-key.txt
REQUEST_KEY=$(cat request-key.txt)
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  -H 'Content-Type: application/json' -H "Idempotency-Key: $REQUEST_KEY" \
  --data-binary @request.json "$SCIENTIFIC_AI_URL/v1/runs" > submitted.json
RUN_ID=$(jq -er '.run_id' submitted.json)
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/runs/$RUN_ID" > status.json
jq '{run_id,model,workflow,version,phase,error}' status.json
```

Persist `request.json`, `request-key.txt` and `submitted.json` in the caller's
workspace. Repeat an uncertain submission with the **same** key and unchanged
request. A changed body with a reused key returns a conflict; a deliberate new
simulation/design gets a new key in a new request directory.

Find the caller's existing runs with `GET /v1/runs?limit=20`: REST returns a JSON
array and, when another page exists, an `X-Next-Cursor` response header. Pass that
header value as the next URL-encoded `cursor` query parameter. MCP `md_run_list`
with `{"limit":20}` returns `{runs,next_cursor}`; pass `next_cursor` as `cursor`.
Add a model/phase filter when useful. This lists only authorized owner runs, not
another user's work. Keep the original run ID when reconnecting.

Poll at about 15-second intervals while active, with the client's own bounded
observation window. On disconnection or observation timeout, report the run ID
and reconnect later; do not declare a still-running job failed. Terminal phases
are `SUCCEEDED`, `FAILED`, `CANCELLED` and `TIMED_OUT`. Long MD jobs retain their
two-week total server deadline across attempts; other workflow budgets are stated
by the live model contract. A submission acknowledgement is not a result.

### Equivalent MCP submission

For the preceding example call `gromacs_hecbiosim_20k` with these typed arguments,
replacing the request key with the saved key and adding the same `inputs` when
custom input was uploaded:

```json
{"parameters":{"steps":50000,"threads":8},"version":"2026.4","idempotency_key":"saved-request-key"}
```

Do not include REST `model`/`workflow` fields in a named submit tool. Use
`md_run_status` with `{"run_id":"the-returned-run-id"}`. Preserve the returned
identifier exactly. Tool failures expose `isError` and a public error; accepted
asynchronous work can fail later, so always inspect terminal status and results.

## Retrieve and verify results

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/runs/$RUN_ID/artifacts" > artifacts.json
jq '.files[] | {path,size_bytes,sha256}' artifacts.json
```

MCP equivalent: `md_run_artifacts` with the same `run_id`. Select a result path
from that inventory and download its `download_url` without sending the scientific
bearer header to object storage. For example, after choosing an actual entry:

```sh
RESULT_PATH='data/actual-result-file'
URL=$(jq -er --arg p "$RESULT_PATH" '.files[]|select(.path==$p)|.download_url' artifacts.json)
EXPECTED_SHA=$(jq -er --arg p "$RESULT_PATH" '.files[]|select(.path==$p)|.sha256' artifacts.json)
EXPECTED_BYTES=$(jq -er --arg p "$RESULT_PATH" '.files[]|select(.path==$p)|.size_bytes' artifacts.json)
curl --fail-with-body --silent --show-error "$URL" --output result.bin
printf '%s  result.bin\n' "$EXPECTED_SHA" | sha256sum --check
test "$(wc -c < result.bin)" -eq "$EXPECTED_BYTES"
```

The placeholder path must be replaced by an actual inventory entry; model skills
describe meaningful result types. Inspect their scientific content as well as
integrity. Signed URLs expire: fetch the artifact inventory again to renew them.
Keep `artifacts.json` private because it temporarily contains credential-bearing
links. Standard S3 tooling may retrieve the same authorized owner-bucket results.

## Cancel, resume and errors

- REST cancellation is `POST /v1/runs/{run_id}/cancel`, or MCP `md_run_cancel`.
  Explicit cancellation does not authorize an automatic replacement execution.
- REST resume is `POST /v1/runs/{run_id}/resume` with, for example,
  `{"region":"eu-north2"}`; MCP is `md_run_resume` with that region and run ID.
  Use only a permitted region, compatible version/mode and verified checkpoint.
  Do not recreate the original request with a fresh execution deadline.
- `401`: refresh the approved token. `403`: permission/region/data binding problem;
  do not switch identities or regions to bypass it. `409`: inspect the documented
  conflict or pending delivery. `422`: correct the identified input/field.
  `429`: honor the retry guidance and existing queue. Transient `5xx`: inspect
  status/retryability and preserve the request key; never duplicate uncertain work.
- Report scientific goal failure, partial outputs and unsynced data loss honestly.
  Do not print signed links, tokens, private deployment metadata or raw scientific
  payloads in shared logs or chat. The skill grants no extra access or resources.
