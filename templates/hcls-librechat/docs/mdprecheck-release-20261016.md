# Optional MD precheck client release — 16 October 2026

The default workbench image adds original customer instructions for the hosted
`mdprecheck` App. It does not contain or publish the private checker source.

## Exact image and scope

- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:62aec6f144ddb07eb015d692e4c539ff0813079dafa0a3fc4fafbb0b39e18e7d`.
- Base: qualified fleet image `sha256:5595cfb290b00b78390d204300eca559dd9ef297784f63a0efc8eb19b9f3a556`.
- Skills bundle: `2026.10.16.3`; 37 canonical skills, 85 installed with the
  pinned ClawBio selection, 88 verified core resources/files.
- Changes: `md-precheck`, optional consent/reuse guidance in `gromacs`, and
  Molecular dynamics categorization in the workbench catalog.
- The installed runner owns upload, exact lookup, idempotent admission/retry,
  operation observation and hash-verified HTML/JSON delivery. It rejects a report
  for different input bytes/options/runtime instead of letting the agent select
  a plausible older result. Repeating its command resumes the same receipt.
- Existing branded UI, state supervisor, OpenFF runtime, bucket and artifact
  helpers, chat provider, credentials and other skills are preserved.

For a prepared new GROMACS workload, the agent offers a check; a refusal does
not block simulation. Exact content/options and the checker runtime identify
reusable prior checks. Running a simulation, silently repairing scientific
inputs or assuming a warning is a clean pass is not authorized by a precheck.

## Using it

Ask: “Check the prepared GROMACS inputs in this bundle with mdprecheck and give
me the full reports. Do not start the production simulation.” Upload the source
bundle first or refer to its workspace path. Static checks are the default;
optional short probes run on CPU. Users need `mdprecheck` in their model grants.

The canonical instructions and REST contract are
[`md-precheck`](../../../skills/scientific-ai/md-precheck/SKILL.md) and its
[`API reference`](../../../skills/scientific-ai/md-precheck/references/api.md).
The App returns compact findings and full HTML/JSON report artifacts. The
check's scientific verdict (`warn` or `fail`) differs from execution failure.

## Qualification and existing workspaces

The [exact release receipt](evidence/mdprecheck-release-20261016.json) records
the real LibreChat skill loader, all 88 file hashes, unchanged inherited base
layers/state entrypoint, seven installed-runner tests and workspace checks.
The internal QA browser confirmed the optional offer/refusal, then completed a
real static check with the exact requested production/2 ns intent. It reported
the file's actual 10 ps mismatch without changing the input or starting MD.
A repeat request reused the same operation; authenticated browser downloads of
both reports matched their artifact and bucket hashes. Do not infer scientific
accuracy on every system or unlimited capacity from these tests.

Earlier candidate chat failures are retained: missing native schema discovery,
busy admission and substitution of a mismatched prior report. The final helper
fixes that delivery path. Intermediate chat narration still changed language
despite English being requested; the final answer was English. The inherited
queued-turns UI route logged a 404 without preventing this workflow. Neither
unrelated limitation is presented as fixed.

Existing instances are updated using a checked, additive file overlay and a
container-only restart. The operator verifies idle chats and unchanged core
files, retains rollback files on `/data/workbench-hotfixes`, verifies the actual
skill loader, and compares user/login/history state before and after. Endpoint
URLs, mounted buckets and key bindings remain unchanged.

An overlay is not an update to the provider's immutable base image: a later VM
recreation must use this default image or reapply the retained patch. Preserve
the managed persistent state and existing workspace ownership when replacing
an instance. This release does not authorize deleting customer workspaces.
