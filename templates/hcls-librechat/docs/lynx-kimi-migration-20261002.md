# Lynx workbench migration, October 2

Status: migration complete; replacement running. Account/data/access checks pass.
Scientific replay: 13 clean technical cases and one self-recovered agent error
out of 14 requests. This is not an error-free or all-workflows release claim.

The owner explicitly requested migration of the existing Lynx workbench to the
[qualified Kimi default](kimi-default-release-20261002.md). This is an upgrade of
the existing shared client, not onboarding new accounts or changing inference
capacity. Lynx retains its documented exception: two separate local logins share
one client, one tenant bucket, and one API key with eight concurrent operations
in total. Other customer endpoints and the public Gateway are outside scope.

## Exact resources

- Predecessor: `aiendpoint-e00kybbs8a1sbxcfyw`, `scientific-ai-lynx-gyorgy-md`.
- Replacement: `aiendpoint-e00a5xqzhy0d3zjg56`, `scientific-ai-lynx-kimi-20261002`.
- Project: `project-e00rene`; CPU shape unchanged, `cpu-d3 / 4vcpu-16gb`.
- Existing shared bucket: `fs2-lynx-c327dcc386444425`, mounted at `/workspace`.
- Immutable replacement image:
  `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:e96a66501807a2c446c17413f66c042b4a6ae2bdee2c32b9b05adcd1d378fd63`.
- Target URL:
  `https://port3080-nh8b93sq9rprrv0.tunnel.applications.eu-north1.nebius.cloud`.

Existing API, Token Factory, Tavily and S3 secret selectors remain unchanged.
Registration stays disabled. The first-user bootstrap password environment
variable is deliberately omitted: restored accounts must not have their existing
password hashes or profiles overwritten by startup seeding. The default email
and original study-owner identity remain unchanged. The old supervisor must be
stopped before enabling the new same-owner supervisor.

## State protection

No active chats or pending studies were observed before the cutover. Both existing
passwords were checked privately. MongoDB was fsync-locked for a consistent logical
export, then the application container was paused while copying the complete
`/data` directory, uploads and temporary files. Bucket contents stay in the same
bucket. Temporary files are retained in the private backup, not blindly restored
over the new image's runtime/tools.

The physical database backup was booted in an isolated local container of the
exact replacement image, with no network and no customer bucket or supervisor.
Every exported document and index matched: 49 collections, including both human
accounts, five conversations, 28 messages and both encrypted plugin credentials.
The service account is also retained. This is a complete MongoDB restoration,
not a conversation import that changes account or conversation IDs.

After backup/restore verification, the old endpoint reported `VMStopped` for an
unexpectedly stopped underlying VM. This records the provider observation, not
a proven root cause. The verified archives were already complete. The exact old
endpoint was then explicitly stopped; no new same-owner supervisor was enabled
before it reached `STOPPED`.

The first candidate restore attempted to stop its container before copying the
physical backup. The provider terminated the VM and interrupted that copy. No
customer data was lost: the archives remained local and independently verified.
The same unused candidate endpoint was restarted; no extra client was created.
Do not use container-stop/copy/start as a Serverless restoration procedure.

The corrected method was tested in isolation on the exact image. It imports
all documents and indexes into a separate MongoDB staging database and verifies
them before installation into the unused target. The target's initial collections
are retained in a separate bootstrap database. Customer users are installed last.
The application container and MongoDB remain running throughout this procedure.
Both saved plugin credentials are decrypted with the backup's keys and encrypted
with the new instance's keys using native LibreChat cryptography. Their plaintext
API-key values do not change; account IDs and password hashes do not change.
The new URL requires a fresh login, not reuse of old browser session cookies.
The original encryption keys remain in the private backup for recovery.

The live import also exposed a MongoDB process open-file limit of 1024 while
staging/renaming duplicate index files. WiredTiger aborted; the application
container stayed running. The incomplete import was reconciled back to the
verified unused bootstrap collections before retry. The replacement's MongoDB
process was recovered with a 64000 soft open-file limit (below its existing
524288 hard limit), and the full restore then completed. No cloud quota, node
capacity, account or API limit changed. Retain this prerequisite for future live
full-database restores; the original default image's entrypoint was not modified
by this migration.

Private operational evidence, backups and scoped migration scripts:
`/home/tux/secure-handoff/fs2-lynx-kimi-migration-20261002/` (directory 0700,
private data files 0600). Never commit these archives, sessions, credentials or
customer chat contents. The baseline logical database SHA-256 is
`cd05d29efeeece86e2198a3d27f7dd84452b8ab0f02d055a3a35c0fe759246a7`.

Serverless stop/restart destroys local disk; retained endpoint metadata is not
rollback. Recovery requires these verified database/runtime archives and the
existing secret references. Ordinary container restarts retain the restored
local state. Do not start a second same-owner study supervisor during recovery.

## Acceptance boundary

Migration acceptance must cover preserved customer records and usable encrypted
credentials, both real login paths, account-isolated chats, shared bucket access,
unchanged API grants and key, actual default-agent configuration, original Lynx
inventory/OpenFF workflows and a hosted GROMACS execution with recovered files.
Retain exact operation IDs and independent artifact checks. A short MD example
does not validate the customer's complete production GPCR protocol, arbitrary
scientific advice, or sustainable eight-session capacity.

## Completed customer-path checks

Both existing account IDs and password hashes match the backup. All five
original conversations and 28 messages are unchanged. Both logins authenticate
through the public API and real browsers; their old chats remain isolated. Each
sees exactly `amber`, `gromacs`, `gromacs-mpi`, `lammps` and `namd`. Both read their
existing shared-bucket markers. Image manifest/layer identity and seeded Kimi K3
high-reasoning configuration were verified; no model/prompt override was used.

Each login ran seven actual seeded-agent cases against the customer workspace:
original mmCIF inventory, inventory plus CSV, force-field advice, the original
20-hydroxyecdysone OpenFF preparation, charged methylammonium preparation, catalog
discovery and a hosted GROMACS starter. Both full OpenFF exports passed five
independent chemistry/file checks each. All 318 output objects matched independent
HTTP and S3 readback; all 62 delivered links resolved. The original customer CIF
was not copied into another tenant's bucket.

| Workflow | First account | Second account |
| --- | ---: | ---: |
| Original mmCIF inventory | 7.1 s | 28.7 s, recovered command error |
| Inventory plus CSV | 12.9 s | 9.8 s |
| Charged OpenFF ligand | 19.3 s | 12.8 s |
| Original steroid OpenFF ligand | 46.9 s | 46.9 s |
| Hosted GROMACS including delivery | 114.9 s | 124.3 s |

Both GROMACS operations completed and their native output hashes were verified:
`bade8b7c-d685-4155-8495-9a96762703cd` and
`e4e9c0b1-261e-4544-a99b-1daf01e5b0ec`. These are unchanged packaged minimization
plus 20 ps NVT, 20 ps NPT and 20 ps production, not the customer's full protocol.

A browser-created compound inventory/CSV request also completed. Its actual
Workspace download matched S3 byte-for-byte. Existing chat history and Nebius /
NVIDIA branding were visible. Test conversations are labelled `Migration QA`;
original customer titles/messages were not changed. Both operator-owned browser
sessions are closed. No customer notification was sent automatically.

### Remaining agent issue — not counted as clean acceptance

In the second original-inventory replay, the deterministic inventory tool
succeeded. The agent then generated an extra Gemmi command using nonexistent
`gemmi.make_one_letter_sequence`, producing `AttributeError`. It corrected its
approach and delivered the preserved measured inventory in 28.668 seconds.
The strict verifier retains that case as failed clean-agent acceptance despite
the successful final answer. There were no failed customer HTTP requests,
watchdog aborts, empty final answers or unfinished requests in either cohort.
This shows that the agent can still make recoverable ad-hoc coding mistakes;
it does not establish arbitrary-command reliability or scientific correctness.
No passing rerun was substituted for that result, and the default image was not
hot-patched to conceal it. The account/data migration passes independently.

## Final retention and bindings

The original shared endpoint remains `STOPPED`, not deleted. Only the replacement
Lynx workbench is running. The same API key still has its existing eight-operation
limit, shared across both logins. No new tenant, user, key, bucket, GPU allocation,
DNS record, public Gateway or unrelated client was changed.

The lifecycle policy, onboarding receipt and private owner handover now point to
the new URL. An additional current-state logical database and runtime-key backup
was saved after qualification without pausing/stopping the application. The
unused bootstrap/staging databases were removed after confirming they contained
no customer-originated work. Both original and post-migration backups are
retained privately. Do not treat a stopped endpoint's metadata as a disk backup.
