---
name: runai-cellpose-cpsam-v2
description: Segment microscopy cells or nuclei with managed Cellpose 4.2.1 CPSAM v2, using caller-owned image archives, explicit geometry and instance-label outputs. Use for the segment-cells workflow, not training, tracking or diagnosis.
license: Apache-2.0
---

Bounded research qualification; commercial clearance and full production acceptance remain unresolved. Follow the live access restrictions. This skill grants no access or licences.

Use the shared [portable client](../runai-scientific-gateway/references/client.md) for credentials, owner-bucket uploads, idempotency, polling, artifact integrity and cancellation. Set `SCIENTIFIC_AI_URL` and `SCIENTIFIC_AI_TOKEN` through the approved environment; use `SCIENTIFIC_DATA_BUCKET`, `SCIENTIFIC_DATA_ENDPOINT`, `SCIENTIFIC_DATA_REGION` and scoped AWS credentials for your existing bound store. No operator tools or native paths are needed.

## segment-cells

Discover the live contract before preparing data:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/cellpose-cpsam-v2?workflow=segment-cells" > model.json
jq '.workflows["segment-cells"].example' model.json > request.json
```

Check `default_version`, `versions`, `settings_input_schema` and the workflow input/output contracts. A discovered example works only after its referenced archive is available in **your own** bound bucket; copy an authorized example or supply your own input. The versioned example names an authorized example archive in that same bucket. If the object is absent, use your own archive below or ask for the approved example-data setup; do not guess shared object keys. Preserve the selected version and recorded scientific settings. Use the shared client's submit/poll/download steps with this request. The seeded example is one BBBC039 field, using BF16 and requesting TIFF/PNG labels, saved flows and an overlay. Its masks should contain individual nonzero cell/nucleus instances; verify label geometry and inspect the overlay. It is a reference check, not an accuracy promise for new microscopy.

Prepare `input.tar.gz` with archive-root `settings.json` and original image files; no `data/` wrapper. PNG, JPEG and single-file TIFF/OME-TIFF use the declared media type. TIFF compression requires a supported installed codec; external OME companion files are rejected. Preserve uint16 intensities and explicit axes. A 2D example requesting all five result types is:

```json
{
  "images": [{"id": "field-1", "path": "field.tiff", "media_type": "image/tiff", "axes": "YX"}],
  "eval": {"diameter": null, "batch_size": 8, "tile_overlap": 0.1, "augment": false},
  "use_bfloat16": true,
  "save_flows": true,
  "legacy_png": true,
  "save_overlay": true,
  "research_only": true
}
```

Upload using the shared client procedure and insert the exact owner object key, SHA256 and compressed byte count into `inputs`. Submit REST `POST /v1/runs` with this body shape and your saved idempotency key:

```json
{"model":"cellpose-cpsam-v2","workflow":"segment-cells","version":"4.2.1","inputs":[{"name":"input.tar.gz","key":"YOUR_OWN_INPUT_KEY","sha256":"YOUR_ARCHIVE_SHA256","size_bytes":12345}],"parameters":{}}
```

Replace the illustrative key, hash and size with real uploaded values. Keep settings in the file when no API override is intended. Omitted parameters preserve file settings; explicit API booleans override them. An API `eval` object replaces the file's top-level `eval` object; per-image `eval` fields then override those global controls. `diameter:null` preserves native scale, with no automatic size estimation. `batch_size` counts native 256×256 tiles, not requests or images.

Typed MCP discovery is `md_models` with `{"model":"cellpose-cpsam-v2","workflow":"segment-cells","detail":true}`. Select its model entry. Call `cellpose-cpsam-v2_segment_cells` with `version`, `inputs`, `parameters` and saved `idempotency_key`; omit REST `model/workflow`. Poll `md_run_status`, retrieve `md_run_artifacts`, cancel with `md_run_cancel`. Preserve run IDs after disconnect and reuse the same key/body for uncertain submissions.

A separately keyed variation using the same owner input requests FP32 explicitly:

```sh
jq '.parameters.use_bfloat16=false' request.json > request-fp32.json
```

Use a new request directory and idempotency key for that changed request; do not
reuse the original key. This varies arithmetic, not image contents or thresholds.

## Interpret science

Each `data/outputs/image-NNNNNN/` contains `science.json` and requested outputs: uint32 `labels.tiff`, 2D uint16-compatible `labels.png`, `overlay.png`/`overlay.tiff`, and `flows.npz`. Inspect the returned inventory; verify downloaded sizes/SHA256 using the shared client. Load NPZ with `allow_pickle=False`. Label 0 is background; positive IDs identify instances, not biological classes. PNG is optional and limited to 2D; use TIFF for analysis and volumes. `compute_masks:false` requires saved flows and produces no label mask.

Check image ID/input hash, canonical YX/ZYX shape, actual dtype/controls, label scope and object sizes. Physical area/volume requires declared spacing/units. Independent 2D planes have plane-local IDs; stitched stacks and true 3D have volume labels. Flow component order follows reported metadata; cellprob is not a calibrated probability and styles are native zero compatibility vectors. Overlays aid inspection. Compare annotated images using instance AP50/AP75 and foreground Dice; valid files or nonzero counts alone do not establish segmentation quality.

Completed images can resume from verified owner checkpoints; an interrupted image/volume recomputes. No in-flight neural checkpoint or cell tracking is provided. Report partial results and unsynced scratch loss; final-upload retries are bounded to 300 seconds before scratch deletion. Queue/cold start is separate from inference time.

## Evidence boundaries

Executed coverage includes one annotated BBBC039 2D field with all five outputs across five GPU classes/four regions, REST/typed MCP, four overlapping public requests, and separate H100 FP32, XY, CXY/channel0 and tile batch 4/overlap0.2/augmentation cases. These are bounded screenings, not broad accuracy, optimization or clinical claims.

True 3D, stitching, multiple-image/time-frame campaigns, physical calibration and other normalization/threshold/format combinations remain scientifically unqualified in managed GPU execution. Some have parser/CPU checks only. Discover their complete schemas; do not infer qualification from advertised support. Training, GUI, restoration and export are outside this inference workflow.

Sources: [Cellpose 4.2.1](https://github.com/MouseLand/cellpose/tree/v4.2.1), [CPSAM checkpoint](https://huggingface.co/mouseland/cellpose-sam), [BBBC039 CC0 reference](https://bbbc.broadinstitute.org/BBBC039). The exact code and checkpoint model card state BSD-3-Clause; the separate annotated training dataset has noncommercial terms. These grants do not replace exact-runtime commercial review; do not infer a noncommercial checkpoint ban solely from the training-data warning.
