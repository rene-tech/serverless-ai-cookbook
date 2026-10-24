# Verified tool reports in the conversation

HTML returned by `visualize_workspace_media` must be visible even when the
assistant omits the Markdown relay. The client reads completed tool results
directly and displays their verified workspace HTML links after the message
content, outside collapsed tool and activity panels. Streamed completions and
reopened saved messages use the same renderer. No model call or report creation
is performed by rendering.

Only this viewer's completed tool-call output is inspected. User text, reasoning,
arguments, unrelated tools, failed calls and incomplete output cannot trigger
reads. Current flattened text and serialized MCP text content are supported.
Links still pass the existing workspace URL validator and authenticated,
size-bounded preview reader; the opaque-origin CSP sandbox is unchanged.

Within one message, canonical report paths have one preview. Repeated tool
results and an assistant Markdown relay retain their original links without
creating additional frames or reads. This ownership is a local React context,
not a global cache shared across conversations or users. Reports without a tool
result continue to render through the existing Markdown path. Optional missing
metadata remains nonfatal and does not fabricate a JSON artifact.

`patch-workspace-tool-reports.mjs` installs the two components and adds one
message-wide wrapper to the pinned `ContentParts` boundary. It fails closed on
an unrecognized seam and is idempotent. The default-release recipe includes the
patch and focused renderer tests. An additive candidate over the qualified
parent needs only rebuilt UI assets and these source changes; worker, API,
skills, model settings and ownership configuration are unchanged.

Offline regression evidence covers completion arriving in an open message,
saved-message remount, repeated equivalent paths, Markdown relay deduplication,
closed tool details, ownership scope, error/metadata handling and rejected
external or malformed links. Actual saved-chat pixels and a view-only new turn
remain a separate qualification gate on the exact static release. Source tests
alone do not establish deployed client acceptance.
