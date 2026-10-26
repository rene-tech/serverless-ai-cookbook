# CamSol protected connection (candidate)

This connector uses Cambridge's actual public login form and GET-only access to
the five advertised CamSol mode pages. It is an external Cambridge service,
not a native Scientific AI worker or an inferred vendor API. Calculation
submission, job observation and result retrieval are not yet qualified or
exposed. No scientific input is accepted by these tools.

## User connection

After the qualified connector is enabled in your workbench, open **MCP Settings
→ CamSol**, enter your existing Cambridge username or email and password in the
masked fields, save, and initialize that connection. Then ask **“Connect my
CamSol account and inspect the available modes; do not submit anything.”**
Do not put passwords, cookies or tokens in chat. No DevTools or local browser
export is needed. A challenge or expired session requires explicit user action;
the connector never loops over login attempts. Revoke the saved fields in the
same settings to prevent further connections.

LibreChat encrypts the fields in its existing user credential store. The normal
MCP manager supplies them only to this user's connection. Explicit base64 header
templates preserve every UTF-8 credential byte; base64 is transport encoding,
not encryption. The hop is loopback-only inside the personal workbench, and
the Cambridge hop uses HTTPS. Cookies live only in isolated process memory,
keyed by the user plus credentials. They are not returned in tools, written to
workspace files or shared across users. A server restart requires reconnecting.

The retained API did not support those templates and had a literal `$`
interpolation defect. `patch-private-vars.mjs` fixes literal substitution and
adds explicit `{{VARIABLE:base64}}` formatting without changing ordinary API
keys or plugin placeholder boundaries. Copying files cannot refresh its loaded
API code: **the replacement image must include and load this fix first**. The
current client has not been modified or qualified for this connection.

## Operator integration

The normal image packages the connector but enables it only with
`SCIENTIFIC_CAMSOL_ENABLED=true`. The existing entrypoint starts one auxiliary
service bound to `127.0.0.1:8786`, tied to the same PID/start-time owner. It does
not replace the API, study worker, state supervisor, skill bodies or agents.

For an already loaded, qualified API, supported admin configuration can add
`mcpServers.camsol` using `connection.json` to one user override via
`PATCH /api/admin/config/user/<user-id>/fields`. Merge only the exact
`127.0.0.1:8786` entry into that principal's existing
`mcpSettings.allowedAddresses`; preserve the existing domain/address policy.
This keeps private-address checking enabled and does not allow adjacent ports.
The admin route invalidates configuration caches; the normal MCP Settings
initialize/reinitialize action creates only that user's CamSol connection.
Do not change Dropbox, cBioPortal or application-owned MCP connections.
An unpatched current API is a stop condition, not a reason to bypass the stdio
configuration guard or invent a parallel credential store.

Preflight must capture the target user/config, all existing MCP settings and
connection scopes, process PID/start identities, idle studies and file hashes.
Verify port 8786 is free and the current instance is the authorized target.
Apply only a reviewed additive spec and file set, then compare every preserved
setting. Rollback removes only the exact new config fields and exact owned
service PID; retain encrypted user credentials unless the user revokes them.
No live activation or account login is implied by this source preparation.

## Qualification and remaining gate

The offline suite uses synthetic forms and isolated cookie jars through the
actual packaged MCP HTTP transport. It covers dynamic CSRF, one login POST,
literal and Unicode passwords, changed forms, external redirects, 307 body
replay refusal, challenges, expiry, per-user isolation and private loopback
guards. `verify-installed.cjs` checks the actual installed LibreChat manager,
schema, private-address policy and supported admin override handler.

The real account form is still unobserved after authentication. First connect
with the user's own protected settings and inspect those forms without data
submission. Retain field names/types, actions and response hashes, never field
values or raw authenticated pages. Only then implement and qualify the actual
calculation/status/output contract. Cambridge's public login and terms are
external-service provenance, not a native API contract or a new product limit:

- https://www-cohsoftware.ch.cam.ac.uk/index.php/login
- https://www-cohsoftware.ch.cam.ac.uk/
