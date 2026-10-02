# Kimi default and Rene demo, October 2

Status: selected default for new deployments; Rene's new demo is running.
Two unchanged hosted cohorts passed technical delivery. This is scoped workflow
qualification, not approval of arbitrary scientific advice or production protocols.

The owner explicitly approved changing the conversational default, promoting the
improved image, and creating a new Rene demo. This is not permission to replace
Lynx, Rene's existing instance, or any other customer's local chat database.

## Exact release

- Runtime source: `3520408d87ef197a6f7b414dfc64317e7a19d9a7`.
- Tag: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:general-kimi-20261002-r1`.
- Registry digest: `sha256:e96a66501807a2c446c17413f66c042b4a6ae2bdee2c32b9b05adcd1d378fd63`.
- Image configuration: `sha256:25d31897c07832f2e8be606105daaea2abe5417874b8f6d9da5fc3d1f127f0c6`.
- Fixed R10 base, 123 layers; bundled skills version `2026.10.01.6`.
- Token Factory `moonshotai/Kimi-K3`, high reasoning, 131072 context, 16384 output.
- 90-second invocation deadline, 300-second accumulated model budget, two
  unchanged repeat rounds. Execution and scientific-job observation are separate.

There is no automatic model fallback and no change to the gateway's App models,
API limits, customer capacity or workflow-specific patient/clinician/judge choices.
The current improvements complete compound outputs before final delivery, retain
measured reports unchanged, and support bounded observation of long scientific
jobs without mistaking pending work for a tool loop. Empty model output receives
one bounded retry, then a visible incomplete-work result rather than endless thought.

## Evidence

Offline checks on this exact image: 38 Node/installed-graph tests, eight Gemmi
tests, and 121 installed MCP/polling/recovery/artifact tests passed without skips.
Separately, 70 source/configuration/deployment tests passed.

Private evidence and credential-free qualification scripts are retained under
`/home/tux/secure-handoff/fs2-kimi-default-rene-20261002/`. Secret values are never
included in the image or committed receipts. Hosted qualification must use the
actual seeded agent without model, reasoning, context or instruction overrides.
Previous comparison-agent results do not count as a clean cohort for this default.

Both actual seeded-agent cohorts passed **13/13 technical-delivery cases** on the
public HTTPS endpoint, with no modified prompts in the system instructions,
model overrides, failed tool calls, empty replies, watchdog aborts or transport
warnings. The user prompts differ only in run-specific output directories and
public fixture paths. Each cohort used two replay workers; the second began while
the first cohort's last GPU job was completing. This is not a capacity benchmark.

Coverage: ligand advice and compatibility questions; measured mmCIF inventory;
inventory plus downloadable CSV; FASTA analysis; summary CSV plus error-bar PNG;
charged methylammonium and the original 20-hydroxyecdysone OpenFF preparation;
undefined-stereochemistry clarification without execution; bounded interpretation
advice; caller-authorized catalog; and a new hosted GROMACS starter run. The
customer-private GPCR CIF was not copied into Rene's bucket: inventory used public
1UBQ. The original private-input comparison remains in the earlier evidence.

| Workflow | Cohort 1 | Cohort 2 |
|---|---:|---:|
| mmCIF inventory | 3.6 s | 3.7 s |
| Inventory plus CSV | 9.9 s | 12.9 s |
| CSV plus error-bar plot | 9.8 s | 13.0 s |
| Charged OpenFF ligand | 12.8 s | 12.9 s |
| 20-hydroxyecdysone OpenFF | 46.9 s | 46.9 s |
| GROMACS starter, including delivery | 124.3 s | 121.1 s |

These are end-to-end case observations, not controlled model-only benchmarks.
The two cohorts made 70 tool calls. All 324 output objects were independently
downloaded through authenticated HTTP and S3 and matched byte-for-byte. All 69
delivered file/directory links resolved. Independent installed OpenFF validation
checked exported molecular identity, stereochemistry, coordinates, atom counts,
partial charges, charge sums and manifest hashes for both molecules in both
cohorts (five tests per completed export, no skips). Native GROMACS filenames,
artifact hashes and operation receipts were checked independently.

GROMACS operations: `53c8c39d-2e89-4f7b-a437-ec9195723a0c` and
`13725851-b958-41cf-a5ee-6ebce51bda55`. Both are the packaged minimization plus
20 ps NVT, 20 ps NPT and 20 ps production protocol, not new force-field validation.
CSV checks retained the missing-base GC result as undefined; the assay means
were 2 and 5 with sample standard deviations 1 and 2. The error-bar plot matched.

Real browser checks covered existing-account login, branding, a fresh compound
inventory/CSV request, Workspace navigation and a downloaded file independently
matched against S3. A browser-initiated GROMACS job was reloaded while running;
the UI resumed the same job and operation instead of submitting again. See the
private browser evidence and sanitized JSON receipt for the completion record.
That additional browser job completed as operation
`ef9cf6ba-8c33-492c-9e4c-8ce0cab1b1f7`, retaining execution job
`4da1f28d-096c-44a8-8e39-344b904cf5d6` across reload and delivering the native
report/links without a follow-up prompt. Its output is separate from both cohorts.

## Deployment and preservation

The requested demo is `scientific-ai-rene-kimi-demo-20261002`, endpoint
`aiendpoint-e00rjnvvypkqgsq1y1`, in the existing Rene project. It reuses the source
endpoint's login-secret reference, Token Factory/Tavily/platform credentials and
S3 mount. No tenant, user, API key, bucket or quota was created or changed.
It uses a fresh local chat database; existing conversations remain on the original
instance. Both can stay running without two supervisors adopting the same study:
the demo has the distinct stable namespace `SCIENTIFIC_STUDY_OWNER=rene-demo-20261002`.
Shared bucket files are still shared. Retain this demo until the owner retires it.

URL: `https://port3080-pm6wszf23fwxqzp.tunnel.applications.eu-north1.nebius.cloud`.
Sign in as `rene@nebius.com` with the existing password. This instance is not a
clone of prior conversation history. Test conversations and reproducible outputs
are intentionally retained; public/synthetic inputs use the task-specific
`runs/fs2-kimi-default-rene-20261002/` prefix, and cohort outputs use recorded
`replays/<cohort>/` prefixes. No customer-private Lynx structure was copied.

`scripts/deploy-workbench-preview.py` validates existing bindings, performs a
provider dry-run, and records private creation evidence. It never stops or changes
the source. Use it only for an explicitly requested parallel preview, not routine
QA proliferation. Normal development uses the system identity and run prefixes.

## Qualification boundary

This release targets agent completion and usable files for the tested workflows.
It is not an unattended scientific adviser, an all-App qualification, a capacity
measurement, or evidence that an arbitrary molecular-dynamics protocol is valid.
Short packaged MD runs demonstrate transport/execution/delivery, not equilibration
or convergence. Human scientists must review force-field compatibility, protocol
selection and interpretation. Do not claim the original Lynx production GPCR
workflow is validated without its complete input bundle and a separate acceptance.

In particular, the held-out free-form interpretation reply still overstated what
finite energies establish and guessed sampling timescales without analyzing the
trajectories. A compatibility reply overstated what convention checks alone
prove. One progress sentence switched to German despite an English prompt.
These are retained limitations, not silently counted as scientific correctness.
Measured inventory/chemistry/native-MD delivery uses the verified factual cards;
there is no comparable guarantee for arbitrary advisory prose. Kimi improves
completion on these workflows, but model choice is not scientific validation.

Existing customer instances do not auto-upgrade when `release-image.sh` changes.
Before any later replacement, preserve account state, chats, uploads, credentials
and bucket bindings. A Serverless stop destroys its local disk; it is not rollback.

Subsequent explicitly authorized migration: [Lynx, October 2](lynx-kimi-migration-20261002.md).
That report preserves its full account-state restore evidence and one recovered
Gemmi command error in the customer-input cohort; do not equate it with a clean
all-workflows qualification or silently inherit the public-fixture result above.
