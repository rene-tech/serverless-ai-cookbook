# MD analysis candidate and Rene replacement preparation

Current outcome: the approved replacement and supported recovery completed;
the real-agent gate is **blocked by an upstream selected-model 404**. See
[the exact replacement result](MD_REPLACEMENT_RESULT_20260923.md). Preparation
notes below are historical, not the current deployment status.

The analysis image below is now the preserved base of the
[bounded polling successor](OPERATION_POLLING_20260923.md). Use successor digest
`81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d`
for the eventual replacement, after a matching dry run and explicit go. Earlier
analysis and migration-preparation evidence below remains historical, not relabeled.

Status at 18:29 UTC, 23 September 2026: **prepared; waiting for the parent's
explicit go**. No live endpoint was stopped, created, changed or deleted. This is
an additive CPU-analysis candidate, not a four-engine scientific or customer
readiness verdict.

## Exact candidate

- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:d074317715d911addafc4b27860eb8088e0ebce6bdd21fde1f4afacda22a1c03`.
- Candidate tag: `md-analysis-20260923-r1` (not the stable deployment default).
- Image source: `c9a1481f0d57d0ca6dd41041c56dc3f54e375c6e`;
  additive environment source commit `bbc92d5`.
- Exact parent image: `sha256:aac7719ca7efd9fcb8e8e5b3e367271b80ff76c61d65fe3a1ede44faf6774eb1`,
  source `d7f257c50dfa0daed1e82ab52b5091baa82e06da`.
- Local image config identity: `sha256:78265a115d92d19edf14ea990758976d46665f816c3819d01d7f8f163e8ba524`.

`Dockerfile.md-analysis` creates `/opt/md-analysis` with the existing Python
3.11.2. Seven requested packages and all 27 runtime distributions are pinned
with source/wheel hashes. ParmEd's source extension uses separately pinned
setuptools/wheel and disabled build isolation. No system package, global PATH,
shared scientific-client dependency or local MD engine is added/upgraded.
The existing FFmpeg/ffprobe is 5.1.9-0+deb12u1.

Only the shared native-MD reference and its hash inventory changed in the skill
bundle. The core manifest remains 2026.09.23.5. The actual installed LibreChat
loader verifies **83 skills, 77 resources and 75 core hashes**. Byte inventory
compared 70,872 protected filesystem entries across the scientific, clinical and
ClawBio environments, client helpers, workbench configuration and skill sources:
exactly those two intentional skill files differ. All 104 base layers and all
behavioral image configuration remain unchanged; seven layers are additive.

The first build attempted the source-only `bundle.py verify` against a mixed
installed core/ClawBio directory and correctly rejected extra extension folders.
Its log is retained. The corrected image uses the real installed skill loader
and core hash check, while the source-only bundle verifies separately.

## CPU evidence and its limits

Private evidence root:
`/home/tux/secure-handoff/fs2-md-engines-20260923/`.

- `client-md-analysis-r1-preservation-digest/receipt.json`: exact base/candidate
  byte and configuration comparison, SHA-256
  `f0d2cec562a6db5ef8df0b889c40d11055d3b7458eaeb9e1461791eebeb0691d`.
- `client-md-analysis-r1-real/run-02/receipt.json`: immutable-image CPU gate,
  SHA-256 `4a30db89d081a9c6cc392ed763b4dad25d8efac0aed4e5c88ee72245c6e40fbe`.
- `client-md-analysis-r1-real/run-02/analysis/receipt.json`: full real reader and
  analysis output, SHA-256
  `e0cfe071a329b3f1104446400c3877c7e9c139da33b97f974386a0841a5d78e8`.
- `client-md-analysis-r1-real/run-02/video/receipt.json`: actual AMBER MP4,
  SHA-256 `b4e051a10e883a74559e305f5e32c36f9af52a4d780e464685c874f21b51e827`.
- `client-md-analysis-r1-real/run-01/`: prior same-config image run with a
  GROMACS MP4; retained separately, not relabeled.

Each pass ran dependency imports, `pip check`, 54 common-analysis unit tests,
real ParmEd loading of the 6,598-atom/6,597-bond master, and netCDF4 checks over
all 1,000 AMBER frames. The frozen external common-analysis program read all
GROMACS XTC, NAMD DCD and AMBER NetCDF frames, checked actual native times/cells,
and produced RMSD/Rg/dihedral/thermodynamic outputs. Every source/raw input was
mounted read-only; network and GPUs were disabled. No new MD operation was
submitted. The external analysis source is evidence input, **not an installed
client pipeline**; its source hashes are in the receipt.

Both MP4s have 1,000 actual frames, H.264/yuv420p, 720×720, 40 fps and 25 s,
verified by ffprobe. Their midpoint previews were visually inspected. This is
renderer qualification, not a complete four-way video. The NAMD DCD reader
fixture deliberately retains the historical PME44 variant, explicitly labeled
in its spec; it is not the replacement PME64 protocol acceptance. LAMMPS's final
trajectory and all final common scientific gates remain the parent's separate
cohort. One nanosecond and readable files are not convergence evidence.

## Preserved account and stop-first boundary

The only replacement target is `aiendpoint-e00rxhvqkjfny2zkzy`, profile
`sandbox2`, project `project-e00rene`. It remains RUNNING on
`sha256:4155dd171ecb2e3c178695a66efe426c75ea8d219dfaceb8757735774dbe8a36`.
Do not operate on any other endpoint.

Latest successful preflight account export: `client-preflight-account-07`
(18:22:32 UTC); images: `client-preflight-assets-03`. They retain 12 conversations
and all messages, 306 paginated platform operations, eight seeded agents,
five images/2,536,895 bytes, account/profile/settings and workspace/study listings.
Projects, presets, favorites, tool favorites and active-skill selections are
empty. Clinical history is empty. One bucket-backed study is failed; no current
study is running. The profile matches the preserved seed configuration.

The agent list alone omits instructions. The updated exporter retrieves each
agent. All eight are view-only to Rene (expanded/edit GET returns 403), but the
permitted view GET includes their actual instructions, models and tools; these
are privately archived for post-restore comparison. The initial expanded-only
export `client-preflight-account-06` failed and is retained as incomplete.

Image hashes match the prior attachment archive exactly. A read-only check with
the configured Rene key confirms its platform bucket matches the existing
workspace mount. Existing MysteryBox selectors, seed account, platform key,
bucket, provider/model settings, port, networking and resource limits are copied
verbatim. Only the image and stop-first supervisor ownership mode change.

`client-replacement-dryrun-06/receipt.json` passed against the exact new digest,
SHA-256 `5a39cd0508e7e06696ea254cfe886e15e7d2ae808602fb41c6f1116385a244c0`.
It used the existing control-plane venv's Nebius SDK 0.6.10; no global SDK install.
The response is `dry_run:true`, `resource_id:""`, `bucket_changed:false`.

**Stopping Serverless destroys its ephemeral VM/root disk.** No full MongoDB or
disk backup is claimed. Do not attempt a Compute stop/image window or describe
restarting the old endpoint as database rollback. Supported conversation/image
import changes object IDs, preserves visible messages/tool content and remaps
attachments. Transient inline UI handles and arbitrary in-process execution
state do not migrate. The byte-exact original exports remain authoritative.
Platform operations and terminal study/workspace files persist in their existing
backend/bucket and must not be resubmitted or copied into another bucket.

## Commands after explicit go only

Use these from the client worktree. Refresh the account/assets into **new**
private directories immediately before the stop if there has been new activity;
rerun the dry run against that export. Check that no study is active and that
no other same-user bucket-writing supervisor is being introduced. These are
preconditions of this selected migration, not authorization to stop anything.

```bash
MD_SDK_PY=/home/tux/worktrees/fs2-gromacs-20260923/k8s-inference/components/control-plane/.venv/bin/python
MD_QUAL=templates/hcls-librechat/scripts/qualification
MD_PRIVATE=/home/tux/secure-handoff/fs2-md-engines-20260923
MD_BACKUP="$MD_PRIVATE/client-preflight-account-09"
MD_ASSETS="$MD_PRIVATE/client-preflight-assets-05"
MD_IMAGE=cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d
MD_UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
"$MD_SDK_PY" "$MD_QUAL/check_endpoint_storage_binding.py" --backup "$MD_BACKUP" --profile sandbox2
```

Only after the explicit go and complete final refresh:

```bash
nebius --profile sandbox2 ai endpoint stop --id aiendpoint-e00rxhvqkjfny2zkzy --async
# Read the exact endpoint state until STOPPED; do not create while it is running.
"$MD_SDK_PY" "$MD_QUAL/replace_endpoint.py" \
  --backup "$MD_BACKUP" --output "$MD_PRIVATE/client-replacement-create-01" \
  --image "$MD_IMAGE" --name scientific-ai-rene-md-20260923 --profile sandbox2 --create
```

Obtain the new ID from the private creation receipt and its HTTPS URL from the
actual endpoint status; do not guess it. After healthy startup, set `MD_NEW_URL`
to that URL and import once:

```bash
"$MD_SDK_PY" "$MD_QUAL/restore_endpoint_account.py" \
  --backup "$MD_BACKUP" --assets "$MD_ASSETS" --url "$MD_NEW_URL" \
  --output "$MD_PRIVATE/client-replacement-restore-01" \
  --profile sandbox2 --browser-user-agent "$MD_UA"
```

If interrupted, use the same output with `--resume` and
`--session-state .../browser-state-private.json`; do not repeatedly password-login
or discard import checkpoints. Capture the new account with the exporter, then
run `verify_restored_account.py --before "$MD_BACKUP" --after NEW_EXPORT
--restore .../client-replacement-restore-01 --output NEW_VALIDATION.json`.
It compares seed profile/agent instructions and settings, all original operation
IDs, terminal study identity/state, and the import verification receipt. Also
rerun the bucket-binding check against the new export. No old endpoint deletion
or global/stable-default promotion is included in this preparation.

If startup or restore fails, preserve the new private diagnostics and original
archives, report the exact failure and stop for coordination. Never run two
same-user supervisors. A recovery deployment from the old immutable image still
requires stop-first and supported account import, not an assumed disk rollback.

## Browser gate prepared, not yet run on a replacement

Use the installed Playwright wrapper via `bash` (its file is not executable).
`npx` and wrapper help, including `state-load`, were checked. Keep screenshots,
snapshots and traces private; never list cookies or emit credential values.

```bash
MD_PW=/home/tux/.codex/skills/playwright/scripts/playwright_cli.sh
bash "$MD_PW" -s=rene-md-final open "$MD_NEW_URL"
bash "$MD_PW" -s=rene-md-final state-load "$MD_PRIVATE/client-replacement-restore-01/browser-state-private.json"
bash "$MD_PW" -s=rene-md-final reload
bash "$MD_PW" -s=rene-md-final snapshot
bash "$MD_PW" -s=rene-md-final screenshot
bash "$MD_PW" -s=rene-md-final console error
```

Use fresh observed element references, not guessed selectors. Check desktop and
390×844 mobile layouts, the existing six research cards and six getting-started
examples, provider/key dialogs without submitting inference, the eight agents,
restored message/attachment views, and existing Workspace files/download hashes.
Confirm all four MD Apps through the ordinary Rene caller-scoped catalog. Check
actual `/opt/md-analysis/bin/python` via the environment-execution tool.

Then the parent's chosen real browser query can analyze already completed
results and show actual video/media links, with no duplicate MD submissions.
Record tool traces, actual outputs/download hashes, browser-console errors and
no unintended job admissions. Library imports, this dry run and local CPU clips
do not replace that browser/customer gate or the required unchanged final
scientific cohorts.
