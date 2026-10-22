# BioEmu2 skill release — 22 October 2026

The canonical `skills/scientific-ai/bioemu2` skill uses hosted App `bioemu2`
and typed tool `submit_bioemu2`. It distinguishes structure prediction,
independent equilibrium conformations, time-lagged endpoints and sequential
rollouts. It is not classical MD, sequence design, calibrated free energies or
an affinity predictor. Public model and checkpoint revisions are pinned in the
bundle manifest. Microsoft Research attribution is separate from NVIDIA.

## Image and retained clients

The shared default selects image
`sha256:06d7359721514aad2d20b3921306e85294b11a66d647af4204a833b7ed97ae03`,
built from skill source `7b6fe1f66e541266bb96d73b8f4e55474893c869`
on prior RFD4 release `576d1448`. The existing 86 skills, prior runtime layers,
renderer, upload/recovery helpers and process configuration are unchanged.
The actual API loader sees 87 skills; the managed molecular-design agent seed
adds only `submit_bioemu2`.

Additive activation was verified in QA, Rene, Arseniy, LynxKite, Whitelab and
Prima Mente. Existing running processes, endpoint specifications, histories,
tenant keys and storage bindings were preserved. Customized agent tools were
not overwritten. No customer API key was used for inference tests.

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
