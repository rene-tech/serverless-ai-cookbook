# Scientific agent reliability — 1 October 2026

## Release decision

**QA candidate, not a customer-ready release.** The workflow/tooling changes are
implemented and deployed to the existing system QA binding. The approved
GLM-5.3-Flash conversational configuration still sometimes ends a turn without
an answer. Alternative-model controls also exposed scientific or delivery
mistakes. Two clean unchanged-release cohorts have **not** been achieved.
Do not use a successful engine job or one passing cohort to promote this release.

Lynx's current shared workbench, two existing logins, chats, bucket and shared
API key with concurrency eight were not changed. API integration and Ripple
are out of scope. No quotas, model-call limits or GPU-pool configuration changed.
The production/default image selector remains unchanged. See
[the conversational-model policy](../CHAT_MODEL_POLICY.md) before changing a
customer's model or introducing a fallback.

## Changes implemented

- One bounded recovery for an empty, normally stopped provider response. It
  retains the original task/tool results, uses an explicitly host-authored
  notice, and invokes only the conversational model. It does not replay tools,
  resubmit scientific jobs, increase budgets or switch models. A second empty
  response remains an explicitly incomplete turn, not a success.
- Typed CPU OpenFF preparation, preserving exact input identity, stereochemistry,
  pinned Sage 2.2.1 and AmberTools AM1-BCC. Duplicate calls reuse the durable job.
  Undefined stereochemistry returns computed choices without parameterization.
- Typed mmCIF inventory and verified final reports for ligand/MD outputs. The
  final report boundary applies only to a completed, explicitly requested final
  tool result. Intermediate inventory and multi-step tasks continue normally.
  Reports distinguish measured facts, configured settings and unvalidated claims.
- A typed launcher for manifest-pinned MD examples using the existing scientific
  client and native recipes. An unambiguous engine child folder resolves to its
  enclosing case; no new submission protocol or controller was introduced.
- Concurrent execution-MCP handling: one chat's long observation no longer blocks
  another chat's command. Responses remain matched to request IDs. This changes
  observation handling, not customer GPU admission/concurrency limits.
- Clear command, job state, exit code and output panels in the actual client.
  Frontend rebuilds preserve the Scientific AI landing page, workspace routes,
  viewers and Nebius/NVIDIA footer instead of rebuilding stale parent sources.
- Actionable errors when an API key's authorized catalog lacks a submission
  tool, before uploading input or starting computation.
- Full database/document/index state export/restore tooling for a future safe
  customer cutover. A QA observer's expiring session is renewed without
  resubmitting its chat or any scientific work; authentication failures remain
  recorded rather than being reported as scientific failures or fast passes.

The scientific skill bundle is `2026.10.01.6`. OpenFF and starter-data instructions
now use installed typed helpers and the existing durable client. These shared
changes are not Lynx-specific branches or a separate customer agent.

## Exact candidate and deployment

| Item | Value |
|---|---|
| Runtime source | `de10947df8547aa303304478633d0c738ba2ed06` |
| Registry image | `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:16815c8cf0d0b8d3c343c56f90559bca1fea26d8c93e7294d544a826ec636af9` |
| Build recipe | `Dockerfile.agent-reliability` |
| QA endpoint | `aiendpoint-e00zd7wjdavqaye6a1` |
| Project / region | `project-e00rene` / `eu-north1` |
| QA identity / bucket | Existing `system/qa` / `fs2-system-35f1ad07f2fe32cf` |
| CPU workbench | Existing 4-vCPU / 16-GB preset, 100-GiB disk |
| QA expiry / owner | 2026-10-08 / this task, system QA |
| Actual instruction SHA-256 | `0e7822765bb21eeb9fa956f78198de875960c7cc4f964609bbc6e4179af9dd19` |

QA URL: <https://port3080-bvcd2kv9nnk22gt.tunnel.applications.eu-north1.nebius.cloud>.
This is an authenticated QA workbench, not the customer handover URL.

The predecessor QA endpoint `aiendpoint-e00z6jxa9wfcs7gcks` was archived and
stopped. No extra tenant or bucket was created for these iterations. Its previous
R11 image digest was `06d0ca2e976242c4120c4f56773359fff2b9a2464e890e262a6e3b7c5018da4d`.
Later source commits only improve qualification and documentation; they do not
retroactively change the tested runtime digest above.

## Evidence and limitations

Exact-runtime checks: 82 Python tests, 16 Node tests and three React execution
panel tests passed. Eight qualification observer/link tests also pass on the
final source. These counts are scoped tests, not whole-platform certification.

The original four customer requests completed on R9: inventory 15.1 s, force-field
advice 24.5 s, the actual 78-atom ligand preparation 99.4 s, and GROMACS 120.5 s.
Broader R9 cases found defects and were rejected. Do not carry those timings or
that success forward as final R10 acceptance. R10 repeats completed inventory and
ligand preparation, but its local GROMACS turn ended empty before submission.

R10 real MD delivery:

| Engine | Operation | Raw artifacts independently rehashed | Native files independently rehashed |
|---|---|---:|---:|
| NAMD | `c529c81a-df33-4f26-933e-fa5ccd7dd991` | 78 | 77 |
| Amber | `b3f50ff7-bfc5-430a-bd4a-a19ede3b4cc2` | 40 | 39 |
| LAMMPS | `9fd0c6f2-760e-4b75-8fd9-792f124db7f3` | 39 | 38 |

NAMD took 108.3 s and Amber 93.2 s end-to-end through the client. The LAMMPS
observer's token expired; its existing operation completed and was recovered by
GET, with no resubmission. Preserve that interrupted-observer evidence rather
than assigning it a fabricated exact chat duration. All three final reports and
authenticated links pass delivery verification. NAMD's log identifies an H100
80GB GPU; LAMMPS identifies its Kokkos one-GPU backend. LAMMPS still emits a
suboptimal default-KISS-FFT warning; this task does not claim to resolve engine
performance optimization. These packaged examples establish execution/delivery,
not scientific convergence, matched-engine equivalence or production capacity.
Their reported GPU-snapshot-used flag was false.

Hosted R10 general cohort 1 completed all eight turns. Cohort 2 completed seven;
the CSV/plot turn was empty and produced no requested files. Across both cohorts,
48 available files matched authenticated HTTP downloads and independent S3
readback. Four real ligand bundles also passed independent identity, coordinate,
charge and hash tests. Missing second-cohort plot files are failures, not replaced
by first-cohort outputs. The subsequent hosted App-catalog request worked, but
GROMACS ended with reasoning only and no submitted operation. This is another
failed agent handoff, not a failed GPU simulation.

Browser validation on the hosted digest exercised the rendered plot, expanded
command/output panel, original result link, authenticated workspace and actual
download. The downloaded CSV matched HTTP/S3 bytes:
`49baa0bad781fd6a0a8319e939b995c1312e6a314d0235f37c2637d23f0fe830`.
The Nebius/NVIDIA footer remains present. Completed chats survive navigation and
reload. A clean final hosted in-flight GPU reconnect is **still unproven** because
the last intended reconnect test ended before job submission.

Model controls used the same tools and scientific cases, not raw chat-only
prompts. GPT OSS 120B and GLM-5.2 completed the four original requests, and
GLM-5.2/Qwen 235B completed eight general turns. None is a qualified replacement:
GPT invented preparation commands/compatibility details; GLM-5.2 misplaced
intramolecular 1–4 interactions at a protein–ligand interface; Qwen claimed a
missing file without inspecting it and used an HTML workspace page as an inline
image. Qwen's `path=directory&file=basename` download was valid: the old verifier
incorrectly requested a root-level file and was fixed to match the existing UI.
Both its original false-failure receipt and corrected technical receipt remain.

## Customer preservation, rollback and remaining work

The existing customer endpoint remains `aiendpoint-e00kybbs8a1sbxcfyw` on digest
`16b34a377caf015553d4d51ef78721ce1eb142d6e5c9a57ccd7cffdf7b9cdc65`.
Read-only captures were restored into an isolated instance before startup.
Original passwords and both users' existing histories were verified; all
collections/documents/indexes and encryption settings were preserved. That
rehearsal is not a final quiesced capture or a completed customer migration.
Never stop the customer Serverless endpoint before a fresh, verified state
capture: stopping destroys its VM/local disk. Preserve the shared binding.

Next steps, without reopening API/Ripple work:

1. Resolve the repeatable empty-turn path or obtain product-owner approval for a
   different conversational default. No automatic fallback was added.
2. Qualify the selected configuration for scientific correctness as well as
   execution, including the known advice, file-inspection and image-link failures.
   Repeat two unchanged-release cohorts and a real hosted in-flight reconnect.
3. Only then promote the image/default, quiesce/capture/restore the customer
   instance, and recheck both logins, existing chats, bucket, APIs and key limit.

Private transcripts, customer inputs, secrets, screenshots and detailed receipts
are retained under `/home/tux/secure-handoff/fs2-agent-reliability-20261001`, not
committed. The task card is
`fs2-scientific-agent-reliability-r20261001` in NIM Fast Start Platform. Do not
overwrite earlier failed cohorts or describe this ticket as completed.

The failed R9 NAMD attempt did not submit inference, but left QA upload evidence:
operation `38d9ad06-e03f-4da5-b139-f8d65a3a4796`, upload
`c92a2830-8fe9-5599-b523-18f529431345`, plus finalized source artifact
`2312e6cf-2af4-498a-a9fe-6c5ee11fd2b8`. These exact identities remain recorded
for supported retention/cleanup; no bucket-wide deletion is authorized.

Closeout: task-owned local R10 was stopped after all 44 execution records were
terminal; prior local candidates are also stopped. Their data remains available
for reproduction. No qualification worker remains running for this ticket.
Only the existing cloud QA replacement is retained, with the expiry above;
the customer endpoint was not stopped or modified.
