---
name: runai-sam2-1-hiera-large
description: Segment images or track prompted objects in short videos with managed SAM2.1 Hiera Large, using owner-bucket media archives and per-pixel object masks. Use for segment-track-media; not diagnosis, arbitrary Python or an interactive shared session.
---

SYSTEM evaluation candidate. The three existing image/video modes have native scientific screens on H100, L40S, H200 and B200, plus public REST/MCP and concurrent-request tests. Additional image-prediction arrays/refinement have native H100 numeric references; use them only when the live authorized schema advertises prediction_options. RTX and complete feature/security/commercial production qualification remain open. This skill grants no access, clinical approval or additional licences.

Use the shared [portable client recipe](../runai-scientific-gateway/references/client.md) for secure environment credentials, owner-bucket upload, idempotency, polling, cancellation and result SHA256 verification. No LibreChat, operator paths or Run:ai management credentials are needed. Discover your authorized live contract first:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/sam2-1-hiera-large?workflow=segment-track-media" > model.json
```

Check supported versions and exact input/output contracts. The scientific version is `sam2.1-hiera-large-665f8e2a`. Keep this selected version and scientific settings with your results. Image/deployment identifiers are private implementation details.

## segment-track-media

The bundled [synthetic example archive](example-input.tar.gz) contains only `settings.json` and a320×240PNG of three colored disks. Its prompted point `(95,86)` selects the cyan disk. The H100 known-reference check produced foreground IoU0.99375; this is a synthetic control, not an accuracy claim for new images. The [example request](example-request.json) names that exact archive and an owner-relative example key; upload it into your existing bound bucket before using the request. No new bucket, account or credential is needed.

From an installed copy of this skill, use ordinary S3 tooling and the portable client's submit/poll/download steps:

```sh
aws s3 cp example-input.tar.gz \
  "s3://$SCIENTIFIC_DATA_BUCKET/examples/runai-sam2-v1/prompted-image/input.tar.gz" \
  --endpoint-url "$SCIENTIFIC_DATA_ENDPOINT" --region "$SCIENTIFIC_DATA_REGION"
cp example-request.json request.json
```

The archive SHA256 is `19503db6126b811c167a0c6856606a145ee30cf6ce1ac5b9d558297bb898e618` and compressed size6569bytes. The request explicitly selects EU-North1/H100 while automatic cost placement is unqualified. Preserve a fresh idempotency key and request file **before** the single submission. Poll the returned ID, fetch the artifact inventory, then download `data/outputs/segment-track/result.zip` with no scientific bearer header and verify its size/SHA256. Do not send the scientific token to GitHub or object-storage download URLs. Reconnect to the same run after a client timeout.

Create `input.tar.gz` with archive-root `settings.json` and its relative media file. Do not add a `data/` directory. PNG/JPEG images and MP4 videos are the accepted media. Example settings for a positive object point:

```json
{"mode":"prompted-image","media_path":"image.png","media_type":"image/png","points":[{"x":160,"y":120,"label":1,"object_id":1}]}
```

Coordinates refer to source pixels, not normalized fractions. Label1 selects foreground and0 marks background. Points sharing an `object_id` describe one object; use different positive IDs for multiple objects. An optional box is `[x0,y0,x1,y1]`, associated with `object_id` (default1). Supply points or a box for prompted modes. Choose coordinates that actually identify your object; this example's centre point is meaningful only for a matching image.

For whole-image automatic segmentation, use `mode:"automatic-image"`, omit points/box and optionally set `max_masks` (1–128, default32). For video use `mode:"prompted-video"`, `media_path:"clip.mp4"`, `media_type:"video/mp4"` and optional zero-based `prompt_frame` (default0). Prompts are added on that frame and tracked forward; earlier frames are background in this bounded workflow. This is not independent per-frame image segmentation.

Limits:64MiB encoded media,2,073,600 pixels/frame,320 decoded video frames,64 points,8 prompted objects and object IDs1–65535. Invalid media, dimensions, mode/format or prompts must fail before GPU admission. Negative/empty predictions can still be legitimate completed scientific results.

```sh
tar -czf input.tar.gz -C prepared-inputs settings.json image.png
```

Follow the shared client's owner-bucket upload procedure. Use the actual uploaded object key, archive SHA256 and compressed byte count. Never put bucket credentials in settings or request JSON. Submission body shape:

```json
{"model":"sam2-1-hiera-large","workflow":"segment-track-media","version":"sam2.1-hiera-large-665f8e2a","region":"eu-north1","gpu":"h100","inputs":[{"name":"input.tar.gz","key":"YOUR_OWNER_INPUT_KEY","sha256":"YOUR_ARCHIVE_SHA256","size_bytes":12345}],"parameters":{}}
```

Replace key/hash/size with your real upload. Submit once to `POST /v1/runs`, preserving the request body and `Idempotency-Key` before POST. Omitted API parameters preserve file settings; explicit top-level parameters override the file. For prediction_options, only explicitly supplied nested keys override the file: omitted keys remain unchanged, explicit false is preserved, mask_inputs=[] clears prior masks, and null is rejected. A deliberate changed request needs a new saved key. An uncertain acknowledgement must be reconciled using the original key/body, never a blind fresh submission.

Typed MCP discovery: `md_models` with `{"model":"sam2-1-hiera-large","workflow":"segment-track-media","detail":true}`. Call `sam2-1-hiera-large_segment_track_media` with `version`, `inputs`, `parameters`, saved `idempotency_key`, and optional authorized `region`/`gpu`; omit REST `model/workflow`. Poll `md_run_status`, fetch `md_run_artifacts` and cancel through `md_run_cancel`. Keep returned run IDs after disconnects. The live schema determines availability and access.

When the live schema advertises `prediction_options`, prompted-image can also return native prediction arrays:

```json
{"prediction_options":{"multimask_output":true,"return_logits":true,"include_embedding":true}}
```

Put this object in REST/MCP `parameters` or merge it into archive-root `settings.json`. `multimask_output` preserves all three native candidates per prompted object; `return_logits` selects full-resolution float32 logits instead of native float32 binary0/1 masks. `include_embedding` adds a float32 NPY of shape `[1,256,64,64]`. The selected label preview remains the highest native-scoring candidate. Scores are model quality estimates, not calibrated probabilities.

The ZIP adds `predictions/object-{object_id}.npz`, containing `masks[candidates,height,width]`, `scores[candidates]` and `low_resolution_logits[candidates,256,256]`. The optional embedding is `predictions/image-embedding.npy`. All arrays remain in your owner artifacts. Verify the downloaded archive before opening NumPy files, and always use `allow_pickle=False`.

For refinement, select one prior low-resolution candidate and retain its leading dimension when saving `float32[1,256,256]` as an uncompressed `.npy` file. This optional local client snippet needs NumPy:

Reuse the original unpacked media and settings. For the bundled example:

```sh
mkdir -p prepared-inputs
tar -xzf example-input.tar.gz -C prepared-inputs
```

```python
import io, zipfile
import numpy as np
with zipfile.ZipFile("result.zip") as result:
    with np.load(io.BytesIO(result.read("predictions/object-1.npz")), allow_pickle=False) as arrays:
        chosen = int(np.argmax(arrays["scores"]))
        prior = arrays["low_resolution_logits"][chosen:chosen + 1].copy()
assert prior.shape == (1, 256, 256) and prior.dtype == np.float32 and np.isfinite(prior).all()
np.save("prepared-inputs/prior-mask.npy", prior, allow_pickle=False)
```

Include `prior-mask.npy` beside your media and settings in the next owner archive. Add `"mask_inputs":[{"object_id":1,"path":"prior-mask.npy"}]` inside `prediction_options` and retain valid point/box prompts for that object; add positive/negative corrections as scientifically appropriate. Paths are exact archive-relative member names, not URLs or host paths. Each NPY is bounded266,240bytes, finite float32, shape `[1,256,256]`, without object arrays or pickle. At most eight distinct objects are supported by this managed workflow; each prior must name one already-prompted object, without duplicates.

For the bundled example, package all three required files, then upload the new
archive to a fresh owner key and update the request's input key, SHA256 and byte
count before submitting once with a new saved idempotency key:

```sh
tar -czf refined-input.tar.gz -C prepared-inputs settings.json media.png prior-mask.npy
```

Results appear in your bound bucket. Verify artifact sizes/SHA256 before opening `data/outputs/segment-track/result.zip` and `science.json`. The ZIP contains `manifest.json`, label `mask.png` and `overlay.png` for images; videos contain all numbered `masks/000001.png` frames plus `overlay.mp4`. Background is0, positive labels are object identities, not biological classes or calibrated probabilities. Inspect geometry, prompt-object correspondence and tracking consistency. Do not equate a nonempty mask with accuracy on unseen scientific images or claim clinical validation.

Execution is a private asynchronous job with scalezero when idle. Short interrupted image/clip work recomputes as a unit; this workflow does not promise exact in-flight video-state recovery. Inputs, frames, scratch and results remain in owner-controlled storage; final-upload retries are bounded300seconds, then job scratch is deleted. A bucket outage may lose the unsynced tail. Inspect terminal errors and partial results rather than resubmitting deterministic failures.

Current capability gaps are not waived: batching, the full automatic-generator control surface, iterative per-frame edits/masks, reverse/bounded propagation, native video-state persistence and training are not yet qualified by this workflow. Mask-logit refinement, candidate arrays and embeddings require the corresponding live schema and release qualification. Do not guess unsupported settings. No customer-ready claim is permitted until the promised scope and executed acceptance agree.

Core code and checkpoint are Apache2.0 under [the pinned upstream licence](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/LICENSE); exact full-runtime commercial/security clearance is a separate platform gate.
