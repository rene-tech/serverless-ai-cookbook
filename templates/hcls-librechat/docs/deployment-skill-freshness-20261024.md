# Deployment skill body freshness

LibreChat initializes its deployment skill registry in the API process. Builtin
`Skill` and manual skill resolution prefer that registry over MongoDB. Copying a
new `SKILL.md` or reconnecting an execution MCP process does not refresh an old
API registry. Verify the complete body in an actual model-invoked Skill result;
a filesystem checksum or an isolated loader process is insufficient activation
evidence.

The image build's existing `patch-skill-result.mjs` now refreshes only the
selected registered file body when returning skill details. Manual, model and
always-apply resolution use the same reader. Registration IDs, frontmatter,
ACL filtering, file references and user-created database skills stay owned by
the existing resolver. No polling, new import service or full-catalog reload is
introduced. Unreadable/invalid bodies and changed identity/frontmatter produce
an explicit error instead of silently returning stale guidance; metadata edits
still require normal definition loading. Existing conversation tool results
remain historical and are not rewritten.

Run `scripts/test-skill-body-freshness.cjs` with Node inside the exact candidate
image, with no network or GPU. It initializes the real loader once, atomically
replaces a synthetic body, and verifies fresh detail/automatic resolution,
unchanged metadata/IDs, denied ACLs, preserved custom database content, and
rejection of changed or missing sources. The unpatched image must fail the
fresh-body assertion.

This source change cannot refresh an API process that already loaded the old
implementation. That process has no installed deployment-skill reload route.
Do not claim an MCP reconnect activates it, use debugger injection, or kill the
API child: the current supervisor treats API termination as container exit and
also stops its study worker. Activation requires a separately reviewed supported
client lifecycle with state preservation, or a previously installed supported
in-process lifecycle hook. File-only maintenance is insufficient.
