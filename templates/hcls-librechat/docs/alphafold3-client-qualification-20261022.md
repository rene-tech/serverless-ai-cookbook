# AF3 client contract corrections — 22 October 2026

The default selects source `a7d62b1a8c0071b80b652ff28336b2981e81e006`, image
`sha256:3a3357728e0e613c5099a5fe40021dfb5f686c525a184489d46c01db11c32e9b`,
portable skills `2026.10.22.3`. It preserves all 56 layers of the previous
BioEmu2-refined default `6b367cc6…`, its runtime configuration and additional
ClawBio skills. Exact OCI-layer readback verified installed bytes for the study
validator, structure/confidence helpers, typed comparison service/schema and
current canonical bundle. All 100 managed bundle files passed the build gate.

The corrections are general customer behavior:

- Reject JSON metadata promised as PDB/mmCIF coordinates before study admission;
  names do not convert bytes. Select the structure phase's `prediction.structure`
  for coordinate delivery and retain the manifest as JSON provenance.
- Recognize native AF3 summary-confidence artifacts. Require one canonical
  coordinate and one summary in the same immutable manifest; verify both
  artifacts' hashes/sizes and keep null monomer ipTM unavailable. Do not invent
  a seed/sample association or treat native confidence as reference accuracy.
- Expose `confidence_result_file` and `request_file` through
  `workbench_compare_structures`, preserving independent input hashes. Use
  `prediction_file` for coordinates/a downloaded manifest, and `result_file`
  for inline coordinate-bearing result JSON. No new inference is needed.
- Install the exact current canonical portable bundle while preserving the
  separate ClawBio tree and current BioEmu2 refinement.

Scoped offline cohorts passed: 79 study/composer/bundle/packaging tests;
53 structure/confidence and 66 preparation/manifest tests (five explicit
private-fixture skips); 32 Node analysis/service tests; final bundle/packaging
subset 32 tests. Counts overlap and are not one aggregate suite.

## Actual workbench acceptance

Only the existing internal QA workbench was patched for this investigation.
Its endpoint specification, credentials, storage, conversations, native jobs,
API and study-supervisor process identities were preserved. File backups and
exact hash readbacks are retained. The provider image still identifies its
older base; the explicit runtime overlay, not that image field, identifies the
QA code. Other retained customer instances were not changed by this task.

The ordinary agent loaded the deployed skills and submitted a real AF3
ubiquitin workflow once. Prediction/comparison/report completed independently
of chat. Its original JSON-as-CIF promise was preserved and then rejected by
the new validator with no model admission. Corrected analysis-only delivery
reused the same prediction. The real installed helper returned CA RMSD
1.4823218648873426 Å versus 1UBQ, pTM/ranking 0.86, and null monomer ipTM.
The 602-atom interactive structure was visually checked after streaming and
saved-chat reopening. Native coordinates remained unchanged.

A fresh ordinary QA chat loaded the updated skill and made exactly one typed
comparison call with the new confidence/request fields. It completed with the
same metrics, canonical manifest association and original input SHA-256, with
`inference_submitted=false`. The existing LibreChat user's actual MCP
connection independently passed the same transport check.

An in-place reconnect initially treated this user-scoped MCP as an application
connection, temporarily removing its tools. It was restored through the
existing manager using the original QA user/config; no visibility/authorization
policy was relaxed. Search excludes already-loaded tools, so an empty tool
search was not accepted as proof of model or helper availability. A missing
declared bundle test file was reconciled and all 100 installed entries verified.
Original activation/search errors remain in private evidence.

## Boundaries and retained failures

This is a scoped client-fix qualification, not all-model/workbench readiness.
The original workflow did not automatically append the final narrative/view;
follow-up turns were needed. A long diagnostic chat later failed during model
compaction with provider HTTP 500; the original error is retained and remains
unresolved. The fresh chat passed; neither original failure is erased by it.
No chat model, provider, customer limit or fallback policy was changed.

Private operator evidence, containing the actual QA identities/conversations,
is under `/home/tux/secure-handoff/model-testing-20261022/alphafold3/`.
The private application repository contains the full six-run scientific,
REST/MCP, native H100, startup, regional/deadline and cleanup review. No private
scientific application code or customer evidence is published in this cookbook.
