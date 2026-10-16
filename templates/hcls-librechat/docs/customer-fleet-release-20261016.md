# Scientific AI client state and interface release — 16 October 2026

Candidate: `workspace-fleet-20261016-r3`, manifest
`sha256:5595cfb290b00b78390d204300eca559dd9ef297784f63a0efc8eb19b9f3a556`,
config `sha256:9450c8c07d691b15cbd046a3d68f4ab530aaeefa5cd53406d9b3eb1897415495`.
Image source: `ebee046b20dc195ab729b0dc55a5ab98ad27d37f`.
Registry: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc`.
Skills remain `2026.10.15.1`; the selected conversational model is unchanged.

## Corrections

The preceding native-polling release retained the newer scientific SDK and file
handling, but its actual image did not contain the required state supervisor or
Scientific AI browser shell. Its source and earlier-image checks did not prove
those features in the immutable release. The broad preservation paragraph in
the preceding README was therefore incorrect; its dated evidence remains intact.

This image composes the native-operation runtime with:

- the dedicated `/data` supervisor, exclusive writer lock, persistent uploads,
  encryption state and non-destructive user/agent seed merge;
- bounded MongoDB diagnostic-log rotation (64 MiB, three rotated logs);
- the Scientific AI landing page, Getting started, Apps, Runs and Workspace;
- Nebius header and the Nebius/NVIDIA powered-by footer;
- the existing file-upload, bucket-picker and saved-attachment implementation;
- the existing client guard that prevents polling a synthetic `new` conversation;
- the current catalog MCP adapter, separating full enumeration from optional
  search and ignoring a stale chat's old query argument during enumeration.

No model runtime, customer grant, bucket quota, key expiry, inference budget or
backend Gateway is changed by this release. An explicitly shared client retains
its separate login accounts and its shared platform-key attribution.

## Packaging and qualification

`scripts/verify-customer-state-image.py IMAGE` checks installed source hashes,
the real image entrypoint, compiled UI markers and the query guard. Run it on the
exact published image before promotion, alongside the existing installed upload
and SDK checks. Dockerfile labels or a successful source unit test are insufficient.

The additive runtime recipe alone is not a final client image. Compose the
runtime, `Dockerfile.customer-state`, and `Dockerfile.branding` stages using explicit
immutable `WORKBENCH_BASE` arguments, then verify the final image. The latter
restores the entire Scientific AI browser shell and current catalog MCP adapter.
Keep all eight installed source hashes in the verifier aligned with that release.

The [exact-image receipt](evidence/customer-fleet-release-20261016.json) records
five verified replacements and six login paths, including the retained shared
client. Eight installed module hashes match the release on every instance.
Original login hashes, conversations, messages, credentials and bucket bindings
were preserved. The additional workbench uses an existing demo tenant; no new
tenant, model key or workspace bucket was needed.

Two consecutive unchanged-image browser cohorts each uploaded seven arbitrary
file fixtures, downloaded six with identical bytes, played audio and retained
attachments after reload without submitting inference. Two further real-agent
cohorts used the approved Kimi default: full authorized catalog, GROMACS schema,
Tavily documentation research, local Python computation and a verified browser
download. Each completed five tool calls with zero tool errors. No scientific
GPU job was submitted. The installed SDK passed 20 tests; the real skill loader
loaded 84 skills and 86 resources with 85 core file hashes verified.

Preserved earlier failures include the missing browser shell, the old catalog
helper's malformed/filtered discovery and the incomplete response from an
inherited QA-only GLM configuration. These are not passing final cohorts.
Raw histories, private bindings, credentials and backup limits stay outside Git.

## Upgrade boundary

Stop the predecessor before starting another MongoDB writer on the same state
filesystem. Back up and verify legacy local state before stopping its Serverless
endpoint: stopping deletes the VM and local disk. Replacements reuse the existing
state filesystem, workspace mount, secrets and scientific owner. The managed
tunnel URL changes; publish the replacement URL only after validation.

This is client lifecycle/interface qualification, not a new scientific benchmark
or a claim that every hosted model, scaling bound, skill or research workflow has
passed. Existing native-operation and scientific-runtime evidence keeps its own
scope and date. The registry still requires authorized pull access.
