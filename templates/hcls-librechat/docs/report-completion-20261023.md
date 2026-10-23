# Retained-result report completion

A real analysis-only chat produced timing files and an interactive structure
preview when the scientist requested a complete HTML report. The OpenMM recipe
had called those partial outputs “the report.” The generated study title also
mistyped the operation ID even though recovery used the correct identity.

`native_md_preview.py` now emits `native-md-report.html`, combining the existing
structure viewer with a scientific summary. Identity comes directly from the
verified receipt. Measurements use the hash-bound native result and, for the
documented OpenMM state output, the verified CSV's last temperature observation
with its own step/time. The summary distinguishes executed segment work from a
cumulative simulation clock, and integration/setup from command wall time.
Queue, worker startup, checkpoint/export and total elapsed time remain unknown
when the native evidence does not measure them. Original artifacts are unchanged.

The shared gateway and batch skills require every requested section to be
delivered or identified as missing; a preview cannot stand in for a full report.
The OpenMM/GROMACS examples declare the HTML summary as the primary report.
Scientific execution, domain skill bodies, model settings and scheduling are
unchanged. Other engines retain their existing native timing rows and show
unrecorded scientific fields as unknown; this adds no new per-engine parser framework.

## Exact image and source

- Source: `c517ae6ef168a235174eda4cc5b469177a9e51f2`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:report-completion-20261023-c517ae6`.
- Digest: `sha256:d73a00bd00f4af578110680c4a4f3083f5f6ec3f753f0147c2f952b8b789f633`.
- Portable bundle: `2026.10.23.1`; [machine-readable receipt](evidence/report-completion-20261023.json).

All 78 compressed layers of the previous OpenMM image are preserved, with 89
layers in the candidate. Runtime configuration is unchanged. All 110 bundle
files and the changed helpers were compared to source. Fifteen recopied runtime
and domain files equal the base bytes, including the study executor, AF3
structure/preparation helpers, artifact and execution clients, and OpenMM and
BioEmu2 domain bodies. Only the report helper/alias, preview helper and report
discovery schema intentionally change among the compared runtime files.

## Bounded verification

The 92 focused tests cover verified observations, unknowns, escaping, source
integrity, retained-file preservation, study publication and skill packaging.
The 17 release-pointer and deployment-link checks also pass.
The exact image generated the report from retained public-input artifacts with
network access disabled and no accelerator attached.

A fresh system/qa chat loaded the actual updated shared skills and OpenMM
reference, then completed one durable analysis-only phase with seven verified
deliverables. The inline report showed 19,605 atoms, 50,000 steps, 100 ps,
303.220912 K, 762.374103 ns/day, 11.333019 s integration, 1.885277 s engine setup
and 15.136111 s command wall time. Unknown timing intervals remained explicit.
Both the original stream and saved-chat reopen rendered the report and nonblank
structure without Reset. All 62 original study files retained their hashes,
and both original chat messages retained their content and metadata;
no scientific model operation was submitted, resumed or cancelled.

QA received only seven helper/skill-reference files with exact-base checks and
backups. Its API, study supervisor and worker process identities were preserved;
only four selected skill registry entries were refreshed, preserving 85 other
skill objects. The OpenMM/GROMACS domain bodies and BioEmu2 skill were unchanged.
No live executor/schema/UI file or endpoint was replaced.

The other five maintained clients received the same seven-path overlay after
fresh idle-study, endpoint, process and base-hash checks. Their common batch
skill lacked two newer AF3 instructions. A conflict-free three-way merge added
only the report-completion guidance, preserving that existing difference.
Its SHA-256 is `b114ca09d32b7502dc0d0a17646f9411b7d89e96f275de1f103953bb37fa2bed`.
These are report-completion overlays, not byte-identical installations of the
full default bundle. On each client, all seven installed hashes and four loaded
skill bodies were verified, thirteen protected files and unrelated registry
objects were preserved, and the temporary loopback inspector was closed.
Existing study plans and receipts retained their hashes. Customer scientific
workflows were not retested, and no customer inference was performed.

Live overlays do not reload the long-lived worker or replace its executor or
schema. That worker's `native-md-timing` execution path was not requalified;
no stale-worker defect was reproduced. The updated workbench recipe and actual
QA used fresh `python-script` helpers. The new default image includes the updated
report discovery schema.

This qualifies the retained-result reporting path at the recorded scope. It
does not qualify new scientific execution, convergence, capacity, cross-user
isolation or provider recreation. The existing static admission acknowledgement
does not update when the live study card completes. The policy's broader
customer-ready/all-workflow verdict remains false.
