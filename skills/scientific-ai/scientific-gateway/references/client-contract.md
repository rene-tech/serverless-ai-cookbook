# Scientific AI Apps client contract

This reference supplements `SKILL.md`. Live `tools/list` and
`get_model_schema` remain authoritative for the caller and deployment.

## Transport and identity

- Transport: stateless MCP Streamable HTTP at the exact `/mcp` path. Do not add
  a trailing slash. Use a conforming MCP SDK rather than hand-writing routing
  headers. TLS verification remains enabled.
- Authentication: `Authorization: Bearer <ordinary inference API key>` supplied
  by the client configuration. Never use an admin bootstrap token.
- A practical full-workflow key has `read:catalog`, `run:submit`,
  `read:operations`, `read:results`, `artifacts:write`, and, if cancellation is
  offered, `run:control`, plus a model allowlist.
- Ordinary serving operation access is tied to the exact submitting key and
  principal. Preserve that identity until required results are retrieved.
- Tool discovery is authorization-aware, private, and uncached. Subscribe to
  tool-list change notifications where supported. Compare the returned
  `tool_catalog_revision` and refetch tools when it changes; reconnect after
  replacing credentials.

The MCP SDK handles protocol negotiation. Let LibreChat manage
`MCP-Protocol-Version`, request routing headers,
client capabilities and JSON-RPC envelopes. Do not configure those as static
headers because method and tool-name values change per call.

## Limits and retention

Use the current model schema, upload reservation and download handle for
request limits, allowed encodings, size bounds and expiry. Do not reuse limits
from an earlier deployment. A signed transfer handle expires independently of
the API key and the underlying immutable artifact.

Raw bytes are not exposed as agent tools. The trusted client uploads through
the handle/content path returned by reservation and downloads through the
authorized HTTP content route or a download handle. Manifest inspection returns
compact metadata rather than base64. Keep transfers outside model context.

Use returned retention/expiry fields and the tenant's configured storage policy.
Never assume a chat history is the durable store for an output.

## Tool families

Core tools cover:

- catalog/schema: `list_models`, `list_scientific_models`,
  `get_tool_catalog_revision`, `get_model_schema`;
- native operation reads: `get_operation`, `get_operation_result`, and the
  advertised native lifecycle tools; no UUID job aliases;
- native async serving (`operation.id` beginning `op-`): the App's named typed
  submission tool, `get_operation`, then `get_operation_result`;
- scientific runs: the App's typed submission tool, `get_operation`,
  `get_operation_result`, `cancel_operation`;
- artifacts: `begin_scientific_artifact_upload`, `finalize_scientific_artifact_upload`,
  `get_scientific_artifact`, `download_scientific_artifact` and
  `multipart_scientific_artifact_upload`.

There is also one named typed tool per authorized App. Paused/disabled acceptance
clones are excluded; restricted keys see fewer Apps. Discover the current count
instead of treating a historical event catalog as the deployed contract.

### One native job identity

| Example returned ID | Hosted status tool | Hosted result tool |
| --- | --- | --- |
| `op-e74c396a38794261` | `get_operation` | `get_operation_result` |
| `ses-0123456789abcdef` (live session) | `get_operation` | `get_operation_result` |

These are shape examples, not authority to read another caller's operation.
Native async responses nest the unchanged ID in `operation.id`; `QUEUED` with
`result_available: false` is acceptance, not a prediction. Never resubmit to
obtain a different ID or coerce `op-*` into a UUID. Workbench polling, result
recovery and visualization accept the same native ID. Retrieve and verify
artifacts outside model context. Whole workflows expose their actual native
operations and are observed by `output_directory` with `read_scientific_workflow`.
They never publish a second job ID. Local command execution and artifact
identifiers are not platform job IDs.
A missing lifecycle tool is a client/grant gap, not permission to submit again
or switch credentials.

## Scientific batch document

Read the exact typed tool schema: MD/scVI/MPI tools expose `request` and
`idempotency_key`; staged tools expose the run fields directly plus
`idempotency_key`. These are current execution families, not versions to try
sequentially. The run object's schema is
`fs2-serve.nebius.ai/scientific-run-request/v1`, including the advertised
operation, an allowed `service_class`, a finalized `input_manifest`,
model-specific `parameters`, and optional `client_context` identifiers. Use one
logical `batch_id` with distinct correlation IDs for related items. Do not
invent service classes or infrastructure priority; use discovery values.

For files, reserve/write/finalize each real input, build a manifest containing
the immutable returned references, serialize it canonically, then upload and
finalize the manifest. Fixture artifact IDs in examples are not caller-owned.
An upload reservation returns `upload_id`, not a job ID. Finalize with that ID;
the response is `{"state":"finalized","artifact":{...}}`. Multipart commands
use the outer upload ID plus `action`, optional `multipart_upload_id` and
`part_numbers`; there is no operation to poll or cancel for a reservation.
Manifests use `entries`, each with `name` and `artifact`, never role/ref aliases.
After submission, poll status and wait for `operation.result_available`. The
scientific result describes attempts, execution identity, semantic validation
and output artifacts. Download the output manifest and its entries; verify exact
SHA-256 and byte size.

## Selected runtime compatibility

- Boltz2 is the protein-only portable runtime. It requires explicit A3M beneath
  each polymer and does not expose NIM ligand, DNA/RNA, affinity, constraint,
  template, step-scale or full-PAE features.
- OpenFold2 accepts exactly `input_id`, uppercase canonical `sequence`,
  `selected_models: [1]`, and `relax_prediction: false`. It has no external
  MSA/template, ensemble or relaxation path in this deployment.
- NVIDIA BioNeMo Agent Toolkit instructions and scripts remain useful domain
  guides, but many call NVIDIA REST URLs, use different authentication and
  expect immediate response JSON. Installing them does not redirect those calls
  to this MCP server. Adapt invocation to the discovered named tool and durable
  result flow; never drop unsupported inputs or fabricate missing scores.
- OpenFold3 native and OpenFold3-OpenBind scientific batch are separate Apps.
- AlphaFold3 and other licensed/academic runtimes require operator-prepared
  assets and applicable terms. Model access does not itself grant a license.
- There is no OpenAI token streaming guarantee, no universal NIM parameter
  parity, and no assumption that a discoverable App is already warm.

For exact examples and selected-runtime sources, call `get_model_schema`.
