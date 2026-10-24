# Report previews in structured messages

An authenticated HTML report linked from a Markdown table now keeps its original
table link and renders one interactive preview immediately after that table.
The preview uses the conversation width instead of the table cell width.
Ordinary paragraph and list previews retain their positions. Report bytes,
download links, sandbox permissions and authenticated delivery remain unchanged.
This applies when messages stream and when unchanged saved messages reopen.

A conventional `report.json` companion is optional. Missing, unavailable or
unrecognized metadata does not turn successfully loaded HTML into a failed
preview. Recognized MD precheck metadata still supplies its summary and JSON
download; a JSON download is advertised only after that artifact was loaded and
recognized. Failure to load the requested HTML itself remains visible.

The retained regression covers link preservation, repeated report paths,
idempotent rendering and ordinary list placement. A local browser check uses
the actual patched Markdown anchor, Markdown parser and report component with
synthetic report delivery: an 880-pixel conversation produced an 854-pixel
standalone preview and an unchanged 832-pixel list preview. Reopening preserved
both. At a 390-pixel viewport the previews measured 332 and 310 pixels without
page overflow; plotted pixels were inspected at both sizes.

The additive release recipe preserves the qualified connection/catalog image,
all inherited scientific runtimes and extra skills, with one filesystem layer.
It rebuilds the UI because the renderer changed. This source/build qualification
does not establish activation on any running workbench.

For an authorized retained-client activation, install all new immutable assets
before switching index.html and retain old assets for existing tabs. The existing
asset middleware supports ordinary reload without an API restart. Changed
Python executor modules require a fresh idle guard and replacement of only the
existing supervisor-owned `--worker` child; the supervisor already respawns it.
Keep the supervisor and API process identities. Reconnect the existing execution
MCP child in its original application/user scope. Never copy executor bytes while
a frozen study or command is active, create a second worker owner, or claim that
file replacement reloads imported modules. The actual retained-client loaded
skills, registered workflow and inline/reopened report acceptance remain a
separately coordinated gate.
