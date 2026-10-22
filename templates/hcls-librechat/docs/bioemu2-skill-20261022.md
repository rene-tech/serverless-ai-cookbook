# BioEmu2 skill release — 22 October 2026

The canonical `skills/scientific-ai/bioemu2` skill uses hosted App `bioemu2`
and typed tool `submit_bioemu2`. It distinguishes structure prediction,
independent equilibrium conformations, time-lagged endpoints and sequential
rollouts. It is not classical MD, sequence design, calibrated free energies or
an affinity predictor. Public model and checkpoint revisions are pinned in the
bundle manifest. Microsoft Research attribution is separate from NVIDIA.

## Image and retained clients

The shared default selects image
`sha256:6b367cc6bb490caced752009191fdc6eeb7176aaf9c16b9b48c4c0ee82491059`,
combining skill source `7b6fe1f66e541266bb96d73b8f4e55474893c869`
viewer fix `584095a3cdbb5209fb243e5dd9f6b19aed4f0914`, and skill refinement
`0c71993` (immutable build source `0fae16c`, before integration rebase).
The skill layer `06d73597` extends prior RFD4 release `576d1448`; the final
viewer overlay changes only the structure bridge and its bytecode. The final
refinement adds only the BioEmu2 instructions and bundle metadata over `eec90d`.
The existing 86
skills, other runtime layers, upload/recovery helpers and configuration remain.
The actual API loader sees 87 skills; the managed molecular-design agent seed
adds only `submit_bioemu2`.

Additive activation was verified in QA, Rene, Arseniy, LynxKite, Whitelab and
Prima Mente. Existing running processes, endpoint specifications, histories,
tenant keys and storage bindings were preserved. Customized agent tools were
not overwritten. No customer API key was used for inference tests.

The coordinated AF3 deliverable-validator image is a separate release in progress.
It must preserve these BioEmu2 refinements, either by building on `6b367cc6` or
including the same skill and manifest from current main. Do not repoint the
default to an image that drops the latest skill; a merged source change is not
proof that a previously built image contains it.

Offline checks: 54 bundle tests and four seed-merge tests passed, plus actual
installed-image skill-content equivalence. The onboarding evidence packet is
`/home/tux/secure-handoff/bioemu2-onboarding-20261022.53L3QW`; it contains exact
activation receipts for each retained endpoint and the private QA chat evidence.

## Customer behavior

Read the live authorized schema; installed instructions do not imply access.
Use uploaded A3Ms or explicitly select single-sequence inference. Never silently
send sequences to public ColabFold. Preserve contact/bond annotations, native
denoising defaults and failed/unchecked physicality flags. Query-only example
alignments are not fabricated homolog alignments.

Upload real workspace files through the existing helper, submit once, then
observe the native operation ID. Verify returned hashes and safely extract
CIF/XTC. Render verified structures inline through `workspace_files`, including
the returned UI marker verbatim. Links are secondary access, not inline delivery.
Report measured frames/s, separating queue/startup from model execution.

The private App onboarding report records exact GPU workflows and limits.
Single-GPU tests do not qualify distributed context parallelism, GPU process
snapshots, biological accuracy or sustained shared-service capacity.

## Real QA chat and discovered rendering fix

The main agent submitted one equilibrium request, used same-ID read-only result
recovery, verified both artifacts and every internal file hash, and requested an
inline structure. Operation `op-4b4ff0ddbb8e5ca3` returned two finite 76-atom
frames, both passing native protein physicality checks. The worker command took
26.98 seconds (model load 5.24 s; embedding/sampling 9.88 s); acceptance to
completion was about 235 seconds including queue, startup and delivery. These
are QA-scale measurements, not a sustained-capacity claim.

Browser inspection caught an actual empty viewer despite the agent's success
claim. CIF rows beginning `ATOM` were classified as fixed-column PDB before
checking the explicit CIF headers. The shared detector now checks CIF first;
the regression covers both local-file and operation-result inputs. Forty viewer
tests passed. Regenerating the same verified file's UI resource rendered all 76
atoms inline, without another model call or modifying coordinates. The old
saved erroneous UI resource is retained as incident evidence; new renders use
the corrected detector.

Retained-client maintenance patches only the detector after checking its exact
old text. It reconnects only an idle `structure-viewer` MCP connection, preserving
other MCP objects and the API/study processes. Backups and receipts are retained.

## Final fresh-session acceptance

A later reused conversation invented completion details and an invalid UI marker
after racing dependent tools. That failed chat is retained, not counted as a
pass. The skill now requires sequential dependent phases, observed operation
outputs and actual successful viewer resource IDs, with a regression test.
These instructions were activated in all six clients without an API restart.

The fresh conversation `223c96fa-24e5-5e1e-a689-613b696f0ba3` then completed
operation `op-d0a160aed1e2f895` on final BioEmu2 runtime R5. Actual tool outputs
verify unchanged public inputs, two generated conformations, all artifact/file
hashes and native physicality. The agent recovered a tar-on-object-mount warning
and observation timeout without repeating inference. It corrected an unsupported
operation-ID viewer call to the documented local-file path. The successful
viewer returned `dcbe9f145f`; the assistant used that real marker and the
browser displayed the 76-atom structure inline without a reload.

Model load: 5.24 s; embedding/sampling: 9.63 s (0.208 generated frames/s).
Tool retries and agent reasoning add latency beyond backend execution. This
does not claim deterministic LLM behavior or all-workflow workbench qualification.
