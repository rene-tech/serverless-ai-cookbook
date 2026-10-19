# Inline report delivery — 19 October 2026

The exact reported conversation contained `demos?tab=workspace&...&file=...report.html`
links. The helper returned `/demos?...`, but the assistant omitted the leading
slash. The Markdown renderer only recognized the latter and silently produced
an ordinary link. Prior tests covered helper URLs and reload/visibility, not
the actual generated relative links. A prompt-only change cannot fix that gap.

The existing owned-workspace URL normalizer now accepts that exact rootless
route and normalizes it before Markdown rendering. External URLs, traversal,
extra query arguments and other routes remain rejected. No new service, fallback
endpoint, or legacy protocol was introduced. Existing saved messages render
without rewriting their contents or rerunning scientific work.

The scientist-facing md-precheck skill now requires inline delivery, preserving
the returned URL exactly. Downloads are secondary. A link-only result is a
viewer failure, not successful report delivery. The private operator skill also
requires actual generated-link, live-stream and saved-message browser tests.

## Evidence and release

See [the release receipt](evidence/inline-reports-20261019.json) for immutable
image/source identity. All 367 UI files in the default image match the patched
clients. The final bundle includes its updated manifest and verified hash lock.

- The real QA agent loaded the updated skill and displayed an existing verified
  report inline as its response arrived. A second response reproduced the exact
  rootless-link format. Browser navigation timing stayed unchanged for both;
  neither required reload, a viewer tool, download or new scientific operation.
- Reopening the saved QA conversation retained the embedded reports.
- The user's unchanged saved 9 ns, 11 ns and 12 ns reports rendered inline in
  the reported conversation. Their real report text and pixels were inspected.
- All five retained workbenches received a reversible static asset/skill patch.
  API/worker/supervisor process identities and scientific
  executor hashes stayed unchanged. Loaded skill bodies were verified in the
  running APIs, rather than assuming copied files changed the memory cache.
- React tests (18), URL/highlighting tests (10) and installed checker-runner
  tests (9) passed. The build retained a pre-existing Tailwind ambiguous-class
  warning; no runtime rendering failure was observed in the exercised paths.

Private screenshots, chat evidence and rollback receipts are retained in the
operator's dated inline-report handoff. Customer payloads are not in this repo.
The first QA activation attempt discovered that SKILL.md is represented by the
registry body, not a separate file record; the activation was corrected and
verified before rollout. No process restart or customer scientific call occurred.

Already open browser tabs still run the old JavaScript: use the existing update
notice or one normal reload to install the new UI. Do not force a reload that
would discard an unsent draft. This is a one-time release update, not a
per-report workaround. Future deployments use the pinned default directly.

For rollback, restore the exact per-client saved index/skill and loaded skill
body; retain additive hashed assets for existing tabs. The previous default
digest is the receipt's `base_manifest`. This release qualifies report delivery,
not every scientific model or a provider instance replacement.
