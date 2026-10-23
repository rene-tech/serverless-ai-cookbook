---
name: scientific-gateway
description: Use Nebius Scientific AI Apps through their typed MCP tools. Apply when discovering models, choosing an App, preparing model inputs, submitting or resuming work, polling an operation or scientific batch, uploading inputs, downloading results, or explaining an MCP error.
license: Apache-2.0
---

# Scientific AI Apps

Use the `scientific-ai-apps` MCP server (or its configured name in another
client). `bionemo-models` is a retired LibreChat alias, not the product name.
Authentication is supplied by the configured client, not a skill file;
never ask for, print, copy, or place an API key in tool arguments. The caller's
key determines the visible Apps and owns the resulting operations and artifacts.

## Discover before invoking

1. For discovery, call compact `workbench_list_apps` once with `{}`. It returns
   the complete authorized catalog without filters. For a domain question select
   the relevant returned group; do not enumerate domains through keyword retries.
   `workbench_search_apps` is a separate literal phrase search: zero matches do
   not mean zero permissions. For a named App, read its schema directly. Portable
   clients without the workbench helper use hosted `list_models` and `list_scientific_models`.
   Compare their `tool_catalog_revision`; refresh tools when it changes.
2. Call `get_model_schema` with the selected public `model_id` and protocol.
3. Use the returned `contracts[].tool_name`, exact `input_schema`, examples,
   source references and active-runtime identity. Independent Apps using the
   same underlying model remain separate Apps.
4. Prefer that named typed tool. Do not infer fields from a model's name, an
   NVIDIA REST example, or an old skill. Re-discover after an authorization,
   missing-tool, or stale-schema error.

Named serving tools accept the model fields directly plus optional
`idempotency_key` and `wait_seconds`. Scientific MD/scVI/MPI tools accept the run
object in `request` plus `idempotency_key`; staged tools such as Protenix,
LeRobot and Complexa accept those run fields directly plus `idempotency_key`.
Select the exact shape from the discovered schema before submission; never retry
a rejected call with a different wrapper. Do not wrap native model fields in
`request` or `payload`. Do not send `model` to a named OpenAI-chat tool: the App already
selects it. Use the exact discovered schema rather than another endpoint's shape.

If this skill disagrees with the tool's current schema, the tool schema wins.
Do not silently omit unsupported scientific inputs or switch models. Explain the
specific incompatibility and ask the user to choose a supported workflow.

## Submit once and resume

- Create one stable idempotency key of 8–200 characters per logical submission.
  Reuse it only with the identical payload after an uncertain transport failure.
  A corrected or deliberately new request gets a new key.
- Set serving `wait_seconds` to `0` unless a short bounded wait materially helps.
  Submission returns a durable operation/status record, not the final prediction.
- Save and report the exact returned operation ID. Copy it from the tool result or verified receipt
  into variables, titles, links and reports; never retype or reconstruct it.
  Do not convert it to a UUID.
  Choose the lifecycle tools by that ID and the live submission-tool description,
  not by whether the App is called "serving" or "scientific":
  - Every job uses the native Serverless `op-...` ID across API, MCP, workbench
    and operator console. Never translate it to a UUID or look for an alias.
    Prefer `workbench_get_operation` for bounded waiting and
    `workbench_get_operation_result` for verified result recovery; hosted
    `get_operation` and `get_operation_result` use the same ID.
    Live audio sessions use their actual native `ses-...` session ID;
    synchronous predictions retain their native `sync-...` receipt ID.
- Scientific submissions return native operation state. Poll
  `get_operation`; do not request the retired archive event stream.
  Wait for `operation.result_available`, then call `get_operation_result` and retrieve
  the returned artifacts. Execution success alone may precede publication.
- Treat `queued`, `activating`, and `running` as nonterminal, not proof of
  advancing execution or a specific capacity problem. Do not resubmit or
  cancel because a chat/tool timeout elapsed. Terminal states are `succeeded`,
  `failed`, `cancelled`, `preempted`, and `expired`.
- Download and verify outputs before an advertised `acknowledge_operation`;
  acknowledgement purges the operation's ordinary request/result payload,
  not its separately published scientific artifacts or checkpoints.

## Scientific artifacts

For a non-LibreChat client, read [portable client setup](references/portable-client.md).
LibreChat-specific workspace and executor tools are optional client capabilities,
not part of the hosted model MCP. Keep the same model contracts in either client.

The workbench has an authenticated Workspace upload/download panel and verified
file helpers. Ordinary chat attachments still are not automatically gateway
artifacts. The connected `visualize_structure` tool renders real coordinates
from completed native inline or bounded JSON-artifact results; it does not
resolve arbitrary scientific-batch artifact collections. Signed handles and
bearer tokens stay outside model context. Never promise an unsupported bridge.

Chat attachments and local paths are not gateway artifacts. For every input:

1. Read the actual caller-owned bytes outside the language-model context.
2. Compute exact SHA-256, byte count, media type and compression.
3. Let the installed trusted file helper call `begin_scientific_artifact_upload`,
   transfer through its handle/HTTPS content path and call
   `finalize_scientific_artifact_upload`. Require `state: finalized` and use its
   `artifact` object. Raw byte tools are not agent-visible.
4. Build a canonical manifest from the returned immutable artifact references;
   upload and finalize that manifest too.
5. Submit the named scientific tool with the finalized manifest reference.

Never invent or reuse another user's artifact ID. Keep base64 values and
structure/media files out of chat. Use returned upload/download handles or
the HTTPS artifact path through the trusted file helper. Check handle expiry.

For a native artifact input use `/opt/bionemo/upload-artifact.py`; this uploads
one exact local file but does not create a scientific input manifest or run a
model. For scientific batch use the installed existing
`/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py --help`.
It handles a source file, canonical manifest, named submission, resumable receipt
and hash-verified downloads. Read model schema and input provenance to select
its arguments; do not implement an improvised uploader in chat. Use one stable
output directory/idempotency key and resume it after a bounded wait. Inspect all
promised output artifacts and scientific constraints; transport verification is
not scientific validation.

Read the **top-level** `get_model_schema.input_artifact_contract` for exact
source entry name, semantic type, media type and compression. An `entry` is a
fixed source role; `operations` selects a role by the published operation;
`source_kinds` selects by the source kind. Do not use a filename/run ID as the
entry name or invent a semantic type from a model name. The source media type
describes its actual bytes (such as `application/json`); the helper creates the
outer `application/vnd.fs2.scientific-manifest+json` artifact separately. Missing
contract metadata is not permission to guess. Keep rejected receipts unchanged;
an explicitly corrected request has new metadata/identity and must not replace
an accepted or unknown admission.

For sequential native, batch or mixed multi-App work use `run_scientific_workflow`
with a `scientific-workflow/v2` study. Discover its current phase schemas using
`describe_scientific_workflow`; `compose_scientific_workflow` can build a larger
plan. Include requested analysis and deliverables. Native phases name actual
input files; batch phases name source and parameter files. The durable
supervisor advances only after verified results and resumes the immutable
study after reconnects. A short queued/running observation is not completion.
Known non-admitted concurrency rejection waits visibly; ambiguous admission or
application failure stops for inspection. Keep the saved `output_directory`,
native `operation_id` values and original idempotency keys. Observe the whole
workflow with `read_scientific_workflow`; only `op-…` values identify Serverless
jobs. Before admission no job ID exists. Do not use shell backgrounding/nohup or chmod on Object Storage.
Native speech calls consume concurrency too; do not submit them all in parallel
when the caller policy allows only one active operation. Do not change keys to evade a rejected
or unknown admission. Optional `/v1/me` describes caller policy, not real-time
reserved capacity.

## Errors and user-facing results

- Before final delivery, compare the user's requested outputs and sections with
  the actual saved artifacts. Finish each item or name the missing evidence and
  its effect; successful tool/study completion alone does not complete the request.
  A structure preview or timing table is not a full scientific report. For a
  requested HTML report, write and inspect the actual HTML with every requested
  section, then deliver its real workspace link inline. Keep units, provenance,
  timing boundaries and unavailable measurements explicit. Use an analysis-only
  follow-up for missing presentation; preserve accepted work and original files.
- MCP `-32602` with `data.type: model_input_validation` means no work was
  admitted. Use each issue's JSON-pointer `field`, `rule`, and any
  `missing_fields`, `allowed_fields`, or `expected` details to fix the input.
- For 401/403 or a missing App, check this user's key and current catalog. Never
  substitute an admin credential or claim academic eligibility in the request.
- For 429, retryable 503, or an interrupted submission, retain the same
  idempotency identity, back off, and check the saved operation.
- For a terminal model failure, report the public model/App, operation ID,
  timestamps and returned structured error. Do not label acceptance as success.
- Current endpoint and speech results use `{operation, result}`; scientific
  batch results are run documents. Large endpoint results use `operation-artifact-result/v1`; the
  workbench resolver saves verified full JSON and returns compact metadata.
  Scientific
  results are versioned run documents whose output manifests point to artifacts.
  Preserve structured fields and verify artifact hashes rather than pasting raw
  files into the answer.

Model access is authorization, not a license grant or biological/clinical
validation. Describe outputs as model predictions. Do not invent snapshot,
replica, priority, or GPU controls in model payloads; those are platform settings.

Read [the complete client contract](references/client-contract.md) for transport
limits, scopes, retention, scientific-file details, and known BioNeMo differences.
