---
name: runai-monai-spleen-ct
description: Segment spleen anatomy from a research CT NIfTI volume using managed Scientific AI REST or MCP, with explicit units, scientific versions and verified owner-bucket outputs.
license: Apache-2.0
metadata:
  status: bounded-research-qualification
---

# MONAI spleen CT on Scientific AI Run:ai

Read the sibling [scientific gateway](../runai-scientific-gateway/SKILL.md) and this
[worked portable example](references/portable-example.md). Use the caller's
configured `SCIENTIFIC_AI_URL`, individual token and existing bound bucket. This
is the managed `monai-spleen-ct` / `segment` workflow; the unprefixed `monai` skill
uses a different backend and artifact protocol. No native Run:ai administration,
operator helper, new account or new bucket is required.

Discover `GET /v1/models/monai-spleen-ct?workflow=segment` or call
`md_models(model="monai-spleen-ct",workflow="segment",detail=true)` first. Read its
exact parameters, versions, input/output contracts and current access restrictions.
Missing required metadata is a platform issue, not permission to guess paths or
artifact roles. The scientific selection key is `bundle-0.6.1`; its framework is
MONAI 1.6.1. Do not substitute the framework version for the bundle selection key.

## segment

For the seeded example, read its complete request from the public schema:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $SCIENTIFIC_AI_TOKEN" \
  "$SCIENTIFIC_AI_URL/v1/models/monai-spleen-ct?workflow=segment" > model.json
jq '.workflows.segment.example' model.json > request.json
```

The referenced archive must exist in your bound bucket. It contains the unchanged
MSD Task09 Spleen case 59 CT, renamed `image.nii.gz`, plus `README.txt` attribution
under CC-BY-SA-4.0. The example has a visible spleen; successful transfer alone
cannot establish correct anatomy. Use the shared client's submit/poll/download
steps. For your own volume instead, use the linked portable upload example.

A separately keyed precision variation is:

```sh
jq '.parameters.precision="bfloat16"' request.json > request-bfloat16.json
```

Use a new request directory/idempotency key for this changed body. BF16 can change
mask boundaries; do not call it numerically identical to the FP32 default.

## Input and controls

Provide **one finite, three-dimensional CT volume in Hounsfield units**, with a
nonsingular affine and verified spatial units. The contract accepts NIfTI1 or
NIfTI2, `.nii` or `.nii.gz`; current live examples exercise compressed NIfTI1.
DICOM, MRI, multichannel/4D input, training and arbitrary MONAI models are outside
this workflow. This upstream bundle is a research example, not for diagnosis;
technical success does not grant commercial hosting or establish clinical safety.

Archive a regular `image.nii.gz` as `input.tar.gz`, without a `data/` wrapper.
The server stages it at `data/inputs/image.nii.gz`. A renamed or nested member uses
its exact `image_path`, such as `data/inputs/ct-series/scan.nii.gz`. For `.nii`,
keep that suffix and set the matching path. Do not put credentials, scripts,
symlinks or serialized model weights in the archive. Input references contain only
`name`, owner-bucket `key`, exact compressed `sha256` and `size_bytes`; this API
does not take the legacy `input_manifest` or upload-handle protocol.

| Parameter | Default | Meaning |
|---|---|---|
| `precision` | `float32` | Explicit `float16` or `bfloat16` requests change arithmetic and may change masks. Never switch silently. |
| `sw_batch_size` | `4` | Number of 96³ patches per forward pass, not number of CT volumes; minimum 1. |
| `overlap` | `0.5` | Sliding-window overlap, from 0 inclusive to 1 exclusive; changing it changes inference. |
| `spatial_units` | `header` | Or verified `mm`, `meter`, `micron`; never guess acquisition units. |
| `image_path` | `data/inputs/image.nii.gz` | Exact staged NIfTI member path, confined to the owner's inputs. |

Keep scientific settings explicit when reproducibility matters. Default FP32 has
bounded research evidence on L40S, H100, H200, B200 and RTX PRO 6000. Additional H100
checks cover FP16, BF16, batch 1/overlap 0.25, explicit mm and a renamed input.
That does not qualify every precision on every GPU or every format/units variant.
GPU availability and permitted regions come from the caller's allocation and
live service; a public schema is not a capacity or production-readiness promise.

## Run, inspect and recover

The portable example covers upload, actual request construction, submission,
polling and checksum-verified download. For MCP use the discovered
`monai-spleen-ct_segment` tool with the same typed fields except REST `model` and
`workflow`, plus the saved `idempotency_key`. Poll with `md_run_status`, retrieve
`md_run_artifacts`, and cancel with `md_run_cancel`. Keep the returned public
`run_id`; a disconnected client must not create a second logical request.

Choose only authorized placement. Omit selectors for eligible platform placement,
or request an allowed region/GPU explicitly. A denied region is not permission to
move data elsewhere. The bucket binding and compute region are separate: requesting
a region does not relocate the bucket or authorize a different data source.

Expected results are `data/outputs/segment/segmentation.nii.gz` and `result.json`.
The uint8 mask uses **0 background, 1 spleen** and preserves input shape, affine,
qform/sform and their codes, and spatial/time units. Read `result.json` for input
hash, bundle/framework versions, exact requested controls, geometry, foreground
voxel count/volume in mm³ and native timings. No probability map is returned.
Native inference time includes windowing/transfers/host stitching; Pod Ready is
not an absolute model-ready timestamp. Do not infer GPU rankings from one run.

A readable mask is not scientific validation. Inspect anatomy and physical
geometry; an empty mask may be a legitimate prediction, while it fails an annotated
positive-reference test. The observed reference Dice is not a guarantee for other
images. Keep precision-dependent differences and uncertainty visible.

CPU input validation precedes GPU execution. Read structured terminal errors and
correct invalid NIfTI, units or paths before retrying. One volume is one request;
multiple volumes require independent requests. The current native worker budget
is one hour; the two-week operation expiry does not extend that worker budget.
Temporary private scratch is deleted after at most 300 seconds of final-upload
retries, including upload failure; unsynced loss must be reported. An interrupted
unfinished volume recomputes: pretrained weights are not an execution checkpoint.
Cross-region MONAI recovery remains a separate qualification gate.
