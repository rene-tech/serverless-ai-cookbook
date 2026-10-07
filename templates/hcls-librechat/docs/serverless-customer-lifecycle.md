# Customer LibreChat on Serverless

The current Scientific AI client is **LibreChat**, in `templates/hcls-librechat`.
`life-science/bionemo-agent` is the historical agent recipe, not the current
runtime. Managed and customer-owned installations use the same client image and
scientific skills. Customers do not need a Kubernetes cluster.

## Two kinds of persistence

| Location | Contents | Ownership |
|---|---|---|
| `/workspace` — Object Storage | Scientific inputs, results, scripts, durable study receipts and example data | Shared tenant bucket by default; private-user bucket when configured |
| `/data` — dedicated Nebius filesystem | MongoDB, accounts, chats, agents, presets, encryption keys, uploaded attachments and upgrade snapshots | One filesystem per LibreChat instance; never shared by concurrent instances |

An S3 mount alone is **not** a chat backup. Do not place MongoDB on S3/FUSE.
New deployments require the separate filesystem; the runtime rejects an
ephemeral/container-local `/data`. Both volumes must remain available when the
Serverless VM is replaced. Use the filesystem in the client's project/region.

The deployment helper creates no model cluster and changes no model permissions.
Existing platform API keys determine App access and concurrency. Login accounts
inside LibreChat are separate from inference users. A deliberately shared client
can have several logins and one inference key: those requests are attributed to
the same inference owner, not independently billed per login. Preserve an
owner-approved shared deployment; do not split it during registration.

## Managed deployment

1. Reuse the tenant/user and bucket returned by `GET /v1/storage`. The existing
   `POST /v1/storage/credentials` discloses that authenticated user's S3 pair;
   store it in MysteryBox, never in Git or a launch URL. Provision customer
   identity/storage through the platform's tenant lifecycle, not this template.
2. Run `scripts/create-state-filesystem.sh` with `NEBIUS_PROJECT_ID` and a stable
   `WORKBENCH_NAME`. Record the returned filesystem ID. The default size is
   32 GiB; `LIBRECHAT_STATE_SIZE_GIB` is configurable. This is separate from the
   workspace's object-storage quota.
3. Set `LIBRECHAT_STATE_FILESYSTEM_ID` for `scripts/deploy.sh`, along with the
   existing project, subnet, email, password-secret, platform-key, Token Factory,
   Tavily and S3 secret selectors documented in the main README. For bulk setup,
   each person's manifest needs its own `state_filesystem_id`.
4. Use `SERVERLESS_DRY_RUN=true` first with a CLI supporting endpoint dry runs.
   Then create the endpoint and verify real login, mounted files and a customer
   workflow. A provider dry run cannot prove image access or application health.
5. In the platform's **Customers** page, open the tenant and register the exact
   existing endpoint and inference owner. Registration is metadata-only; it
   neither clones the endpoint nor changes keys, accounts or storage.

Keep a stable `SCIENTIFIC_STUDY_OWNER` namespace for replacements. Parallel QA
must use a different namespace and a different chat filesystem, even when it
reuses the system tenant's workspace bucket. Do not create another customer
tenant/bucket for every test attempt.

## Updates and recovery

The Serverless API currently requires a replacement endpoint to change its image.
The admin **Upgrade LibreChat** operation therefore:

1. Validates ownership, the independent state filesystem, the pinned release
   and the provider's copied create request **before** stopping the predecessor.
2. Stops the predecessor so only one MongoDB writer can own the filesystem.
3. Creates a deterministic replacement using the same mounts and secret
   references. Before MongoDB starts, the client records a state snapshot.
4. Waits for the public application health check, then updates the durable
   customer binding and URL. The old endpoint record is retained, not deleted.
5. If startup fails, stops any partially created successor and recreates the
   previous image, restoring its pre-upgrade state when a snapshot exists.

The operation is persisted in PostgreSQL and can resume after a worker restart.
Runtime filesystem locking prevents concurrent writers. Restore is one-shot:
an ordinary later restart must not rewind chats created after recovery. Displaced
state is retained beside the snapshot for investigation.

Finish active chat turns before an upgrade. There is an interruption and the
managed HTTPS URL changes; open the updated URL from Customers. This is not a
zero-downtime upgrade or a promise that an in-memory tool process survives.
Already submitted platform jobs have durable operation IDs and are not implicitly
cancelled or resubmitted by client replacement.

User-created chats, logins, settings, agents, encrypted provider credentials and
uploads stay together. Seeded agents use a three-way merge: untouched defaults
can update, while customer-edited fields are retained. Existing account passwords
are never reset by startup seeds. Scientific files stay in the same bucket.
Store custom scripts in `/workspace`; manual edits or package installs in the
container image are ephemeral and must be captured in a reproducible image or
environment definition. Generated `librechat.yaml` follows deployment settings,
not manual edits to the generated file.

Snapshots on `/data` protect an upgrade, **not loss/deletion of that filesystem**.
An independent off-filesystem backup/retention policy is a separate operational
requirement. This release does not claim cross-region disaster recovery.

## Legacy clients and cleanup

Instances without a dedicated chat filesystem are inventory-only and display
**migration required**. Export their full database, runtime encryption keys and
uploads and prove restoration before their first stop. Stopping Serverless
destroys its local disk; a stopped endpoint record does not contain that data.
Do not treat successful restoration of a single exported conversation as full
account migration. Owner-held endpoints expose no lifecycle actions.

The cloud inventory deliberately includes stopped and unassigned resources.
“Unassigned” does not mean “unused”: check ownership, active work, references and
retained data before retiring an exact resource. The customer view hides legacy
identity clutter by default without deleting those identities or their history.

## Customer self-service

The deployment button pre-fills the CPU client, port and state-volume settings.
It cannot include secret values. Before Create, the customer selects their
project/subnet, adds their platform and conversational-provider keys, and mounts
their existing workspace bucket at `/workspace`. Use the same runtime and
durability settings as the managed deployment above.

The current release registry is private. The customer project needs pull access,
or the operator must publish a separately checked public image. A link does not
grant registry access. Until that distribution decision is completed, describe
this as a **configured Serverless deployment**, not anonymous zero-configuration
one-click onboarding. Customer-owned instances are not remotely upgraded by the
platform unless management has explicitly been delegated.
