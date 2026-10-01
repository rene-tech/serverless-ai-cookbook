# Lynx workflow instruction replay — 1 October 2026

Historical investigation. The later **general-purpose** packaging, deployment
and broader tests are in [the shared OpenFF release report](general-openff-release-20261001.md).
The local-only and missing-installed-runtime statements below describe this
earlier experiment, not the new image. No customer-specific fork was created.

## Decision and release scope

**Candidate only; production is unchanged.** The primary-agent instruction
rewrite, dedicated OpenFF skill and deterministic helpers are implemented and
tested locally. The OpenFF execution replay now delivers verified ligand files.
No tested conversational configuration has yet passed all three scientific
answer checks: unsupported structural/force-field interpretation remains.
Do not represent this as a customer release or silently change the live model.

The user requested rewriting instructions, testing the customer's collected
workflow, and comparing alternative models (possibly “Ripple”). Ripple's exact
product/model identifier was requested but has not been supplied. It was not tested.

Repository: `rene-tech/serverless-ai-cookbook`, branch
`agent/scientific-ai-client-general-20260920`. Changes are local, not published.
The pre-existing Kopra registration files are unrelated and untouched.

## What changed

- One primary instruction source, `agent-instructions.md`, used by both seeding
  and endpoint rendering. About **7,800 characters**, versus 76,473 in the live
  incident agent. Explain, inspect and execute are distinct request modes.
- Detailed domain procedures load as skills rather than being appended to every
  turn. Specialized tutorial agents retain their existing instructions; this
  test does not qualify them or every other scientific workflow.
- GROMACS advice routes to a short compatibility reference. A dedicated `openff`
  skill handles CPU ligand preparation, dependencies, charge assignment, export,
  actual completion and validation limits. The skill is not a new model App.
- `inspect-mmcif.py` reports coordinate facts using Gemmi, distinguishes author
  numbering from label sequence coverage, and does not infer receptor loops.
- `prepare-openff.py` parameterizes a standalone SMILES ligand with CPU
  RDKit/AmberTools AM1-BCC and an explicit Sage version. It preserves charges on
  later failure, exports actual GROMACS files and verifies output readback hashes.
- The replay harness submits through the real isolated LibreChat agent API,
  observes durable generation state, retains private evidence and distinguishes
  provider errors, empty answers, watchdog termination and scientific acceptance.

The optional OpenFF environment is **not installed in the production image**.
The Dockerfile packages the helper, not the coordinated conda environment. The
new skill explicitly reports a missing `/opt/openff/bin/python` rather than
installing packages inside a customer chat. `openff/environment.yml` records the
candidate package versions; a publishable runtime still needs a resolved lock,
image build and exact-release qualification.

## Replay method and privacy

The three inputs are the customer's original CIF inventory, force-field advice
and OpenFF parameterization prompts, with a hash-verified read-only copy of their
actual CIF. Customer conversation text, SMILES, files, credentials and generated
results remain outside Git:

`/home/tux/secure-handoff/fs2-lynx-onboarding-20260929/instruction-replay-20261001/`

Candidate container: `fs2-lynx-instruction-replay-20261001`, localhost port 13085,
4 CPUs, 8 GiB RAM, **no GPU**, private local workspace rather than the live bucket.
Base image:
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d`.
Source files and skill changes were mounted/copied into this candidate; a new
release image was not built. No cloud instance, endpoint, tenant, key, bucket or
GPU job was created. Actual Token Factory inference was used for the chat replays.

The tests exercise the real agent-server, MCP tools and file outputs, **not a
browser UI**. They do not qualify browser reconnect, the raw-JSON presentation
complaint, production bucket semantics or unrelated Apps. HTTP health alone is
not treated as a customer acceptance pass.

## Observed results

Historical incident: the original GLM agent spent approximately 122 minutes on
the CIF task without delivering an answer; its nine tool calls totalled about
3.1 seconds. This is incident evidence, not a controlled latency baseline.

Exploratory comparisons used evolving instruction revisions, so the following
are observations, **not a same-prompt statistically controlled ranking**:

| Configuration | Observed completion time | Quality finding |
|---|---|---|
| GLM-5.3-Flash, no explicit effort | CIF stopped at 180 s twice; advice ended around 150 s without an answer | Failed completion |
| GLM-5.3-Flash, explicit `low` | CIF 9–12 s; advice 15–18 s | Faster, but factual/API errors; OpenFF did not execute successfully |
| Qwen3-235B-A22B-Instruct-2507 | Revised CIF 21 s; advice 9–15 s | Unsupported completeness/structural claims; attempted package installation in the missing-dependency case |
| GPT OSS 120B, valid configured calls | CIF and advice about 12.6 s each | Invented structural assignments, invalid OpenFF export APIs and compatibility advice |
| Kimi K3, final candidate | CIF 9.1 s; advice 21.1 s; OpenFF **114.3 s** | OpenFF completed correctly; narrative structural/parameter-quality overclaims remain |
| DeepSeek V4 Pro, final candidate | CIF 21.1 s; advice 12.1 s | Invented chain/domain interpretation and overconfident compatibility advice; OpenFF not tested |

Examples of rejected answer claims: identifying unmodeled sequence ranges as
specific receptor loops without an alignment; calling scFv a nanobody; inferring
all atoms are complete; saying Sage parameters automatically match CHARMM;
claiming that no molecule-specific torsion validation is needed. Nonempty prose
and fast completion do not make those passes.

The final candidate core hash (stripped text) is
`9707e2f34811c636b24e1598b6d440dbc77a9c23ec5f6094a72a2262d79405b4`.
Private cohort directories include `final-kimi-r1`, `final-deepseek-r1` and
`final-kimi-missing-env`; earlier revisions are retained for diagnosis.

### Important experimental corrections

- The first GPT OSS attempts were rejected by the client's model allowlist.
  Their three-second responses are **configuration failures**, not model speed
  results. Error extraction was fixed and regression-tested before valid replays.
- Earlier missing-dependency tests caught Qwen/Kimi trying to install packages
  in the isolated container. These were failures, not accepted fixes. They changed
  the local environment; subsequent OpenFF tests are explicitly the
  **environment-available** condition, not the original clean-image condition.
- Early cohorts reused model/case output prefixes. Their apparent artifacts
  cannot establish independent clean completion. The harness now allocates a
  unique cohort prefix; the final successful OpenFF replay used that new prefix
  and was independently checked.
- Polling is at three-second intervals. Reported agent wall times include
  observation latency. Tool time is not GPU time; LibreChat token counts are
  not treated as provider billing evidence. `scientific_pass` is not inferred
  automatically from transport success.
- The last dependency probe removed only the canonical interpreter symlink,
  **not the installed runtime**. Kimi found the alternate path, contrary to the
  skill's prescribed path check, and started the CPU helper. Its chat was stopped
  by the 90-second probe watchdog; the original CPU execution subsequently
  completed successfully and was not resubmitted. This is neither a valid
  clean-image missing-dependency pass nor a model inference timeout. A truly
  dependency-free image test remains outstanding.

## OpenFF CPU evidence

The checked helper ran the customer's exact molecule on **CPU only** in
**92.1 seconds**, including **87.4 seconds** for AmberTools AM1-BCC. The Kimi
agent then used the same helper through the MCP execution tool and finished in
**114.3 seconds**, with approximately 92 seconds in the actual preparation job.

Measured outputs: 78 atoms, neutral charge sum within floating-point tolerance,
Sage `openff-2.2.1.offxml`, GROMACS `.top`/`.gro`, force-field definition, SDF,
per-atom charge JSON, OpenMM System XML, provenance and a hash manifest. Actual
versions: Toolkit 0.18.0, Interchange 0.5.2, forcefields 2026.01.0, AmberTools 26.0,
OpenMM 8.6.1 and RDKit 2026.03.1. Early conversational version claims were not
used as authoritative evidence; the helper reads installed package metadata.

Independent checks passed for both the operator-produced bundle and the
agent-produced bundle: byte hashes/sizes, isomeric molecular identity from SDF,
GRO/SDF/topology atom count, topology partial charges versus the saved assignment,
neutral total charge and finite CPU reference energy. Negative checks reject
undefined stereochemistry and preserve existing output directories.

This is **not** a protein/membrane system or a GROMACS simulation validation.
The export uses a documented artificial empty box with 1 nm padding. `grompp`,
matched-engine energy/force agreement and scientific accuracy/convergence have
not been tested. The Toolkit-default conformer seed is not represented as a
caller-selected seed. No GPU or GPU snapshot is needed for this preparation.

Primary references:
[OpenFF installation](https://docs.openforcefield.org/en/latest/install.html),
[Interchange export example](https://docs.openforcefield.org/en/latest/examples/openforcefield/openff-toolkit/using_smirnoff_in_amber_or_gromacs/export_with_interchange.html),
[GROMACS export limitations](https://docs.openforcefield.org/projects/interchange/en/stable/using/edges.html).

## Verification and remaining release work

Passed: 31 repository tests (bundle, instruction seeding/rendering, transport
error handling and existing GROMACS bundling), six mmCIF tests, three OpenFF
integration checks against real outputs, JavaScript syntax checks, both skill
validators and checksummed bundle verification. These are different layers of
evidence, not a claim of complete platform coverage.

Before a customer rollout:

1. Keep the OpenFF skill and checked helper; build the optional CPU environment
   reproducibly and qualify the exact deployment image. Test the missing-runtime
   response as well as actual output delivery through the customer's UI/storage.
2. Do not change the global conversational default based solely on speed. Kimi
   is a promising execution candidate, but unsupported scientific interpretation
   in the CIF/advice responses remains an acceptance failure. Consider presenting
   deterministic inventory output directly rather than asking an LLM to invent
   extra interpretation; that UI change is not implemented by this task.
3. Replay existing non-MD workflows before globally replacing their instruction
   source; only the three collected customer tasks were exercised here.
4. Obtain the exact Ripple identifier before making a meaningful comparison.

Customer files, the live shared Lynx instance, its selected model, logins and API
key were not changed. No production readiness claim or deployment notification
was sent to the customer.

The task-owned candidate container was **stopped after testing**. It was not
deleted. Verified operator/agent OpenFF bundles and execution receipts were
copied to the private evidence directory's `retained/` folder before shutdown;
the original conversation receipts and source changes remain available.
