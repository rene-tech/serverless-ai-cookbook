# OpenMM: submit once, recover and render

For a new run, reuse the [durable MD study template](../../gromacs/references/timing-study.md).
Change its model/tool/entry/semantic type to `openmm`,
`submit_openmm_workflow`, `openmm-inputs`, `openmm-input-bundle/v1`, and retain
the scientist's real source archive and parameters. Do not copy its three-repeat
example: omit `expected_repeats` unless intentionally checking dynamics-step IDs.
OpenMM's final coordinate output is **`final-structure-1.cif`**, not `.pdb`;
declare that filename in analysis outputs and deliverables. The installed
`/opt/bionemo/native_md_preview.py` produces `native-md-report.html` with
observed scientific fields, explicit unknowns and the interactive final-frame
view. The separate `md-structure-preview.html` is only a coordinate preview,
not a substitute for the requested report. Check any additional requested
analysis against the helper's scope and add it or explicitly report missing evidence.
Copy that script into the workspace before the study freezes it.

If an operation already succeeded, **do not add a batch/model phase** just
because its report failed. Recover its verified outputs into a new folder:

```bash
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --recover-operation-id EXISTING_OPERATION_ID \
  --output /workspace/openmm/recovered
```

This is read-only: no model/source/parameters/key argument is needed. It creates
`recovery-receipt.json` and `native-files.json`; the outer `result.json` is not
the native manifest. Do not rename receipts or modify the previous failed study.
Load `operation_id` from that verified receipt when constructing titles or links;
the report helper copies it directly. Use a descriptive title without an ID if
it cannot be copied reliably; never reconstruct one from memory.

Use a new **analysis-only** `scientific-workflow/v2` study, with the existing
`python-script` method and these arguments (choose actual, unused paths):

```json
{
  "script": "/workspace/openmm/preview-native-md.py",
  "inputs": [{"name": "native_manifest", "file": "/workspace/openmm/recovered/native-files.json"}],
  "parameters": {"structure_preview": true},
  "outputs": ["native-md-report.html", "native-timing-report.json", "native-timings.csv", "native-timing-report.md", "md-structure-preview.html", "md-structure-preview.json", "final-structure-1.cif"]
}
```

Declare `native-md-report.html` as the primary `report` deliverable, the separate
preview as optional `support`, Markdown as a supporting `report`, CIF as `support`,
CSV as `metrics`, and JSON as `provenance`. This is one native job; for multiple
jobs declare their actual `final-structure-N.cif` outputs (maximum four views).
The durable study publishes and verifies those files without another simulation.
Deliver the completed study's actual workspace report links inline, using
`deliver_scientific_results` when answering from existing files. A raw CIF dump
or download-only link is **not** the requested inline report. The 3D view is a
final frame, not a trajectory movie or proof of convergence. Report measured
ns/day and elapsed phases; do not narrate backend GPU, image or snapshot details.
The summary distinguishes completed segment work and cumulative simulation time,
last sampled temperature (with its step/time), integration, engine setup and
command wall time. Queue, worker startup and total elapsed remain unknown when
the verified native evidence does not measure them. Inspect the finished HTML
and reconcile every requested section before declaring the request complete.
