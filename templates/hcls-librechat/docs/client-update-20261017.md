# Open-tab UI updates — 17 October 2026

Runtime source `19bcad5b3a50ad780388a646eb36d3bd86789e18`, image
`client-update-20261017-r1`, digest
`sha256:eaf15340996e3507a40ae0dd377351c6ea35b609ff6e90c36fe52fe009818618`.
Built over the current admission-recovery image `7bec331506c0`; scientific
workers, installed skills, credentials and job contracts are unchanged.

## Incident and correction

The reported saved precheck rendered in a fresh authenticated browser, while
the already-open customer tab showed links only. The customer confirmed that
one ordinary reload restored the report. Serving uncached HTML cannot replace
JavaScript already running in an open tab. Earlier release checks covered fresh
page loads but missed that boundary.

The HTML now declares its asset revision in a meta element, matching the
existing `X-Scientific-Client-Revision` response header. A small UI component
checks `HEAD /index.html` on focus, reconnection, visibility and every minute
while visible. A different revision displays an accessible update notice.
Failures, absent revision and unchanged responses do not claim an update.
Reads are deduplicated, time-bounded and aborted on unmount.

Reload is always explicit, with a confirmation and warning to save unsent text.
There is **no automatic navigation**. Jobs continue independently. Tabs running
the older code require one ordinary reload before this notice can work.

## Qualification

- Exact installed image: seven Express tests and fifteen React tests passed;
  production UI build and branding verification passed. Patch application is
  idempotent; base and default image builds include the same component.
- In the retained System QA browser, a real served index transition triggered
  the notice while the page stayed open. The unsent draft remained intact;
  dismissing reload confirmation caused no navigation. The candidate index was
  restored, an explicit reload removed the notice, and the test draft was cleared.
- The exact reported customer conversation and a saved QA precheck both rendered
  the actual findings inline on the new asset revision. Screenshots were visually
  inspected. No precheck, simulation or customer inference was rerun for this fix.
- Five retained clients passed authenticated login and mounted-workspace checks
  (six logins including the two existing shared-customer logins). HTML, HEAD
  revision and current JavaScript entry agreed on every client.
- All five API/supervisor/worker process identities remained unchanged. Old
  immutable assets were retained for open pages; only the complete index was
  switched atomically. The installed asset middleware was refreshed in process;
  the local diagnostic inspector was closed after each refresh.

Private evidence: `precheck-inline-20261017.Lsa7Dt`, including exact before/after
receipts, installed tests, actual transition screenshot, and report screenshots.
The sanitized [receipt](evidence/client-update-20261017.json) is not a claim of
all-model, capacity, failover or scientific-result qualification.

## Deployment and rollback

The source default and generated deployment link pin the published digest.
Rene, Arseny, LynxKite, Whitelab and System QA were patched in place; their
provider resource metadata continues to name the original base image. A future
recreation must select the pinned default and preserve `/data` and storage
bindings. Do not mistake a runtime overlay for a provider image update.

Each exact instance retains a private `dist-before.tar.gz`, previous middleware
and process/readback receipt under its recorded `/data/workbench-hotfixes/`
directory. Roll back that paired asset/middleware set only; preserve chat,
workspace and worker state. A browser reload is required after either direction.
