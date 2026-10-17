# Paired Scientific AI router, service and UI maintenance

`scientific-router-maintenance.cjs` is an operator-only, release-qualified helper
for the pinned Node 24 / Express 5.2.1 workbench. It is not a public endpoint,
version adapter, runtime watcher or generic hot-reload facility. It installs the
current `/workspace/preview` router together with its matching service and UI
without restarting the API, study worker, supervisor or provider endpoint.

The retained-client asset patch alone is insufficient: an already loaded
Express router does not acquire routes when its source file is replaced. The
current UI requires the authenticated, bounded preview route and no longer
falls back to downloading arbitrary-size reports.

## Preparation and invocation

Use the existing loopback-only maintenance-inspector transport recorded in
`/home/tux/secure-handoff/gromacs-chat-e2e-20261016.lnPajd/reload_service.cjs`.
Reuse its PID/command-line validation, existing-debugger refusal and verified
inspector closure; replace its old function-export mutation expression with the
calls below. **Do not run that historical service-mutating expression.** Never
expose port 9229 or kill/restart the API to apply this patch.

1. Inventory the exact instance and API/worker/supervisor PID/start identities.
   Keep its URL, state volume, bucket, current running studies and account
   configuration unchanged. Back up the three target files and record hashes
   outside the instance. Stop if another writer owns a patch.
2. Stage the exact qualified image's `demos/service.cjs`, installed
   `api/server/routes/scientific-demos.js` and `client/dist/index.html` in a
   private staging directory. Do not overwrite these live targets yet.
3. Copy all required immutable hashed assets first. If an existing hashed name
   has different bytes, stop. Keep old assets for existing browser tabs. Record
   a SHA-256 manifest of installed assets; preserve non-asset current resources
   required by the qualified image as part of the separately verified release.
4. Ensure the qualified `scientific-client-assets.cjs` middleware is installed
   using `installOnRunningApp`. It must be present exactly once. Stage the
   maintenance helper under a unique release path and keep that module cached
   for the entire transaction; reloading it would discard its rollback handle.
5. Through the existing inspector, invoke the helper synchronously:

```javascript
const require = process.getBuiltinModule('module').createRequire('/app/package.json');
const app = require('/app/api/server/index.js');
const maintenance = require('/data/workbench-hotfixes/RELEASE/scientific-router-maintenance.cjs');
maintenance.install(app, {
  release: 'current-contract-20261017',
  service: { path: '/data/workbench-hotfixes/RELEASE/stage/service.cjs', sha256: 'EXACT_SHA256' },
  router: { path: '/data/workbench-hotfixes/RELEASE/stage/scientific-demos.js', sha256: 'EXACT_SHA256' },
  index: { path: '/data/workbench-hotfixes/RELEASE/stage/index.html', sha256: 'EXACT_SHA256' },
  assets: {
    'assets/index.EXACT.js': 'EXACT_SHA256',
    'assets/index.EXACT.css': 'EXACT_SHA256',
    // Include the complete qualified installed assets manifest, not just entry files.
  },
});
```

`targets` is a test seam; production uses the three fixed canonical paths in
the helper. Do not pass customer credentials or request bodies into this
maintenance call. The receipt contains only release, PID, routes and hashes.

The helper verifies hashes, the existing mounted-router identity, the same
authentication middleware, retained route/service exports and the new preview
route. Candidate modules compile under their canonical filenames, so installed
aliases and relative imports resolve normally. Only the two module-cache entries
and the existing mounted router's handler are replaced. The old exports are not
mutated, preserving handlers already executing against them. The HTML entry is
published last in the same synchronous event-loop turn.

## Verification, rollback and closeout

Qualify **System QA first**, then the other authorized retained instances one at
a time. Before finalizing, prove authenticated preview/download, ordinary
cached-browser reload with inline report rendering, unchanged login/workspace,
current API/native operation IDs and the relevant scientific workflow. An open
tab needs one ordinary reload; do not rewrite its saved conversation. Compare
API/worker/supervisor PID/start identities and check existing study progress.
No running study may be replayed or interrupted as part of maintenance.

To roll back, in the same API process and through the same cached helper:

```javascript
maintenance.rollback(app, 'current-contract-20261017');
```

Rollback verifies nobody changed the router, service or three live files, then
restores the old index first, source bytes, cached modules and handler. A
conflicting writer is an explicit failure, never silently overwritten. The
in-memory rollback handle is not a durable backup; preserve the external backup
and receipt. On successful verification, call
`maintenance.finalize(app, 'current-contract-20261017')` to release that handle.
Close the inspector and prove it is no longer listening after **every** call.

This refresh updates the API process only. The following companion refreshes
are mandatory; source-file copies do not update already imported Python modules
or JavaScript functions. Do not claim a complete client rollout from API/static
tests alone. Provider VM
recreation loses overlays; future/replacement clients must use the qualified
current image and retain the customer's persistent state.

### Drained MCP connections and study worker

The pinned application's `getMCPManager()` owns these connections. The existing
loopback loader `reload_execution.cjs` in the same private evidence directory
already uses `manager.appConnections.disconnect(name)` then
`manager.appConnections.get(name)` for `environment-execution` and
`structure-viewer`. Do not kill their PIDs directly. First verify the exact
connection has zero SDK `_responseHandlers` and zero active manager borrowers;
if calls are active, wait rather than terminating a command. Retain the recorded
connection object and verify the replacement is distinct. Reinitialize the
current tool list through `refreshToolList()` and compare schemas, not just file
hashes. Use the inspected pinned lifecycle methods, not wholesale manager or
registry replacement. Do not change current credentials or user configuration.

`scientific-demos` is per-user (`LIBRECHAT_USER_ID`), even in a managed instance.
Enumerate **loaded** user connections, not just app connections. The current
`manager.getUserConnections(userId)` returns that user's Map;
`manager.disconnectUserConnection(userId, 'scientific-demos',
{reason:'lifecycle'})` removes its cached connection and honors existing borrower
leases. The next authenticated request recreates it with that user's actual
credentials; qualify that reconnect under the intended login. Do not synthesize
a user or pass one customer's credentials into another scope. User-scoped
`structure-viewer` configurations need the same treatment. Absent connections
need no teardown; their first creation loads the current source. Never use
`disconnectAll` or touch unrelated Tavily/customer MCP connections.

The pinned manager exposes these Maps at runtime. A scoped maintenance
expression, run only after the freshly observed chat/tool activity drains, is:

```javascript
const manager = require('/app/api/config').getMCPManager();
const names = new Set(['environment-execution', 'structure-viewer', 'scientific-demos']);
const appEntries = [...manager.appConnections.connections].filter(([name]) => names.has(name));
const userEntries = [...manager.userConnections].flatMap(([userId, connections]) =>
  [...connections].filter(([name]) => names.has(name)).map(([name, connection]) => ({userId, name, connection})));
function requireIdle(connection) {
  if (connection.client._responseHandlers.size || manager.connectionBorrowers.get(connection)) {
    throw Error('Current tool activity has not drained; leave this connection running');
  }
}
for (const [, connection] of appEntries) requireIdle(connection);
for (const {connection} of userEntries) requireIdle(connection);
if (manager.pendingConnections.size || manager.activeConnectionCreations.size) {
  throw Error('A connection is being created; recheck after it finishes');
}
for (const [name, previous] of appEntries) {
  requireIdle(previous);
  await manager.appConnections.disconnect(name);
  const next = await manager.appConnections.get(name);
  if (!next || next === previous) throw Error('Connection did not refresh');
  await next.refreshToolList();
  // Compare await next.client.listTools() against the exact release manifest.
}
for (const {userId, name, connection} of userEntries) {
  requireIdle(connection);
  await manager.disconnectUserConnection(userId, name, {reason: 'lifecycle'});
  // Reconnect via this user's existing authenticated session, not copied keys.
}
```

This is not a concurrent-traffic fence: if new chat activity appears, stop and
re-establish a drained interval. The generic model-submission pause does not
pause local shell commands. No helper may convert a busy tool into forced
termination. Separately refresh the `scientific-ai-apps` remote MCP connection
after its backend/tool schema rollout using the same scoped lifecycle methods.

For the worker, `scientific-study-worker.py::supervise` already restarts only its
`--worker` child when that child exits. The API child exiting instead shuts down
the whole supervisor and is forbidden here. Under the existing nonblocking
`receipt_lock(studies.registry() / 'queue-worker')`, require an empty/non-active
queue, fresh health with no current/blocked study, and the exact worker
PID/start identity parented by the unchanged supervisor. A held lock means a
phase is active: stop and wait. Only then signal that **worker child PID** with
SIGTERM, keep the queue lock until the supervisor creates its replacement, and
release the lock. Verify fresh health from the new worker and unchanged
API/supervisor PID/start identities. Never signal a process group, replay a
study, erase a receipt or restart an active worker to apply new code.

`test_scientific_worker_refresh.py` exercises this exact existing supervisor
mechanism with a local idle queue and a harmless stand-in API process. Real
customer queue/connection draining must still be freshly proven at rollout.

## Local qualification

Run the tests only in disposable containers with no network or customer
configuration. Both pinned images contain Express 5.2.1. The actual-image test
deliberately removes the preview registration from its **test** cached router
to reproduce the retained-process seam; it uses stubbed JWT/plugin persistence,
not a live MongoDB login. Source/service functions otherwise come from the
baseline image and exact candidate worktree.

```sh
docker run --rm --network none \
  --env SCIENTIFIC_EXPRESS_MODULE=/app/node_modules/express \
  --env SCIENTIFIC_TEST_IMAGE_CONTRACT=true \
  --mount type=bind,src=/ABSOLUTE/CHECKOUT/templates/hcls-librechat,dst=/qualification,readonly \
  --entrypoint node EXACT_IMAGE_ID \
  --test /qualification/test-scientific-router-maintenance.cjs \
  /qualification/test-scientific-client-assets.cjs
```

The suite checks unchanged PID, in-flight completion through the original
service, route/auth preservation, ordinary shell refresh, immutable old assets,
bad hashes/assets/source rejection, rollback after failed HTML publication and
conflicting-writer refusal. The actual preview route returns authenticated
plain text with `nosniff`; unauthenticated, missing, escaping and oversized
requests return 401, 404, 400 and 413. Original oversized downloads still work.
These tests establish the maintenance mechanism, not customer-release readiness.

Current marked gateway refusal (`admission: not-submitted`, retryable and one of
`ADMISSION_PAUSED`, `ADMISSION_LIMIT_REACHED`, `MODEL_MAINTENANCE`) enters the
existing bounded same-idempotency admission wait. Unmarked/transient 503 remains
ambiguous and is never resubmitted automatically. The persisted receipt retains
the actual marker and Retry-After seconds; this is not a model-execution retry.

Historical campaign runners `scripts/qualification/{run_campaign,batch_transport}.py`
still depend on retired deployment contracts and are not current runtime paths.
Their retirement also requires handling `qualify_worker_recovery`, `reevaluate`,
`observe_campaign`, `verify_diffdock_public` and their four exclusive test
modules. Do not run them for this release or silently adapt them to old APIs;
retain historical scientific evidence while closing out that offline tooling.
