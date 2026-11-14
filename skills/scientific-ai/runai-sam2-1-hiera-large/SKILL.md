---
name: runai-sam2-1-hiera-large
description: Segment images or track prompted objects in short videos with managed SAM2.1 Hiera Large, using owner-bucket media archives and per-pixel object masks. Use for segment-track-media; not diagnosis, arbitrary Python or an interactive shared session.
---

SYSTEM evaluation candidate. The three existing image/video modes have native scientific screens on H100, L40S, H200 and B200, plus public REST/MCP and concurrent-request tests. Additional image-prediction arrays/refinement have native H100 numeric references. Explicit automatic-generator controls and all three native mask formats have bounded scientific screens on H100, L40S, H200 and B200; use new options only when the live authorized schema advertises them and matching public qualification is complete. RTX and complete feature/security/commercial production qualification remain open. This skill grants no access, clinical approval or additional licences.

Use the shared [portable client recipe](../runai-scientific-gateway/references/client.md) for secure environment credentials, owner-bucket upload, idempotency, polling, cancellation and result SHA256 verification. No LibreChat, operator paths or Run:ai management credentials are needed. Discover your authorized live contract first:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/sam2-1-hiera-large?workflow=segment-track-media" > model.json
```

Check supported versions and exact input/output contracts. The scientific version is `sam2.1-hiera-large-665f8e2a`. Keep this selected version and scientific settings with your results. Image/deployment identifiers are private implementation details.

## Additional native image modes

Use the following only when your authorized live schema advertises them. Standalone embedding/mask-only screens cover H100, L40S, H200 and B200. True two-image batch prediction screens cover H100, L40S, H200 and B200; new-feature public REST/MCP qualification remains required before customer release. These are the same `segment-track-media` workflow, not new management APIs.

- `embedding-image`: archive settings contain mode, media_path and image MIME only. No points, box or prediction_options. The result contains manifest.json and predictions/image-embedding.npy, float32[1,256,64,64]; it does not invent segmentation prompts or a mask.
- `refine-image`: supply only media and prediction_options.mask_inputs, with1–8 unique object IDs and archive-relative finite float32 NPY[1,256,256] priors. Points, box, object_id, prompt_frame and max_masks are rejected. Native image decoding receives the real mask prior without fake points/boxes.
- `batch-image`: settings require batch_operation and images. Each image has its own media_path/media_type. For predict, each image has1–8 unique object_ids and real prompts: point_coords[objects,points,2] with point_labels[objects,points], optional boxes[objects,4], and optional mask_inputs paths[objects]. Points within each image must be rectangular; different images can have different object/point counts. Native mask-only multi-object batches are unsupported; use refine-image instead. Batch-level single-image fields are rejected. For embedding batches, omit all prompts, object IDs and prediction_options.

Omitted prediction_options.normalize_coords preserves source-pixel coordinates. Explicit false selects the native normalized[0,1] convention for prompted images or image batches. There is no automatic guess about coordinate units.

The [two-image example](batch-example-input.tar.gz) contains only synthetic media and settings, with a matching [request](batch-example-request.json). Upload it into your bound bucket using the shared client recipe, then preserve a fresh idempotency key, submit once, poll the same returned ID and verify result.zip size/SHA. It selects EU-North1/H100 and32GiB temporary scratch. Run the portable checker only after artifact verification:

```sh
python check_batch.py result.zip --input batch-example-input.tar.gz
```

The checker requires NumPy and Pillow and checks this bundled synthetic example only. Batch results preserve image order and object IDs under batch/0001, batch/0002, etc. Every object NPZ contains float32 masks, scores and low_resolution_logits; include_embedding adds one float32 NPY[1,256,64,64] per image. Native binary masks contain0/1; return_logits preserves full native mask logits. The preview picks the highest-scoring candidate per object, retaining complete scientific arrays separately.

The native encoder processes the image batch together. Source images, normalized tensors, outputs and native eager automatic-mask lists all consume memory; input/schema maxima are not throughput or universal memory-fit guarantees. No output is silently clipped to force a fit. Queue, native weights-loaded time and first completed result are distinct measurements; this managed job is not a continuously ready HTTP pod.

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

Replace key/hash/size with your real upload. Submit once to `POST /v1/runs`, preserving the request body and `Idempotency-Key` before POST. Omitted API parameters preserve file settings; explicit top-level parameters override the file. For prediction_options and automatic_options, only explicitly supplied nested keys override the file: omitted keys remain unchanged, explicit false is preserved, mask_inputs=[] clears prior masks, and null is rejected. A deliberate changed request needs a new saved key. An uncertain acknowledgement must be reconciled using the original key/body, never a blind fresh submission.

Typed MCP discovery: `md_models` with `{"model":"sam2-1-hiera-large","workflow":"segment-track-media","detail":true}`. Call `sam2-1-hiera-large_segment_track_media` with `version`, `inputs`, `parameters`, saved `idempotency_key`, and optional authorized `region`/`gpu`; omit REST `model/workflow`. Poll `md_run_status`, fetch `md_run_artifacts` and cancel through `md_run_cancel`. Keep returned run IDs after disconnects. The live schema determines availability and access.

When the live schema advertises `prediction_options`, prompted-image can also return native prediction arrays:

```json
{"prediction_options":{"multimask_output":true,"return_logits":true,"include_embedding":true}}
```

Put this object in REST/MCP `parameters` or merge it into archive-root `settings.json`. `multimask_output` preserves all three native candidates per prompted object; `return_logits` selects full-resolution float32 logits instead of native float32 binary0/1 masks. `include_embedding` adds a float32 NPY of shape `[1,256,64,64]`. The selected label preview remains the highest native-scoring candidate. Scores are model quality estimates, not calibrated probabilities.

The ZIP adds `predictions/object-{object_id}.npz`, containing `masks[candidates,height,width]`, `scores[candidates]` and `low_resolution_logits[candidates,256,256]`. The optional embedding is `predictions/image-embedding.npy`. All arrays remain in your owner artifacts. Verify the downloaded archive before opening NumPy files, and always use `allow_pickle=False`.

For prompted-image refinement, retain the original point/box settings and select one prior low-resolution candidate and retain its leading dimension when saving `float32[1,256,256]` as an uncompressed `.npy` file. This optional local client snippet needs NumPy:

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

## Explicit automatic-generator controls

When `automatic_options` appears in the authorized live schema, the same
`segment-track-media` workflow exposes the pinned native automatic generator.
The [automatic example archive](automatic-example-input.tar.gz) contains the
executed 320×240 three-object control, and its
[request](automatic-example-request.json) selects EU-North1/H100 with a 32GiB
private job volume. This is a small diagnostic example, not a speed or accuracy
benchmark for other images. Its archive SHA256 is
`66d09edbb0daa02df509ad52be58ca35d9b61978ce77835adbf7fbdd1e1860f4`
and size is 6,642 bytes.

```sh
aws s3 cp automatic-example-input.tar.gz \
  "s3://$SCIENTIFIC_DATA_BUCKET/examples/runai-sam2-v6/automatic-image/input.tar.gz" \
  --endpoint-url "$SCIENTIFIC_DATA_ENDPOINT" --region "$SCIENTIFIC_DATA_REGION"
cp automatic-example-request.json request.json
```

Use the shared portable client to save an idempotency key, submit once, poll,
verify artifact hashes and download the result. The same typed MCP tool above
accepts this request's `parameters`, version and input descriptor. The archive
settings contain all 16 native controls:

```json
{"mode":"automatic-image","media_path":"media.png","media_type":"image/png","max_masks":32,"automatic_options":{"points_per_side":8,"points_per_batch":4,"pred_iou_thresh":0,"stability_score_thresh":0,"stability_score_offset":1,"mask_threshold":0.5,"box_nms_thresh":0.5,"crop_n_layers":1,"crop_nms_thresh":0.5,"crop_overlap_ratio":0.25,"crop_n_points_downscale_factor":2,"point_grids":null,"min_mask_region_area":4,"output_mode":"binary_mask","use_m2m":true,"multimask_output":true}}
```

`point_grids` is an alternative list of normalized `[x,y]` sampling grids,
one for each crop layer. Set `points_per_side:null` when providing those grids;
otherwise use positive `points_per_side` with omitted/null grids. Sampling and
output budgets are checked before admission. More points/crops can increase
compute, output size and native eager-mask memory substantially; the current
measured explicit-controls envelope is this 240×320, 128-point, at most
384-candidate case. A configured output budget is not a promise that every
larger configuration fits GPU/host memory.

Omitted controls preserve the existing wrapper defaults. To apply small-region
postprocessing, explicitly request positive `min_mask_region_area`; inspect
`native_postprocessing_executed` in the returned manifest. An explicit request
must fail if its matched native component cannot execute. Omitted control
behavior is retained for reproducibility and is stated in the manifest.

The result retains every native annotation and overlapping mask in
`automatic/annotations.json`. `max_masks` limits the nonoverlapping uint16
label preview, not that complete scientific result. Each annotation preserves
area, box, native quality/stability scores, sampled point, crop and segmentation:

- `binary_mask`: segmentation references `automatic/mask-000001.npy` and so on;
  arrays are boolean `[height,width]`, opened with `allow_pickle=False`.
- `uncompressed_rle`: segmentation is JSON `{ "size":[height,width], "counts":[...] }`.
- `coco_rle`: segmentation has the same size and native compressed text counts.
  Counts are JSON strings, not Python byte values.

For another format, change only `automatic_options.output_mode` in the archive
or typed parameters, update the uploaded archive descriptor if its bytes changed,
and use a fresh saved idempotency key. Decode RLE with standard `pycocotools`;
the optional local checker needs NumPy and Pillow, and additionally pycocotools
for either RLE mode:

```sh
python check_automatic.py result.zip --input automatic-example-input.tar.gz
```

This checks all mask areas/dimensions and independently matches each known
colored object at IoU≥0.7. It does not certify segmentation accuracy on unseen
scientific or clinical images. With modified typed parameters, prepare a matching
settings archive for this exact-fixture checker or inspect the artifacts directly.

Results appear in your bound bucket. Verify artifact sizes/SHA256 before opening `data/outputs/segment-track/result.zip` and `science.json`. The ZIP contains `manifest.json`, label `mask.png` and `overlay.png` for images; videos contain all numbered `masks/000001.png` frames plus `overlay.mp4`. Background is0, positive labels are object identities, not biological classes or calibrated probabilities. Inspect geometry, prompt-object correspondence and tracking consistency. Do not equate a nonempty mask with accuracy on unseen scientific images or claim clinical validation.

Execution is a private asynchronous job with scalezero when idle. Short interrupted image/clip work recomputes as a unit; this workflow does not promise exact in-flight video-state recovery. Inputs, frames, scratch and results remain in owner-controlled storage; final-upload retries are bounded300seconds, then job scratch is deleted. A bucket outage may lose the unsynced tail. Inspect terminal errors and partial results rather than resubmitting deterministic failures.

Current capability gaps are not waived: public release of the new standalone/batch modes, larger automatic-generator memory envelopes, iterative per-frame edits/masks, reverse/bounded propagation and native video-state persistence remain open; training scope remains undecided and is not advertised by this workflow. Mask-logit refinement, candidate arrays and embeddings require the corresponding live schema and release qualification. Do not guess unsupported settings. No customer-ready claim is permitted until the promised scope and executed acceptance agree.

Core code and checkpoint are Apache2.0 under [the pinned upstream licence](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/LICENSE); exact full-runtime commercial/security clearance is a separate platform gate.
