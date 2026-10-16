# GROMACS optional precheck offer correction — 16 October 2026

This corrects the missed offer on a prepared, saved study. The agent had loaded
the right GROMACS skill, but the shared execute-authorized-work instruction
overrode the optional conversation choice. The shared instructions now contain
an explicit GROMACS exception: offer mdprecheck and end the turn before
admitting a new unchecked simulation, including a changed-duration prepared
study. A bare request to simulate is neither consent nor refusal. Explicit
refusal still permits MD; an unchanged continuation needs no repeated offer.

## Exact release

- Code: `515bc9962ef616c9d0b63df21a588c244a6a201c`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:precheck-offer-20261016-r4`.
- Digest: `sha256:3ba84351d86a1160407faef7dcd18e0985253e36a6d3501bb556b6575c31159e`.
- Skills `2026.10.16.4`, 37 canonical skills, 88 verified files.
- Inherited fleet base: `sha256:5595cfb290b00b78390d204300eca559dd9ef297784f63a0efc8eb19b9f3a556`.

The overlay includes shared instructions, not just skills. The private checker
source, provider settings, persisted user/chat data and credentials are unchanged.
The default pointer applies to future clients. System QA and the reporting
operator's existing client were patched in place without restart; other managed
clients retain the preceding overlay until their next controlled update.

## Narrow acceptance evidence

Two fresh QA conversations asked for 10 ns and 20 ns against a prepared
1,000 ns public 1UBQ fixture with a saved study. Both offered the check and
stopped before MD admission. A consented static check completed as
`op-89652243a4373191`, reported the exact 10 ns versus 1,000 ns mismatch,
delivered HTML/JSON reports, and did not start MD. The downloaded report hashes
match the runner's verified delivery receipt:

- HTML: `f0b9ad873fa308d2477be788a48d68a95c7d1c48a1bbfb42de129689f5eb91a3`.
- JSON: `190f8973b5146dfb5280ed4c984c167441a37b3d07f7d5fea2b0b57ff32815f0`.

Checks passed: 4 shared-instruction tests, 12 execution-guidance tests,
26 skill contract tests, 7 installed runner tests, and bundle verification.
The reported customer's already-submitted study was not canceled or resubmitted.
Its requested duration was correctly converted to 10 ns; the defect was the
missing conversation choice, not an accidental 1,000 ns submission.

This is not a claim that every agent turn is reliable. Retained limitations:
the consented QA turn first tried invalid `--wait-seconds 0`, then recovered
before admission; another offer included a hypothetical command with unsupported
flags, which was not executed. An earlier fixture setup race is excluded from
the clean offer evidence. The deterministic runner still owns idempotency,
exact report identity and delivery; a prose offer is not execution evidence.

Private chat/patch receipts are retained under the operator's secure handoff
directory, not in this public repository. On-client rollback files are under
`/data/workbench-hotfixes/precheck-offer-20261016-r4`. Provider base image is
unchanged for patched instances; VM recreation must select this pinned default
or reapply the retained overlay. See the [previous release](mdprecheck-release-20261016.md)
for the unchanged backend, report delivery and optional-check contracts.
