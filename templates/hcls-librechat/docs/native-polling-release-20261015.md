# Deferred discovery and native polling — 15 October 2026

This default-image selection carries the trusted-host-notice discovery fix and
the native `op-*` polling guidance into future installations. It changes no
running customer endpoint, QA endpoint, credential, provider/model default or
scientific request. Explicit deployment image overrides remain supported.

## Immutable identity

- Source: `65b88e24ca1ed20d73b6a6c7eef0ef8366e6d21e`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:workspace-s2qa-20261015-r2`.
- Manifest: `sha256:bd339b8357a381e3c453d5a5132fdc89fb514ff4b9e4cd67dc3ac2c4f1f5ca4d`.
- Config: `sha256:abf7424b90518ebe038c4c8553bd94f9fcc00f84826d478c8063f925b694abc2`.
- Skills: `2026.10.15.1`; 36 core / 84 installed including retained ClawBio.
- The 122 layer descriptors and manifest/config bytes match independent registry
  readback; the 113 inherited parent diffIDs and base configuration are preserved.

Both full and additive recipes enforce actual installed CJS/ESM discovery
gates. The additive path patches only the reviewed discovery seam, preserves
base configuration and does not rerun the broad server patch. Native serving
`op-*` IDs use `get_scientific_status` / `get_scientific_result`; legacy UUID
aliases remain separate. Human messages and untrusted lookalikes still stop
discovery; only the existing trusted host notice is transparent.

## What passed

The exact immutable image, executed locally as its unchanged configured UID0
without network, passed 20 installed SDK gates with zero skips, the actual
84-skill loader and 85 core-file SHA checks. Retained ClawBio content was
compared to the pinned base. Final image build also passed the installed
workspace UI checks, OpenFF runtime and backed dense/CSR/CSC single-cell gates.

A fresh idle internal-QA backup was restored into a separate local MongoDB.
All document/index hashes matched before normal image startup. Existing login,
history and message routes returned 200; 22 conversations, 44 messages, one saved
encrypted credential and the original user/password hash survived. Both local
containers were stopped after the check, with no ports/network/provider calls.
There were no uploaded-file fixtures in this backup; this is not upload parity.

Actual browser follow-up used the retained QA image with the candidate's exact
SDK/guidance bytes, not a managed endpoint replacement. It performed deferred
discovery → status → result for the same completed native operation
`op-e74c396a38794261`; no new scientific work was submitted. The final answer
correctly reported MW 46.069 and AMES 0.11980573832988739 as model predictions,
not human-safety findings, and the 866-byte artifact SHA
`c69fded8a3a4eccaf722015d3d04d3bcacbfa52bd72bca731f5ce4cbb35505d8`.
The original QA agent was restored afterward.

The reviewed installed guidance was explicitly added to the temporary QA agent
instructions; autonomous skill loading was **not** tested. The QA provider/model
was Nebius Token Factory / `zai-org/GLM-5.3-Flash`; this does not change the
release's Kimi-K3 default. Actual provider count/cost were unavailable; the
bounded upper limits were 8 calls and $1.294336, not measured usage.

## Retained failures and limits

The first build's ESM test mixed CJS/ESM message classes; its corrected installed
gate passed without changing the production provenance boundary. The r2
BuildKit upload then timed out after 3600s while its exact OpenFF layer advanced
at roughly 0.37 MB/s. Authentication remained valid. After the old writer stopped,
root authorized a CAS-only digest-preserving publication; host skopeo completed
in about 50s, and independent readback passed at 12:13:51.887 UTC. No new build or
recompression occurred. A registry rate limit or precise network cause was not
proven. Both failures remain in their original evidence.

Configured UID0 is the qualified runtime identity. UID1000 cannot traverse some
copied public skill directories (0700); normalization is a separate portability
follow-up, not performed in this digest. This release does not establish broad
customer readiness, concurrent capacity, every advertised workflow, an actual
managed replacement, or a full immutable-image browser cohort. Historical
workspace/science receipts keep their own identities and limitations.

## Promotion, rollback and evidence

`scripts/release-image.sh` and the README's generated immutable launch link
select this digest. Existing instances do not auto-upgrade. Rollback for future
installations restores the prior tag `workspace-20261008-r3`, digest
`sha256:752a860b307e85e69b8ad3b5983ac158f78ad5121bb8dbf4f5ec6e89a30e0c1b`
and skills version `2026.10.07.5`; it must not roll back a running client's DB.

Sanitized hash-linked receipt: [evidence/native-polling-release-20261015.json](evidence/native-polling-release-20261015.json).
Private payloads, credentials, backup archives and raw logs are excluded from
Git. Root owns final integration/default promotion and any later deployment.

Promotion checks: 26 focused pointer/deployment/link tests passed; shell syntax
and diff checks passed. The broader template run had 50 passes and one inherited
`test_product_does_not_use_tenant_branding` failure from an unchanged separate
customer-registration helper. The same failure reproduced against the clean
65b88e24 source archive; it was not hidden or repaired in this pointer change.
