# Native execution IDs

The Scientific AI product uses the Serverless execution ID directly. A job's
`op-...` ID is identical in REST, MCP, workbench tracking and the operator console.
Live audio uses its actual `ses-...` session ID; synchronous predictions retain
their native `sync-...` receipt ID. Never convert these into UUIDs or implement an
old-to-new job resolver.

Local whole-study IDs, artifact IDs, upload IDs and local process IDs identify
different objects. They are not aliases for a remote job. A lost admission
acknowledgement can have a request receipt without a confirmed job ID; do not
invent one or submit a second request to obtain one.

## Candidate and activation

`Dockerfile.native-identities` overlays the existing qualified inline-report
image without changing models, credentials, storage, login/history, the UI or
scientific dependencies. It updates bounded polling, result recovery, structure
viewing and the gateway/precheck instructions together. It deliberately rejects
old UUID job references.

This source is a candidate, **not a live/default-image qualification**. Activate
it with the native-ID Scientific AI API after its Serverless identity-preparation
dependency (API 0.11.122+) is live and tested. Preserve active work; do not patch
client polling while an old-identity study is still running. Existing files and
chat history are retained; old job links are not a permanent API contract.

Before promotion, verify real REST/MCP submission, idempotent replay, progress,
result download/rendering, cancellation and continuation with internal QA. Check
the returned ID in the native console/listing. Promote the exact qualified image
through the normal default-release workflow, then update all five managed
clients without resetting their state. Do not change the deployment button or
default image based on offline tests alone.
