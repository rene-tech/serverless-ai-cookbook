# General Scientific AI workbench / OpenFF release — 1 October 2026

## Scope and verdict

This is one **shared general-purpose image**, not a Lynx-specific variant. New
deployments use the same instructions, scientific skills and installed CPU
OpenFF environment. Existing customer endpoints are not automatically upgraded.

**Packaging and runtime checks pass. Broad unattended-scientist readiness does
not pass.** Real LibreChat tests are substantially faster than the retained
default, and produce genuine OpenFF/GROMACS files, but the default conversational
model still sometimes ends without an answer or adds inaccurate scientific
prose. Those failures are retained, not counted as successful tests. Installing
OpenFF does not solve all agent reasoning. No silent model fallback is enabled.

This release does not requalify all Apps, large-molecule preparation, arbitrary
protein/ligand force-field combinations, GPU snapshotting, or platform scaling.
OpenFF ligand preparation itself is CPU-only; existing GPU model services are
unchanged.

## Exact image and deployment

- Repository: `rene-tech/serverless-ai-cookbook`.
- Image source: `4239aa4` (the later metadata/report commits do not change it).
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:general-openff-20261001-r11`.
- Digest: `sha256:06d0ca2e976242c4120c4f56773359fff2b9a2464e890e262a6e3b7c5018da4d`.
- Pinned parent: `lc@sha256:16b34a377caf015553d4d51ef78721ce1eb142d6e5c9a57ccd7cffdf7b9cdc65`.
- Preserve this parent for rollback; it does **not** include the new OpenFF runtime.
- Shared selector: `templates/hcls-librechat/scripts/release-image.sh`.
- Deployment entry point: `templates/hcls-librechat/scripts/deploy.sh`, tested
  without an `IMAGE` override. `SERVERLESS_DRY_RUN=true` checks the same request.
- System QA: `project-e00rene`, eu-north1, CPU D3 4 vCPU / 16 GB, 100 GiB disk;
  endpoint `aiendpoint-e00z6jxa9wfcs7gcks`,
  [authenticated workbench](https://port3080-ep8rp3bgcyjva6y.tunnel.applications.eu-north1.nebius.cloud).
  Provider state RUNNING, registry digest, running-container image and installed
  source revision were checked independently. This is the retained system QA
  instance, not a replacement for a customer's instance.
- Bucket: `fs2-system-35f1ad07f2fe32cf`, existing system/qa principal
  `8f343d1c-35d2-556b-ae4b-fad3d903be52`, non-admin App key, concurrency 2.
  App grants: GROMACS, GROMACS MPI, Boltz2 and OpenFold2, not all customer models.
- Older QA endpoints `aiendpoint-e00qh8akarevfwqb93`,
  `aiendpoint-e00tgjvxqph1s686gw` and `aiendpoint-e00rpmeqwn43j4k4z6` were
  backed up and STOPPED before replacement;
  bucket content was retained. No customer instance,
  login, API key or bucket was changed.

## Installed capabilities

The primary agent and custom endpoint share `agent-instructions.md`: 9,969
characters, down from 76,473 in the retained baseline. Domain instructions load
on demand. This is a change to prompt composition, not a new scientific agent.
The approved `zai-org/GLM-5.3-Flash` default remains; reasoning effort is `low`.
Explicit operator overrides remain supported, including `high` / `max`.

- 36 canonical customer skills, 84 installed including the pinned ClawBio set;
  actual LibreChat loader tests verified 78 hashed core files / 79 resources.
- `/opt/openff/bin/python`: Toolkit 0.18.0, Interchange 0.5.2, AmberTools 26.0,
  OpenMM 8.6.1, RDKit 2026.3.1, openff-forcefields 2026.01.0. A SHA-256-pinned
  conda package lock installs the coordinated environment during the image build.
- `prepare-openff.py`: exact, stereospecified standalone ligand SMILES; pinned
  Sage 2.x; CPU AmberTools AM1-BCC; GROMACS `.top` / `.gro`, charged SDF, charges,
  exact force field, versions, finite CPU point energy, file hashes/readback.
- The helper rejects undefined stereochemistry before outputs are created.
  `--inspect-identity` computes the actual isomeric SMILES and CIP labels using
  RDKit; it does not choose an isomer or run parameterization. Instructions tell
  the agent to ask using these computed choices. R7 exposed reversed R/S labels
  when the model guessed them; R9's helper test covers that exact case.
  Existing results are not overwritten. No package installation is required
  in a customer's parameterization task.
- Deterministic Gemmi mmCIF and Biopython FASTA inventory helpers. GC over zero
  A/C/G/T bases is undefined, not zero. Workspace file URLs are returned by helpers.
- Native skill references are included in tool results; installed `/app/skill/`
  paths resolve through the original skill reader and its permissions. This
  removes the path mismatch; it **does not establish a fix for every empty turn**.
- Title generation retains GLM and bounds reasoning. A cold title request may
  still reach the existing 10-second abort and use the user-text title fallback.
- MD starter guidance uses the existing installed scientific-batch client, not
  the pack's POSIX-only `run-example.py` on an S3 mount. Native input archives
  and parameters stay unchanged. The client retains operation identity and
  verifies downloaded bytes; completed-run recovery cannot submit inference.
- `native_md_artifacts.py` materializes engine-native filenames by exact
  `(sha256, size_bytes)` identity, never by list position. Native copies and
  per-file workspace links are indexed in `native-files.json`; raw artifacts
  remain independent of later native-file edits. The same generic result
  contract is covered for GROMACS, NAMD, Amber and LAMMPS with shuffled/aliased
  unit fixtures; live coverage in this release is GROMACS only. Native copies
  require additional bucket storage equal to the copied native outputs. The
  transport still retains its raw artifacts; this is not storage deduplication.
- The additive build assembles changes separately and copies eight runtime roots
  onto the retained parent. The final image has 121 layers and successfully
  creates containers; the first R10 build exceeded Docker's runtime layer depth
  and was rejected before any deployment.

The OpenFF environment adds about 3.9 GB unpacked (~980 MB of compressed conda
packages). The full image is about 11 GB unpacked, so fresh Serverless image pulls
are a deployment cost. It does not consume GPU memory or claim GPU snapshot reuse.

## Comparison method and findings

The committed `scripts/qualification/default-release-cases.json` contains eight
public/synthetic scenarios: 1UBQ inventory; force-field advice; neutral aspirin;
+1 methylammonium; undecided stereoisomer; FASTA inventory; CSV/error-bar plot;
missing input. Separate hosted fixtures exercise authorized App discovery and
the actual seeded GROMACS route. These are scoped workflows, not a full scientific
validation programme.

Tests call the real LibreChat agent API, follow durable generation IDs, preserve
transcripts, and use fresh output prefixes. GLM release tests retain the actual
seeded agent, not a privileged hand-made replacement. Local replicas have 4 CPUs
and 12 GB RAM. Two worker threads are used; polling contributes up to 3 seconds.
Chat elapsed time is not GPU time, and message token counts are not billing data.

Baseline: four of eight turns hit the 150-second watchdog (structure inventory,
both ligand preparations, unresolved stereochemistry). Completed advice, FASTA,
plot and missing-file turns took approximately 51, 78, 69 and 12 seconds. Baseline
timeouts are censored observations, not exact completion times.

Earlier candidates completed many equivalent turns in 6–48 seconds. Some were
still wrong: false atom totals, invented force-field details, GC=0 for an all-N
sequence, broken download links, or blank answers after skill loading. R4 hosted
cohort 2 had **two unfinished OpenFF turns**. R5 and R6 also had unfinished turns.
All are failed evidence; no cherry-picked clean-cohort claim is made.

Kimi K3 and GPT OSS 120B were compared through the same client/tools, in isolated
candidate agents. Both completed the eight requests at transport level; neither
earned an all-scientific-pass verdict. Kimi invented an `example.com` workspace
link and overstated stereochemical preparation properties. GPT OSS produced a
placeholder plot, invalid links and unsupported compatibility advice. There is
no evidence here to call a default-model switch a complete fix.

## Scientific and artifact validation

Actual neutral and charged ligand outputs are independently checked against the
input molecule: canonical identity, atom count, GROMACS charge rows and sum,
coordinate count/box, finite CPU reference energy, and every manifest hash.
These checks do not establish matched-engine energies or molecular accuracy.

The export box is artificial and empty with **1 nm padding**. There is no solvent,
protein assembly, equilibration, production MD or `grompp` validation in this
helper. A parameter bundle is not an MD-ready protein/ligand system.

Hosted R4 already exercised authenticated workspace reads and independent S3
readback of 25 files, with matching bytes and both ligand chemistry checks.
GROMACS operation `bc13dbf6-d0e6-4e55-9120-c786a466b3ba` succeeded on one H100:
unchanged seeded minimization + 20 ps NVT + 20 ps NPT + 20 ps production,
56 recovered artifacts, approximately 83 seconds accepted-to-terminal / 74
seconds compute. An optional summary append failed on the object-storage mount;
that warning is retained, not counted as a fully clean workflow. This earlier
image evidence is **not** final-R11 acceptance.

### Retained R7 failures and recovery

Both hosted eight-case cohorts produced visible answers (one status-read HTTP
503 required observation recovery, not resubmission). Across the two cohorts,
50 files matched authenticated workspace download and direct S3 readback,
including four independently checked OpenFF exports. The chat nonetheless
proposed reversed R/S labels; these are **failed scientific cohorts**.

A GROMACS chat ended blank before submission. A second submitted operation
`ec94b08a-50b1-4949-9798-51f4b0d073c5`, which ran successfully on one H100
(11:35:40–11:36:58 UTC). The older bucket example script then failed with a
partial/zero-byte manifest and unsupported lock-file behavior on Mountpoint S3.
It also installed an unnecessary temporary environment. Operator recovery using
the already installed client verified all 56 outputs in a fresh directory,
with `inference_submitted: false`. This is a recovered result, not a clean
end-to-end chat pass, and it motivated the shared starter-data instructions.

The real browser download of `summary.csv` matched the verified workspace/S3
bytes (SHA-256 `64c708ac69b1d1bbd648e328aa6b5a8f981715105eb45003b12134fe15e5bada`).
Opening its link creates another tab; a wait on the old tab was a test-driver
mistake, not a failed workspace link.

### Retained R9 evidence

Offline: 20 instruction/deployment/replay checks, four title/skill-adapter tests,
five installed OpenFF checks including a real charged output fixture, and the
actual installed skill loader all pass. Registry readback confirms the digest.

Local cohort `dece347275c6401bab361a4b21ba0276` completed seven of eight turns
with visible answers in 6–33 seconds; unresolved-stereo stopped after loading
instructions without asking the required question. Aspirin and methylammonium
parameterization took 33.1 and 27.1 seconds (the baseline both exceeded 150s).
The plot's numerical summary was correct, but its prose said the SD intervals
“overlap heavily”; [1,3] and [3,7] only meet at their boundary. This is a factual
failure even though the requested files were created. No whole-cohort pass.

Hosted R9 cohorts `f47f58a5147b44938cea81f943e591f5` and
`5216474d0a444aa8b3fbcb908af1cb51` completed 14 of 16 conversational turns.
First-cohort aspirin and undecided-stereo were incomplete; cohort 2 had visible
answers throughout but invented force-field advice (including Sage as a protein
force field and different combining rules). All three produced ligand bundles
passed independent molecular/charge/export checks. In total 39 available files
matched authenticated HTTP and S3. Absent aspirin outputs were a failure, not
silently replaced by results from another cohort.

The original reported larger-ligand workflow also ran privately on R9: 108.5s
chat elapsed, 78-atom neutral bundle, independent molecular identity/charges and
hashes passed. The original CIF inspection took 9.1s but added unsupported
structural interpretation; this is not a full customer-workflow pass.

R9 GROMACS operations `2db3e924-6c5f-4d6b-a091-40074c110055` and
`ef4812e0-c49c-4ebb-ab01-2acf6cdfc97e` both succeeded. The first delivered 56
correct raw artifacts, but the agent incorrectly renamed derived files: five
expected native paths were absent and the remaining 50 did not match native
hashes. Its summary link was also incorrectly base64-encoded. The second chat
hit its 360s watchdog after the simulation had completed. These are failed chat
handoffs, not model-runtime failures. Original raw bytes remain intact.

This directly motivated deterministic native-file materialization, covered by
14 tests, the 43-test real-SDK client/diagnostics suite and reconstruction of all
55 native files from the retained real result. No GPU work was resubmitted for
that reconstruction.

### Final R11 evidence

Exact installed SDK client/diagnostics/native-file tests: 43 passed. Packaging,
registry digest, actual container creation and installed OpenFF runtime pass.
The final selector also passes 20 instruction/renderer/seed/deployment/replay
tests and three native-skill adapter tests. Each of four real hosted ligand
bundles and the original larger-ligand output passed five installed-OpenFF
checks, including independent identity, coordinates, charge rows and hashes.

Two unchanged hosted cohorts completed all **16/16** core chat turns, but that
is conversational completion, not a scientific pass rate:

| Workflow | Retained baseline | R11 cohort 1 | R11 cohort 2 |
|---|---:|---:|---:|
| mmCIF inventory | >150s, aborted | 6.7s | 6.7s |
| Force-field advice | 51.2s | 34.6s | 6.7s |
| Neutral aspirin preparation | >150s, aborted | 84.7s | 59.5s |
| Charged methylammonium preparation | >150s, aborted | 56.3s | 50.1s |
| Unresolved-stereo question | >150s, aborted | 22.2s | 6.7s |
| FASTA inventory | 78.2s | 22.2s | 6.7s |
| CSV/error-bar plot | 69.2s | 31.6s | 37.8s |
| Missing input | 12.1s | 25.2s | 3.6s |

Cohorts: `d7025ee3137c42a4a2a75e0bc59883d4` and
`0ec0edc4c4384eea96ffd0262e5f9406`. The hosted instance used mounted S3;
the baseline used a local workspace. These are observed workflow timings,
not a controlled inference-speed benchmark or a latency guarantee. Cloud
provider response time and two concurrent test workers contribute to variation.

All 50 files produced by these two cohorts matched authenticated HTTP download
and independent S3 readback. Both molecular identities and formal charges
survived export; undefined stereo resulted in a question, no parameterization,
and computed R/S choices independently confirmed with RDKit. Both FASTA results
correctly left the all-N sequence's GC percentage undefined. Plot means/SDs
matched the source data; no statistical significance was measured.

**Known final-image failures:** cohort 1's force-field advice invented a CGenFF
penalty threshold of about 0.5. Official guidance instead discusses validation
for scores 10–50 and possible optimization above 50
([MacKerell lab](https://mackerell.umaryland.edu/cgenff_prgrm.php)). Its plot
comment also overgeneralized that small n makes significance testing inappropriate.
Cohort 2's aspirin answer named the correct output directory/files but omitted
clickable links. These are retained prose/handoff issues, not broken exports.

Apps cohort `a2e23bd8d4b340948580ef0797307ead` discovered exactly the four
granted Apps and completed the actual seeded GROMACS workflow:

- Operation `f7e29d77-6802-4b78-9f3d-d07ff807d58c`, 12:18:27–12:19:49 UTC;
  82.4s accepted-to-terminal; 144.0s complete chat including files.
- Existing `h100-ondemand-1x` pool, one GPU, one attempt. No new GPU capacity,
  quota or scheduling-policy change; the existing App chose the pool. Runtime
  digest `sha256:14ffdae0f0389c7771bae8791c56a5e21736ece630bd11dfb0f3b6a78f8cd643`.
- Unchanged minimize + 20 ps NVT + 20 ps NPT + 20 ps production; engine logs
  confirm completion. This is execution/file-handoff coverage, **not** sampling
  convergence or a fresh engine-performance qualification.
- All 56 raw artifacts verified; all **55 native paths matched their exact
  engine-recorded size and hash**, with no model-generated renaming. All 136
  objects under the output prefix matched HTTP and S3, including raw/native
  copies, request records and receipts.

Apps cohort `3642cc72822a4bedaeb74c654d53201a` discovered the same Apps,
but its GROMACS chat ended after loading a skill: **incomplete, no submission,
no output artifacts**. No duplicate/replacement inference was launched to hide
that failure. Thus only one of the two MD chat workflows passed; the two-clean-
cohort gate is not met. Across core plus App workflows, 19/20 chat turns completed;
this is **not** a 95% scientific correctness claim.

The final local replay of the original reported larger-ligand request produced
a verified 78-atom neutral bundle in 150.4s chat elapsed; independent chemistry
checks passed. Its inventory and advice turns took 69.3s and 60.2s. The inventory
still added structural interpretation beyond a coordinate inventory; no claim
is made that the entire original scientific workflow has been validated.
Private original inputs stayed local, outside the system bucket and Git.

Real-browser checks passed: login, Nebius branding, the four caller-scoped Apps,
inline plot, and chat → Workspace → Download. Downloaded `summary.csv` matched
HTTP/S3 (SHA-256 `e97e865d5098f60052383f2ea015bf7f8bc82167ce13c9e5bb5c23f9461e7174`);
the actual GROMACS chat's `native-files.json` download also matched
(`5b825978ed55ac844a1cc7736b489fc805897172ce554a04dfca584e0a18d67b`).
There were zero browser-console errors; one existing iframe warning remained.
An initial test waited for a model link when the UI actually uses a heading;
the corrected selector passed. That driver mistake is not an App outage.

All task-owned local QA containers are stopped. One final system QA endpoint is
retained, with earlier endpoints stopped and backed up. A sanitized
[machine receipt](general-openff-release-20261001.json) accompanies this report.
**No broad customer-ready or two-clean-
cohort claim is made.**

## Reproduction, retained evidence and next work

- Build: `docker build -f templates/hcls-librechat/Dockerfile.default-release
  --build-arg HCLS_IMAGE_REVISION=<commit> -t <new-immutable-tag> .`.
- Offline: instruction/renderer/seeding, deployment dry-run, replay parser,
  skill-result/path adapter and installed skill-loader tests.
- Runtime: execute the mmCIF/FASTA tests with `/opt/scientific-client/bin/python`;
  OpenFF tests with `/opt/openff/bin/python`, including a real output fixture.
- Live: `scripts/qualification/replay_agent_instructions.py --help`; use the
  exact deployed seeded agent, two unchanged cohorts, then independent artifact
  and browser checks. Transport `scientific_pass: null` must be reviewed, not
  automatically changed to true.
- Private evidence: `/home/tux/secure-handoff/fs2-default-openff-release-20261001/`.
  This contains secrets/session state; do not upload the directory to Git.
- Task: `fs2-librechat-default-openff-release-r20261001` in NIM Fast Start Platform.
- Retain one system QA endpoint through 8 October, then review/backup before
  stopping. No automatic deletion of histories or bucket data.

Before describing this as unattended-scientist ready: resolve/reproduce empty
provider completions, prevent unsupported scientific prose and invalid handoff
links, and obtain two genuinely clean unchanged-release cohorts. Do not retry
already-submitted scientific jobs to mask a chat-layer failure.
