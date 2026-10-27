# Scoped transfer and bounded Endpoint diagnostic

The provider Job dry-run currently fails for the reviewed immutable image with
`metadata.labels: label value length (...) exceeds maximum value (64)`.
A loopback capture of CLI 0.12.287 proves that its request has no metadata labels;
the failure appears in provider Job-to-Compute translation. The equivalent SDK
request is not an established workaround. A subsequent actual Endpoint SDK
dry-run also rejected the full digest with the same label-length error, both
with no labels and with short owner/task labels. No compute was created. Keep the digest; do not substitute a
mutable tag. This Endpoint fallback is currently blocked at provider validation; its exact
image and lifecycle have not passed. It is not a streaming or HTTP inference service.

`transfer.py` uses only Python's standard library. It downloads one owned tar via
a scoped HTTPS GET, verifies exact byte size and SHA-256, executes a fixed command,
and uploads all closed outputs plus logs/inventory via a scoped HTTPS PUT. No
cloud account key or Scientific AI import enters the container. Redirects are
rejected and capability URLs are omitted from errors. The science subprocess
group has a caller-selected finite timeout; a timeout exports partial logs with
exit code 124. Local scratch is distinct from the durable object prefix.

`run_bundle.py` accepts an uncompressed tar with `parameters.json`, the pinned
`tool_loc_convlstm.onnx` and a video selected by `parameters.video_file`. Include
the downloaded model's license. Video names and frame choices are ordinary user
inputs. Paths must remain inside the owned archive; links and duplicate paths
are rejected. The actual portable CLI performs model and video validation.

For an Endpoint, presign three exact objects in an existing authorized bucket:
input GET, output PUT and a fresh start-marker PUT. The marker PUT must sign
`If-None-Match: *` and `Content-Type: application/json`. The wrapper claims the
marker before science. HTTP 412 skips execution; an uncertain claim never starts
science. Success, failure and repeated starts enter idle sleep. This prevents
automatic model replay, but does **not** stop billing: the resource owner must
stop/delete the Endpoint at its predeclared deadline and after exporting results.
Preserve the marker until the exact Endpoint is deleted; deleting it early
would allow another execution.

Keep a private transfer JSON file (never commit its scoped URLs):

```json
{
  "input": {"url": "SCOPED_HTTPS_GET", "sha256": "TAR_SHA256", "size_bytes": 12345},
  "output": {"url": "SCOPED_HTTPS_PUT", "max_bytes": 268435456, "headers": {"Content-Type": "application/x-tar"}},
  "claim": {"url": "SCOPED_MARKER_PUT", "headers": {"If-None-Match": "*"}},
  "execution_timeout_s": 1800
}
```

The output budget and timeout are caller-selected; size them for the recording.
Use one run prefix and a new marker per intended execution. URL expiry must cover
image pull, inference and complete output export; do not grant broad bucket keys.

Prepare a request without contacting the provider:

```bash
python3 provider/prepare_endpoint.py \
  --image "$IMAGE" --project "$NEBIUS_PROJECT_ID" --name "$RUN_NAME" \
  --platform "$HOLOSCAN_PLATFORM" --preset "$HOLOSCAN_PRESET" \
  --transfer-config "$PRIVATE_TRANSFER_JSON" --output "$PRIVATE_REQUEST_JSON"
```

It requests no port or public IP. The provider must still support private egress
for registry and object storage. Validate with the official pinned `nebius==0.6.29`
Python SDK using `CreateEndpointRequest.from_json(...)`,
`SDK(config_reader=Config(profile=YOUR_PROFILE))`, and
`EndpointServiceClient(sdk).create(request, retries=1).wait()`. The generated
request has `dry_run=true`; retain the response. Only after a successful dry-run
and an owned cleanup plan should the owner submit the same reviewed request with
`dry_run=false`. Reconcile an uncertain create by its operation/name rather than
replaying it. This directory performs no provider mutation automatically.

Retain the returned Endpoint ID. Poll logs and the output object's full checksum;
verify the scientific artifacts before stopping. Then stop/delete **that ID**,
confirm termination/NotFound, and remove only its owned transient object prefix
when the required evidence is retained. Endpoint exit and a closed terminal are
not proof that compute stopped. The API has no Job-style timeout or retry-count
field, so a separate owner deadline is required.

Run the CPU transfer/guard checks with:

```bash
python3 provider/test_transfer.py
```
