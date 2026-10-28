# Consolidated default workbench fixes

This release builds on the qualified sparse-preview image `be5adc6c`, preserving
its scientific runtimes, GPU-free preparation tooling and ClawBio extension.
It packages the fixes that had already been applied selectively to retained
clients, so newly launched instances receive them without manual overlays:

- Inline HTML/artifact Markdown boundaries, including delimiters adjacent to prose.
- Sparse and large-mmCIF previews, nonfatal optional previews and complete native
  MD reports. The report helper and CLI alias both use the qualified `1981d4bb`
  source, which distinguishes final observations, averages, integration and native
  command wall time rather than inventing unavailable measurements.
- Kimi K3's advertised 1,024,000-token context and generic deferred MCP schemas,
  preserving explicit tool selections and the compact always-available tools.
- The current scientific skill bundle, including evidence-grounded cancer,
  immunology and CAR-T research, OpenMM, BioEmu2 and updated MD budget guidance.
- Optional Dropbox OAuth support and the corrected cBioPortal research plugin.
  The latter is packaged at `/opt/hcls-librechat/plugins/cbioportal-research` for
  explicit activation using the existing plugin loader. Neither connection is
  enabled for other customers by installing this image; no credentials or
  customer conversations are embedded.

For all six MD engines, omitted/null `max_output_bytes` requests have no explicit
aggregate output cap; explicit budgets remain binding. Scratch capacity,
per-file/manifest limits and actual bucket capacity still apply. Explicit resume
retains the original parameters and cumulative elapsed budget; it does not renew
spent wall time. These are the deployed R10 contracts, not a multiweek endurance
claim or permission to change native output cadence.

The default-image pointer applies to new launches. Existing instances retain
their state and independently recorded overlays; a pointer update does not
restart, replace or declare them byte-identical to this release. Research
connectors still need their own authorized account and selection.

The release receipt records the immutable image, source, actual installed-file
checks, inherited layers/runtime configuration, loader/UI verification and
remaining qualification scope. Existing scientific execution and live-client
receipts are reused at their exact scope; no model job is replayed just to
publish a client image.

## Published image and checks

- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:client-fixes-20261024-c6d0950`.
- Digest: `sha256:6eab1b90c79b8e9144b7a9e7b595495ea046ce3fe49a826c2695d37e2c7e6d7b`.
- Source: `c6d095056893dc8bffbd48ec94bf4f63a32a66db`; bundle `2026.10.24.4`.
- [Exact image receipt](evidence/client-fixes-20261024.json).

All 112 inherited layers preserve their compressed digests/sizes and uncompressed
identities; the final image has 116 layers. OCI descriptors replace Docker gzip
descriptors without changing those bytes. Runtime configuration changes only
the context default from 131,072 to 1,024,000 tokens. All 123 canonical bundle
files and 22 explicitly compared source/runtime files match; both report entry
points match the qualified helper. The real installed loader reads 94 skills and
115 resources. Source checks pass 92 tests, tool loading six, and the built
inline renderer 18. Existing scoped live-client evidence remains distinct from
a new whole-image end-to-end qualification; no customer client or scientific job
was restarted/replayed to publish this default.
