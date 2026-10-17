# Scientific progress, inline reports and GROMACS preparation

This is an additive release over the qualified optional-precheck client, not a
new client or a claim that every scientific workflow is qualified. Read
`scripts/release-image.sh` for the current immutable default.

## Release identity

- UI/observer source: `b79d07937fa452f3e1a95ecde542b57c88e9bd8f`.
- Compact image packaging: `544eb8d17f6c185b7ab2fb626cec35cf1ee33434`.
- CPU tooling and final instructions: `6ca17f0049f57453be43891f0b471e26f3830b8e`.
- Native report packaging correction: `19f92471e04ecc6ae8f27985277d9d683004093b`.
- Combined image tag: `scientific-progress-gromacs-prep-20261016-r2`.
- Registry: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc`.
- Digest: `sha256:86025c2732cfc0334f5c315d019e11cf178c4ee268ec21e2b7afc9223fdfb572`.
- Scientific skill bundle: `2026.10.16.6`, 37 canonical skills / 88 locked files.
  The complete installed inventory also includes the existing pinned ClawBio skills.

The former image ancestry reached Docker's layer-depth limit. The intermediate
progress image compacts the filesystem while retaining the exact base's runtime
environment, entrypoint, healthcheck and working directory. The final tooling
overlay uses that immutable intermediate digest. Credentials, bucket bindings,
MongoDB state and provider configuration are deployment-time inputs, not image
contents. No private mdprecheck source or customer input is added to the cookbook.

## Customer behavior

- Runs and Whole studies display measured scientific work, rate and freshness.
  Observed progress and durably checkpointed progress are separate. Unknown is
  never zero; old jobs need not be restarted just to acquire new instrumentation.
- Customer status cards omit GPU SKU/count, image and placement details.
  Native scientific input/protocol artifacts remain available for reproducibility.
- Saved mdprecheck HTML/JSON links can show verdicts, findings and the embedded
  interactive report in the chat. Downloads retain their original bytes.
- GROMACS native-timing JSON summaries and existing plots/videos render inline;
  the installed structure viewer handles genuine output coordinates. No new
  simulation is required just to view results. Raw outputs remain downloadable.
- CPU GROMACS 2026.4 is on the environment-execution shell PATH for inspection,
  preparation and analysis. Simulations still use Scientific AI. The skill
  distinguishes duration-only TPR conversion from scientific reconstruction
  requiring complete sources and intent. See [preparation](gromacs-preparation-20261016.md).
- Optional mdprecheck still requires an offer before a new unchecked simulation.
  Neither a saved study nor a duration change silently bypasses that choice.

## Qualification

The actual existing System QA precheck report rendered in a real browser:
WARN, three warnings, 18 information findings, 28 embedded SVGs and an interactive
3D canvas. Its HTML/JSON downloads matched the original SHA-256 values. The
opaque-origin iframe allowed scripts needed by the report but could not access
the parent document; CSP blocked external report networking. Hard-refresh and
subsequent ordinary refresh passed without JavaScript errors.

Native CPU acceptance compiled a real 648-atom water TPR with `grompp`, no
`-maxwarn`; inspected, converted and compared the resulting files. Both exact
current platform GROMACS images read those CPU-generated TPRs successfully.
In an actual seeded QA-agent conversation, the agent created a 10 ns copy,
verified that only `nsteps` changed and left all 25 original fixture files
unchanged. It made no simulation/precheck submission and did not claim to
repair stereochemistry. The configured environment-execution MCP shell also
passed native acceptance on the existing operator client, without restart.

The actual QA agent recovered a completed 1 ns GROMACS operation through the
documented helper, verifying all 16 published artifacts and 15 native files.
Its canonical report rendered both real segment timing rows inline; unavailable
per-segment counts stayed unknown, while operation status independently confirmed
1 ns observed and durable. Genuine final coordinates rendered in the interactive
structure viewer. The original coordinate file and derived PDB both contained
18,916 atoms; the viewer excludes 12,419 hydrogens, accounting for its displayed
6,497-atom count. This is visualization, not scientific validation of the run.
The report download matched the generated source bytes. No new simulation was
submitted to recover, report or view the result.

Source checks include 74 Python progress/study/tooling/instruction tests and
26 combined Node contract tests on the pinned runtime. The image build also
executes the complete installed skill loader, browser-component tests and
branding/workspace verification. Host-only attempts lacking `typescript` or
`httpx2` are dependency failures, not substituted for the pinned-runtime results.
Separate backend evidence records real MD jobs and exact worker/API digests.

Actual completed-run chat recovery found two compatibility gaps in the migrated
API (the explicit published-result alias and typed native-result artifact),
and a missing native-report helper in the pinned client ancestor. The API now
preserves both contracts without changing scientific files, native provenance,
old manifests or work accounting. The final client explicitly installs the
report CLI and its verifier, and runs both CLI entry points at build time.
The intermediate image was not promoted as the new default while that gap
remained; recovery/report qualification reuses the same completed operation.

The final pulled image passed native preparation, installed skills, branding
and workspace verification. All 367 compiled UI files and progress adapters
match the qualified parent; entrypoint/environment/healthcheck and other runtime
configuration are unchanged. The combined image has twelve layers. Both serving
runtimes read TPRs generated from this exact final image, not just a local build.
The final installed report CLI also produced a complete two-segment report from
retained real output files; this offline packaging check is distinct from the
actual browser/agent qualification above.

## Existing-instance patch and rollback

**17 October correction:** the bridge/hard-refresh procedure below is historical.
Use [immutable asset delivery](client-assets-20261017.md) and ordinary reload;
all five retained clients now carry the inline viewer and that correction.

System QA and the reporting operator's existing endpoint were patched in place.
The API, supervisor and study-worker process identities remained unchanged;
the previously submitted study was neither canceled nor resubmitted. Other
managed clients are not implicitly upgraded by changing the default pointer.

For a no-restart patch, retain old static assets, instructions, skill files and
the GROMACS install receipt. The running Node API caches its index HTML, so the
patch includes a reversible old-entry JavaScript bridge to the new assets.
Use **Ctrl+Shift+R once** after activation. The older live API lacks the new
preview route; the UI handles that exact 404 through a bounded authenticated
workspace-file fallback. New-image instances use the normal preview route.
Do not restart Node to refresh HTML while the study supervisor has active work.

Instance patches are not persisted by provider VM recreation: select the pinned
default when recreating or reapply the retained patch after restoring client
state. Tool rollback restores the previous PATH command and keeps evidence;
static/instruction rollback uses the exact per-instance backup. It does not
delete chats, workspace inputs or scientific runs.

## Bounds and known follow-up

Physical repairs are not guaranteed from a TPR alone; reconstructed precheck
sources are not automatically equivalent originals. No throughput, scientific
convergence or all-agent-turn reliability claim follows from these tests.
At 1440×1200 the branded footer can intercept a new-chat Send-button click;
keyboard Enter worked. This separate existing interaction defect is retained in
Task Deck `fs2-librechat-composer-footer-hit-target-r20261016`, not hidden by the
successful preparation test.
