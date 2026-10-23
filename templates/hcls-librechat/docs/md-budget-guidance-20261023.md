# MD budget guidance: source-only correction

The shared native-MD reference incorrectly described a universal 4 GiB workspace
default and six-hour wall budget. Current Apps have different schema defaults
and bounds; OpenMM permits an omitted/null output cap. Fresh schema discovery
does not correct stale prose already loaded by an agent.

Skill bundle `2026.10.23.3` updates only the shared native-MD budget guidance and
the corresponding GROMACS MPI explanation. It distinguishes omission/defaults
from maximum bounds, explicit request budgets from bucket/scratch capacity,
and submission budgets from retrieval of an already completed operation. It
preserves scientific output cadence and prohibits resubmission merely to fetch
existing results. Other skills and helper code are unchanged.

Validation: bundle hashes verified and all 26 existing bundle/contract tests
passed. This is an offline documentation correction, not a live client or image
release. The default image and retained clients still contain their existing
bundle. No running chat, process, MCP connection or client file was changed.
After the active recovery window is explicitly closed, package the correction
into the next reviewed image/client update and verify the actual loaded
reference text, preserving user customizations and connection scope.

Repeated recovery-tool searches and time before the first recovery invocation
are separate observations. This documentation change does not establish their
cause or qualify recovery performance on large inputs.
