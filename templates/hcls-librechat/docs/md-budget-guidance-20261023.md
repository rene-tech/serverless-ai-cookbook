# MD budget guidance

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
passed. The initially source-only correction is now packaged in the
[sparse-coordinate viewer release](sparse-preview-20261023.md), whose exact
default image contains bundle `2026.10.23.3`. Six maintained clients received
these two reference files with the viewer correction, after idle and exact-file
checks. Their running registries expose the verified reference contents; domain
bodies, customizations, connection scope and processes were preserved. These
are scoped overlays, not full-bundle replacements. Existing studies and their
scientific request budgets were not changed.

Repeated recovery-tool searches and time before the first recovery invocation
are separate observations. This documentation change does not establish their
cause or qualify recovery performance on large inputs.
