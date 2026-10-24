# Artifact openers attached to prose

A saved assistant response attached `:::artifact{...}` directly to the preceding
sentence. Markdown therefore rendered the directive as text and its React body
as a code block. The existing artifact runtime already supports React and
Recharts; the observed failure occurred before that runtime was invoked.

`ScientificArtifactMarkdown.ts` inserts the missing block boundary before a
complete, top-level artifact opener attached to prose. It runs before Markdown
block splitting so saved responses and streamed content use the same artifact
indices and existing sandbox. It leaves artifact bodies, saved messages, valid
directives, fenced/inline code and quoted or indented examples unchanged.
There is no chart-specific data conversion, dependency substitution or new
execution path.

`patch-report-preview.mjs` installs this normalization at the existing Markdown
splitter seam. The default release recipe includes the patch. The separate
`Dockerfile.artifact-rendering` builds a presentation-only overlay on the exact
reporting client's existing base; it does not change default release pointers.

## Verification

- Eighteen focused tests exercise preceding prose, streamed headers and bodies,
  preserved literal examples and stable later code/artifact indices. The exact
  overlay builds successfully; applying its source patch twice is idempotent.
- A scoped no-restart static asset overlay retained all old hashed files and
  atomically replaced the index only after all new assets were present. The
  existing fresh-asset middleware served the new content-hashed entry on normal
  reload; no cache bypass, socket interruption or forced reload was used.
- The original saved artifact opened through its normal chat card and displayed
  two charts with 24 bars. Both charts' hover values matched the retained source.
  Normal reload and reopen reproduced the chart pixels without Reset.
- The complete original conversation and all eight messages were byte-equivalent
  as parsed database documents. Captured user, token, plugin and configuration
  collection hashes, API and supervisor PID/start identities were unchanged.
  No message, scientific file, tool evidence, model setting or skill was edited.

This is a rendering correction. It does not validate the historical chart's
scientific assumptions or replace it with later analysis. The original React
chart retains its own responsive layout and the existing Recharts development
deprecation warnings. No runtime exception prevented chart rendering.

Private build logs, hashes, preservation checks and browser screenshots are in
the operator's dated visualization handoff. Roll back by restoring its saved
`index-before.html`; retain additive hashed assets while old/new tabs exist.
The live overlay is not a provider image redeployment and does not update other
clients. An already open tab needs one normal reload to load the new renderer.
