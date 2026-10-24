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
