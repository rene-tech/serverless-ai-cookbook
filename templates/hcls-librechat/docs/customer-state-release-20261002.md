# Persistent Serverless client release — 2 October 2026

Release: `customer-state-20261002-r3`, immutable registry digest
`sha256:873be148673dec6dc191ba30d2933c01acee4622fd3fa14888388378539f13d3`.
Repository: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc`.
Built source: `4612a2b`; parent image:
`sha256:e96a66501807a2c446c17413f66c042b4a6ae2bdee2c32b9b05adcd1d378fd63`.
Kimi K3/high, scientific skills `2026.10.01.6` and existing scientific tools are
unchanged. This is lifecycle qualification, not renewed proof of every scientific
workflow or model capability in the base image.

## What changed

A required dedicated `/data` filesystem keeps MongoDB, accounts, chats, uploads,
encrypted credentials and agent settings across replacement of the Serverless VM.
The S3 workspace remains separate and may be shared by tenant users. A filesystem
lock prevents two live MongoDB writers. Seeded accounts never reset saved passwords;
seeded agent settings use a three-way merge that preserves customer-edited values.
Upgrade snapshots are created before database startup. Rollback restores once,
preserving subsequent chats on later restarts. No customer Kubernetes is required.

The [operating guide](serverless-customer-lifecycle.md) describes deployment,
managed registration, replacement, self-service and legacy migration limits.
The historical `life-science/bionemo-agent` README now points to this template.
The deploy button pre-fills a CPU endpoint and state volume without embedding keys.
Private-registry access is still required; anonymous public one-click deployment
has **not** been qualified or enabled.

## Live qualification

Target: project `project-e00rene`, `eu-north1`, CPU D3 4 vCPU/16 GiB, dedicated
32 GiB filesystem `computefilesystem-e00gqq5jjwr47xn4b4`; existing system bucket
reused. No new tenant, bucket, inference key or GPU. Exact operation receipts are
in the backend's `k8s-inference/acceptance/customer-workbenches-20261002/README.md`.

- Initial replacement and unchanged-release repeat each passed 14 checks: two
  public logins, original identity/password hashes, encryption keys, chats/messages,
  customer agent instructions, preset, encrypted credential, attachment, bucket
  file and the public history API. Second run used the real admin upgrade button.
- A real post-upgrade public chat retained Kimi K3/high and wrote the exact
  requested workspace file through its execution tool in **6.098 seconds**.
- Deliberately unhealthy successor took a **2,900,597-byte** snapshot, then only
  its synthetic attachment was changed and a test-only file added. Stopping that
  exact candidate triggered automatic recovery to the previous image at 16:13:48
  UTC. All 15 checks passed, including the real conversation. The attachment was
  restored, added file removed and displaced state retained.
- A new public chat after recovery completed in **7.663 seconds**, wrote the
  correct bucket artifact and successfully discovered hosted models with the
  retained platform key.
- The recovered container was then restarted. All **16** checks passed, including
  both real conversations: the recovery snapshot did not rewind newer data.
- Upgrade and rollback both resumed across backend worker rollouts, without a
  duplicate successor. The unhealthy test image was removed from release choices.
- 56 state/deployment/link tests and 3 seed-merge tests passed. Restore was also
  exercised on the image's actual Python 3.11 runtime, not only host Python 3.12.

Failures are retained in evidence: R1's extraction API was incompatible with
Python 3.11; fixed before R3. The first API attempt hit an SDK protobuf `deepcopy`
error before any source stop; fixed in the backend. Browser testing caught a
double-serialized admin request; fixed and covered by actual HTTP-serializer
tests. The fresh-chat harness initially used a non-browser User-Agent and received
an SSE error; the actual browser contract passed. None is counted as a clean
first attempt.

## Limits and retained customer state

Complete replacement took about **7m40s** and changes the Serverless tunnel URL.
The admin binding shows the current URL. Finish active chat turns first; this is
not zero downtime or continuation of an in-memory tool process. Backend scientific
jobs remain independent durable operations.

Legacy clients lacking this filesystem must be fully exported and restored before
their first stop. Registration is metadata only, not migration. Existing customer
clients were not replaced during this release. **LynxKite is explicitly protected
and remains on its original image, both logins and shared key unchanged.**

Filesystem snapshots do not protect against loss/deletion of that filesystem.
Off-filesystem backup/retention and migration/cleanup of existing customer clients
remain explicit operational work. Container-local package edits are not durable;
keep customer scripts in the workspace and reproducible dependency definitions.

After qualification, the four stopped task-owned predecessor/fault endpoint records
were deleted. Their test data and snapshots remain on the dedicated QA filesystem.
The final QA endpoint `aiendpoint-e00b7bgf52mxk5ahhw` is stopped to release its CPU
capacity; its persistent state is retained for repeatable tests. No customer
endpoint, bucket, user, API key or customer file was deleted.
