# Deferred discovery and native operation guidance — source candidate

This is an **unreleased source candidate**, separate from the frozen API116/AppR42
QA cohort. It does not change a release pointer, base image, customer instance,
agent defaults, provider budget, credentials or scientific request.

## Proven installed state

The existing QA image `16815c8cf0d0b8d3c343c56f90559bca1fea26d8c93e7294d544a826ec636af9`
received only the two discovery-module patches from source `5701105` after a
full backup. One browser ADMET invocation `op-e74c396a38794261` completed with
verified result bytes and ordinary owner/peer checks. The chat reported queued;
GET-only qualification completed it separately. Autonomous polling was not
tested. The original agent was restored, other agents unchanged.

Actual runtime tests proved that the trusted host budget notice must remain in
provider history but be transparent to both deferred-discovery helpers. Ordinary
human/steer messages and untrusted lookalikes must still end the discovery view.

## Proposed source changes

- The portable gateway skill distinguishes native `op-*` IDs from original UUID
  IDs. Native async serving uses `get_scientific_status` / `get_scientific_result`;
  UUID-only aliases and current workbench wrappers must not receive `op-*`.
  Same-owner reads and exact IDs are retained; no new lifecycle client or retry.
- Full `Dockerfile` retains its existing `patch-server.mjs` integration and adds
  an installed CPU-only gate. The additive recipe uses a discovery-only patch
  entrypoint, not a replay of all server/configuration patches.
- The additive final stage copies both patched CJS/ESM SDK files and their
  trusted-notice dependency, then runs the actual installed ToolNode/schema
  activation tests. Existing final RUN mounts avoid extra final image layers.
  Unknown or already-patched SDK seams fail closed rather than silently skip.
- Bundle `2026.10.15.1` carries the corrected guidance. Default release pointer
  `workspace-20261008-r3` / `752a860b…0e0c1b` is unchanged.

The pinned additive base remains `16b34a37…cdc65`; no new immutable image has
passed all build gates. The installed gate must prove that its existing host-notice
producer provides the required provenance. A missing producer/dependency is a
build blocker, not permission to classify arbitrary human messages as trusted.
Root must review any such concrete base mismatch before a broader patch.

## Validation and handoff

Local results: 35 Node tests passed, one explicit installed-SDK prerequisite
skip; 26 portable-skill tests passed; bundle inventory verified. Re-locking also
corrects the already-committed scientific-batch skill's stale inventory entry
(`7f8a8908…` to actual `06baf39e…`); that skill's bytes are unchanged.

Run from repository root:

```sh
node --test templates/hcls-librechat/test-scientific-tool-search-patch.cjs templates/hcls-librechat/test-scientific-study-admission.cjs templates/hcls-librechat/test-deferred-discovery-packaging.cjs templates/hcls-librechat/test-deferred-discovery-boundary.cjs
python3 -m pytest -q skills/scientific-ai/tests/test_bundle.py
python3 skills/scientific-ai/bundle.py verify
```

Without the exact SDK, the boundary suite reports its explicit prerequisite
skip. Both image recipes set `SCIENTIFIC_DISCOVERY_INSTALLED=1` and the exact
Graph path, making missing SDKs/host provenance fail the image build. These gates
make no provider, MCP, inference or network calls. Root alone integrates/builds;
verify immutable image, final installed module hashes and bounded client behavior
before any promotion. A same-container hotpatch is not an immutable release.

## Pinned-base ESM gate correction

The first immutable build from `944c8c1` failed its final installed gate: ten
CJS cases passed, but the ESM case returned no discoveries. The full failure log
is retained separately; its SHA-256 is
`c94b51a4233502bb073fbb4f7e1336a1c8821782a6155e4124de2ffb067b8fc2`.

This was a test-fixture class mismatch, not a failed production transformation.
The exact base's `@librechat/agents` 3.8.0 checks `instanceof ToolMessage` and
`instanceof AIMessageChunk`. Its CJS and ESM LangChain exports have different
constructors; the old gate incorrectly gave CJS messages to the ESM helper.
The corrected ESM fixture uses the installed package's `import` export and its
own ToolSearch, ToolNode, injected-message converter and AgentContext. It proves
cross-format rejection remains strict and repeats the provenance, unrelated
tool-call, ordinary-user and untrusted-message negatives for ESM.

A disposable CPU container over the exact `16b34a37…cdc65` base, with networking
disabled and no provider credentials, passed **20 installed tests, zero skips**.
Both ToolNode paths activate the same deferred schema without changing provider
history or the host budget. The production patch, recipes and provenance checks
are unchanged; resulting module hashes remain:

- CJS: `65ab6044c60cab0fb410a2f21d087698853c30c002446fd22ce0985cd2275eb2`
- ESM: `a3274c14965af5abe657447b1d57827e5c6b2935a9ad880a5f27571d85b3a38e`

This is exact-base CPU evidence, not a completed immutable build or new client
qualification. Root must rebuild from the integrated correction and retain the
same final installed gate before considering any release.
