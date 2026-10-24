# Combined native MD HTML

The existing `report` analysis method now also publishes `report.html` when
every section uses `format: native-md`. It uses the same verified typed inputs
and HTML renderer as individual native MD reports. Missing observations remain
unknown; sampled temperature, cumulative clock, segment time and timing scopes
keep their original labels and source links.

Select the combined HTML with `{ "step": "aggregate", "file": "report.html" }`.
Existing `native-timing-report.json` paths can feed a single assembly phase;
no repeat native execution, recovery download or per-engine analysis is needed.
Markdown, customer summary JSON, provenance and exact input copies remain
available. The completion manifest hashes the new HTML alongside those files.
Generic or mixed-format reports retain their existing output contract.

This is a forward change: use a new output directory for a new assembly study.
Do not overwrite completed reports or change their immutable study bindings.
CPU qualification covers the installed Python interpreter, source verification,
one-phase publication, preserved old outputs and escaped/linked HTML. Local
browser checks cover desktop/mobile readability. Existing-client activation and
actual model-loaded Skill freshness require separate qualification; source-file
hashes or execution-MCP reconnects alone do not prove the builtin Skill body.
