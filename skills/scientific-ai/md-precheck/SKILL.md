---
name: md-precheck
description: Optionally check prepared GROMACS inputs before a new MD workload using the hosted mdprecheck App. Use for geometry, topology, chemistry, sequence-coverage and parameter checks, optional short CPU probes, or interpreting its JSON/HTML reports. Ask before executing unless the user already requested a precheck; never make it a mandatory simulation gate.
license: Apache-2.0
---

# MD input precheck

Read `scientific-gateway`. The hosted App is **mdprecheck**. It checks input
files; it does not run the production simulation, repair a system, or prove
scientific validity. The platform keeps the checker source private. Customers
do not need its repository, a local installation, or a GPU.

## Consent and reuse

For a **new prepared simulation workload** without a completed check, ask once:
“Would you like me to run mdprecheck on these inputs before starting GROMACS?”
Then end the turn and wait; do not queue or submit the simulation while asking.
A generic request to simulate, including a prepared saved study, is not consent
or refusal. A changed requested duration must be part of the new check's intent.
An explicit request to check inputs is already consent. If declined, continue
with the requested MD workflow; record the decision with that workload.
Advice, file inventory, and continuing the same checkpoint are not new workloads.

Use `lookup_mdprecheck` with the exact input reference and options to find an
earlier check. This is read-only and does not submit compute. A found pending
operation should be observed, not duplicated. Read the scientific result of a
completed operation; `warn` and `fail` still mean a check was performed.
Changed file bytes, scientific intent, selected files, probe options or checker
runtime need a new lookup/offer. Do not claim a prior check covers changed inputs.
Keep the result/operation ID in the workload's existing receipt directory.
Do not scan operation history or infer a match from filenames, timestamps or
input bytes alone. Use the exact lookup with **all requested options**, including
intent. An older report without the requested intent is not a substitute.
Cancelled, timed-out or infrastructure-failed attempts do not count as completed
checks; explain the failure and offer a retry. Never report them as a clean pass.

## Preferred LibreChat execution

After consent, use the [installed runner](scripts/run-precheck.py) for a workspace
bundle. It performs discovery, verified upload, exact lookup, safe admission
backoff, durable observation and report downloads through MCP. Do **not** redo
these steps as individual chat tools, scan history, or write a replacement client.

```sh
/opt/scientific-client/bin/python /app/skill/md-precheck/scripts/run-precheck.py \
  --file /workspace/md/inputs.tar.gz --input-format tar.gz \
  --coords conf.gro --top topol.top --mdp md.mdp \
  --output-dir /workspace/md/precheck --idempotency-key md-precheck-001
```

Use actual file names; omit optional selectors if unknown. Add one `--intent`
per supplied intent, e.g. `--intent stage=production --intent length_ns=1`.
Add `--probes grompp energy minimize stability` only if requested. Other schema
fields have corresponding flags; consult `--help`, not the source code.
Omit the runner's `--wait-seconds` to use its default; unlike the direct MCP
submit tool, this observer does not accept zero. Do not invent CLI examples.
Observe the same execution with `read_execution`. Its `delivery.json` supplies
the exact operation, scientific verdict and verified report links. Report only
that delivery; **never substitute older reports** while waiting for admission.
If the bounded observer exits while queued/running, resume the identical command
and output directory. Do not change inputs, keys, scientific options or accounts.
An admission rejection means not checked yet, not permission to reuse a mismatch.

Other MCP/API clients can follow the manual contract below.

## Prepare and invoke

1. Read `get_model_schema(model_id="mdprecheck", protocol="native", tool_name="run_mdprecheck")`; use the deployed bounds and
   typed `run_mdprecheck` contract. Missing authorization is not permission to
   use an administrator key. Report unavailability and let MD proceed if desired.
2. Bundle the prepared coordinates, topology **and all includes**, MDP, optional
   index, reference FASTA and workflow JSON. Use the deterministic GROMACS
   `scripts/make-input-bundle.py` helper. Tar, tar.gz and zip are supported;
   a standalone TPR can also be checked, but source-only checks/probes are limited.
   Inputs remain unchanged. The current limit is 4 GiB uploaded / 16 GiB unpacked.
3. Upload through the existing trusted file helper. For a gzip tar, use
   `application/gzip` and **compression none**: the bytes are an archive, not
   the compressed scientific-manifest transport used by GROMACS submissions.
   Save the finalized artifact reference; never invent hashes or artifact IDs.

   ```sh
   /opt/scientific-client/bin/python /opt/bionemo/upload-artifact.py \
     --model mdprecheck --file /workspace/md/inputs.tar.gz \
     --media-type application/gzip --compression none \
     --output-dir /workspace/md/precheck-upload --idempotency-key md-precheck-upload-01
   ```

4. Pass the finalized reference as `input`, and `input_format: "tar.gz"`.
   Optional `coords`, `top`, `mdp`, `ndx`, `tpr`, `fasta`, `workflow` select
   relative files inside the archive. Include `intent`, e.g. `["dt=0.002",
   "length_ns=100", "stage=production"]`, when provided by the user. Do not
   invent reference sequences or silently fetch private data from another service.
5. Lookup first; with consent, call `run_mdprecheck` with a stable idempotency
   key and `wait_seconds: 0`. Static checks are the default. If requested,
   `probes` may include `grompp`, `energy`, `minimize`, `stability`; these use
   CPU and require original sources. Default probe length is 5,000 steps,
   maximum 100,000; this is not the production duration. Overall limit: 30 min.
6. Poll `get_scientific_status`, then `get_scientific_result`. Download the
   returned `artifacts.json` and `artifacts.html` with the trusted artifact
   tools, preserving checksums. Return the verified workspace HTML link so
   LibreChat renders its inline report viewer; never paste the HTML into chat.

If the client cannot discover `run_mdprecheck` or `lookup_mdprecheck`, refresh
the MCP connection once. Do not repeatedly search for guessed tools. The
documented REST path remains available with the same caller key; otherwise
report the missing client tool instead of claiming that a different old result
satisfies the requested check. The installed native invocation helper accepts
the finalized artifact **object**, not a workspace filename, as `input`.

## Interpret honestly

Distinguish operation success from the check's scientific `status`. Summarize
failures/warnings, which checks were skipped, missing reference sequences, and
whether optional probes actually ran. Show the report inside the session via
its verified workspace HTML link, retaining the full HTML/JSON downloads. An
existing completed report can be displayed without rerunning the check.
Never hide failed checks, describe unrun probes as passed, or automatically
change timestep/force field/coordinates to obtain a green result. Ask about
scientific changes, then check the changed workload if the user wants that.

mdprecheck complements native `grompp`; it does not justify `-maxwarn` or replace
domain review. A TPR-only check cannot recover every source-level assumption.
No GPU snapshot is needed for this CPU-only input-checking App.

For non-MCP integration, see [REST usage](references/api.md).
