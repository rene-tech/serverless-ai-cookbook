# GROMACS workbench release — 23 September 2026

This is an additive GROMACS release of the existing Scientific AI agent, not a
new agent or an all-model readiness claim. The user explicitly authorized
replacing the recording instance after recording finished.

## Immutable runtime

- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:4155dd171ecb2e3c178695a66efe426c75ea8d219dfaceb8757735774dbe8a36`.
- Tag: `gromacs-p2-20260923-r1`; runtime source `ccc918b556ca4af312992e3d792d6ed39bec7bc0`.
- Canonical skills version: `2026.09.23.2`.
- Based on the exact prior recording image `sha256:7edb49a149626f585e11293cdf19e3d0c238b0d23f131ecc12a845725619ed63`.
- Existing UI, pinned ClawBio selection and GLM 5.3 Flash default retained.
  The installed loader verifies 80 skills, 70 resources and 63 core files.

The canonical GROMACS skill and scientific-batch client add the hosted single-GPU
and separate MPI App contracts, customer-bucket artifacts, native restart,
PLUMED/Colvars guidance and explicit unsupported/unqualified boundaries. Current
two-node TCP execution is slower than single H100; multi-node is not the default.

## Hosted acceptance before replacement

The exact image's client submitted/polled/downloaded via normal typed MCP:

- Colvars, 200 ps: `96d6a1b5-aef4-48f8-93a2-bcd3f44d4ed6`; 84.522 s;
  42 native artifacts; 101 frames through 200 ps; customer objects verified.
- PLUMED, 1 ns, worker eviction/retry:
  `6c62e47c-db60-45e3-99af-55c06123e693`; 311.193 s; 95 native artifacts;
  501 frames through 1,000 ps; complete HILLS/COLVAR and bucket outputs verified.
- Two-H100 MPI, million-atom STMV, peer eviction/retry:
  `647af3b7-1ca4-42bc-ba49-47f17650729b`; 346.492 s; 24 native artifacts;
  joined native energy checked through 12 ps; 575,034,848 exported bytes verified.
- MPI cancellation: `6ac88364-d1c3-4052-ba13-101fbc519af6`; all GPU resources
  released in 131.908 s including the configured 120-second termination grace.

These are workflow and recovery measurements, not cold-start timings or
scientifically converged free-energy results. Recovery uses native GROMACS
checkpoints and bias files, not persistent CUDA/CRIU snapshots.

## Recording-account migration

Predecessor: `aiendpoint-e00vc5qbt61ha6me9g`. Replacement:
`aiendpoint-e00rxhvqkjfny2zkzy`. The replacement copies the existing endpoint spec,
changing only the immutable application image and same-user supervisor ownership
mode. Bucket selectors, credentials, provider/model settings and resource sizing
are preserved. No quota was raised.

Before stopping, private exports captured 11 conversations and their messages,
workspace/run listings and five referenced chat images (2,536,895 bytes, hashed).
The mounted bucket was independently matched to the bucket authorized by the
actual Rene platform key. No customer bucket was deleted or recreated.

Important observed Serverless behavior: the endpoint owns an ephemeral VM and
root disk. A direct Compute stop triggered the Serverless `VMStopped` teardown,
which superseded the stop operation, deleted the VM/disk, and made the attempted
private full-disk image backup impossible. A running RW-attached disk cannot be
imaged, and there was no usable stopped-disk window. **No full disk/MongoDB backup
was obtained.** Do not repeat that approach. Stopping the endpoint is not a
disk-preserving rollback. Preserve data through supported application exports
or a tested pre-stop database/filesystem backup before any future replacement.

The conversation/image exports are retained privately under
`/home/tux/secure-handoff/fs2-gromacs-20260923/recording-backup-v3` and
`recording-assets-v1`. Native import changes conversation/message IDs; it must
preserve visible text/content and restore attachment references. It does not
migrate arbitrary local MongoDB or resumable execution state. The source archive
remains authoritative for original provenance. Existing model operations and
workspace files remain in the platform/bucket.

Restoration passed: **11 conversations / 40 messages / five images**. Text,
structured tool content, roles and remapped image attachment coordinates were
verified after native import. LibreChat strips transient assistant renderer
tokens of the form `\\ui{0123456789}`: old embedded UI widgets are not migrated.
The verifier normalizes only that exact assistant-text token shape, never user
text or tool payloads. Original unmodified messages remain in the private export.

The migration helper initially omitted the file API's browser User-Agent and
required image dimensions. These operator-harness errors were corrected without
changing server policy. Repeated password logins reached the normal login rate
limit; the resumed migration reused its authenticated refresh session instead.
Resume checkpoints now retain imported IDs before validation, preventing duplicate
chats/images after interruption. Five targeted migration tests pass.

Live UI: existing Nebius header, six research cards, six getting-started examples,
provider selection/key dialogs, prompt copy, desktop/mobile layout and no
unintended inference all passed. Both GROMACS Apps appear in Rene's caller-scoped
catalog. The workspace API uploaded and downloaded the three public Colvars
fixture files with matching hashes through the unchanged customer mount.

New URL: <https://port3080-mz8eyp8tbzg8hyp.tunnel.applications.eu-north1.nebius.cloud>.
The old endpoint remains stopped; restarting it is not a database rollback.
The actual browser-agent request submitted operation
`031f7588-a7bc-437e-a30e-0a8ad88e10a0` once and completed the 200 ps Colvars
workflow in **80.534 seconds from acceptance**. Independent workspace downloads
verified all 43 artifacts / 42 native files, five steps, seven checkpoint
generations, 101 trajectory frames ending at 200 ps and finite gyration values.
All 46 customer-bucket export objects / 25,287,102 bytes and 212 references also
verified. The full chat adds protocol inspection and reporting time; this is not
an 80-second prompt-to-report or uncached cold-start claim.

Targeted final checks: 23 onboarding, deployment, GROMACS-skill and migration tests
passed; canonical 32-skill bundle verified. Pytest emitted cleanup warnings for
unrelated old PostgreSQL socket fixtures; no unrelated files were removed.
Browser logged no errors and one headless wake-lock permission warning.
The disposable qualification key was revoked; Rene's existing key was unchanged.

The agent's first ad-hoc report parser rejected whitespace-padded XVG data and
assumed an outdated performance-column layout. The simulation and its verified
artifacts were unaffected. The agent retained the failed script and corrected
the parser without resubmitting MD. This is not a flawless-chat claim. A reusable
native-output reader would reduce both this class of analysis error and repeated
LLM file-inspection latency; the deterministic release validator already handles
whitespace correctly. Colvars' first column is MD step, not simulation time.
Its README generator also initially assumed every manifest entry had a
`size_bytes` field; it corrected that locally. Both analysis failures were retained.
The initial browser prompt-to-report took **760.5 seconds (12 min 40.5 s)**,
without intervention during execution or analysis and without duplicate MD.
Its final prose used a generic `file=<name>` link and claimed a fixture copy
that was absent from the directory listing. Those are presentation defects,
not additional successful checks. A follow-up asks it to reconcile its report
with real files and provide exact links; do not describe the initial response
as unattended-perfect. The actual Workspace download control returned the
summary successfully with the independently expected SHA-256.
Final deliverables are in
`/workspace/my-studies/gromacs-colvars-client-20260923/`.

Presentation follow-up completed: `HANDOVER.md` contains four concrete links;
fixture.json was copied byte-for-byte from the supplied source. Independent
capture found exactly these two new files and no changed/missing previous file
among the original 76. The corrected summary link opens a new Workspace tab
with summary.md selected. The first link-test helper waited in the old tab and
timed out; selecting the actual opened tab verified the correct destination.
Final private capture: `client-p2-study-handover-final-v2` (78 files,
26,452,942 bytes). No additional simulation or analysis run was submitted.
