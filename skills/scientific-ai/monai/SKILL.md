---
name: monai
description: Segment a spleen from a 3D CT NIfTI volume with the qualified MONAI bundle, using Scientific AI artifact Jobs or the portable Docker/Serverless recipe.
---

# MONAI CT segmentation

Use this for the `monai-spleen-ct` App's first pretrained bundle. Other MONAI
models, training, annotation servers, DICOM SEG and clinical deployment require
separate evidence; do not infer them from a successful spleen workflow.

Discover the caller-authorized App and fetch its live contract. Prefer the
typed `submit_monai_spleen_ct` tool when published. Do not invent its readiness
from this skill. Follow the shared scientific-gateway and scientific-batch
artifact upload/finalize and durable-operation conventions.

The input manifest contains one entry named `image`, semantic type
`ct-nifti-volume/v1`, media type `application/x-nifti`, with compression `gzip`
for `.nii.gz` or `none` for `.nii`. Use the user's immutable artifact reference,
not base64, filesystem paths, arbitrary external URLs, or a new model download.
The volume is one 3D CT in Hounsfield units. Ensure geometry and spatial units
are meaningful; ask for the actual units if the header omits them.

Submit operation `segment` with an appropriate service class and a stable
idempotency key. Parameters: `precision` (float32 default), `sw_batch_size` (4),
`overlap` (0.5), and `spatial_units` (`header`). Use the discovered schema for
current choices. Never silently change precision or spacing to make a request
fit. A lower patch batch can reduce memory without dropping input voxels.

Retain the operation ID and use `get_operation`, `get_operation_result`, and
`cancel_operation` on that same operation. Do not resubmit while polling. Return
downloadable `segmentation.nii.gz` and `result.json` artifacts. Summarize label
0 background / 1 spleen, original geometry preservation, model revision and
whether foreground was found. A mask is a model prediction; an empty spleen
label is not by itself a transport failure. Report actionable terminal errors.

The upstream bundle is a research example, not intended for diagnosis. Its
published validation Dice and this recipe's regression case do not establish
accuracy for a user's image. Do not interpret segmentation as a medical diagnosis.

For an on-premises Docker run or a provider-managed Nebius Serverless Job, use
[`templates/job-monai-segmentation`](https://github.com/rene-tech/serverless-ai-cookbook/tree/main/templates/job-monai-segmentation).
That portable recipe builds from public pinned sources and needs no Scientific
AI token. Use its explicit CPU mode when requested; do not claim GPU execution
from a CPU result. Keep image publication, GPU test results, App REST/MCP tests,
and provider Serverless tests distinct.
