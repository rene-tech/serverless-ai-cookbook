# Observer recovery in future images — 17 October 2026

Published default: `lc:future-jobs-20261017-r1`, manifest
`sha256:f125725950ae56927b630e4289bda2370491f52993e4a7c977bca8207e01cbd6`.
Registry: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc`.
Build source: `f43adea48b72c5f1d722b01461d591d8556a315f`.
Image config: `sha256:c5d05937e20cd23228d1de685941ffdf1bf2c6caf3dde145d9295ea565d3494b`.

## Scope

This is an **image/build release only**. The owner explicitly requested keeping
every existing endpoint unchanged. No endpoint was created, stopped, restarted,
replaced or patched; no URL, state volume, credential, bucket or running
scientific job was changed. Existing in-place patches still depend on their
current runtime: this release does not change those endpoints' old provider
image specifications. New deployments use the fixed immutable image directly.

The parent is the qualified observer release
`sha256:8b7a4b6655276bb730b350d53a6b44e827506287ffe45d544381c4d43f6e1386`.
The three observer/transport source files are byte-identical to that parent;
the UI, skills, scientific executors and state supervisor are inherited intact.
Its [scientific acceptance](observer-recovery-20261017.md) retains its own date,
exact runtime and scope. This packaging check is not a new model benchmark or
all-workflow production qualification.

## Build and deployment changes

- `Dockerfile.default-release` now extends the current fixed workbench instead
  of rebuilding an old ancestor with an incomplete subset of transport files.
  It installs all three current observer/transport modules explicitly.
- The full source, additive default and observer recipes run
  `scripts/verify-observer-recovery.py` against **installed** files. The gate
  checks exact source hashes, nested disconnect handling, fair queue selection
  and preservation of permanent errors. Missing or stale files fail the build.
- `scripts/verify-customer-state-image.py` also verifies these three installed
  modules alongside persistent startup, catalog and compiled browser branding.
- `deploy.sh`, `deploy-link.py` and the README console button select the same
  manifest digest. An explicit operator image override remains possible.

The default recipe is a scoped additive build, not a promise that arbitrary
source changes are automatically included. For another feature, update its
owned recipe and qualification before promotion. Historical recipes are not
alternative current defaults.

```sh
docker buildx build --load --platform linux/amd64 --network none \
  -f templates/hcls-librechat/Dockerfile.default-release \
  --build-arg HCLS_IMAGE_REVISION=YOUR_COMMIT -t YOUR_CANDIDATE .
python3 templates/hcls-librechat/scripts/verify-customer-state-image.py YOUR_CANDIDATE
python3 templates/hcls-librechat/scripts/qualification/qualify_operation_polling_image.py \
  --image YOUR_CANDIDATE --output /private/new-qualification-directory
```

## Evidence and limitations

Two consecutive fresh-container cohorts passed **139 tests each**, using the
image's installed Python/MCP/HTTP clients and all three installed recovery
modules. No network, GPU, customer mount or credential was provided. Tests cover
known-operation recovery, later queue progress, no duplicate submission,
bounded repeated outages, exact result bytes and identity/cancellation failures.
The image passed eleven installed-file checks and compiled browser checks.
The gate rejected the preceding pre-fix catalog image as intended.

The first expanded cohort exposed an obsolete test that expected a transient
download disconnect to escape instead of recover. The assertion now requires
automatic recovery of the same operation and exact artifact bytes; an additional
test proves persistent outages exhaust the bounded read budget and remain
resumable without inference. No production runtime change was needed.

Two unrelated broader-suite failures also reproduce on unchanged parent main:
`tests.py::test_saved_agents_receive_gateway_instructions_and_skills` expects
older specialized-agent instruction text, and
`tests.py::test_product_does_not_use_tenant_branding` scans a historical patch
message. They were not modified or represented as passing. The focused image,
deployment and observer gates pass; the entire historical suite is not green.

See the [machine-readable receipt](evidence/future-image-recovery-20261017.json).
No provider restart or live endpoint/GPU test was performed in this image-only
task. Rollback future deployment selection to the parent digest if needed;
do not mutate existing customer endpoints as part of changing that default.
