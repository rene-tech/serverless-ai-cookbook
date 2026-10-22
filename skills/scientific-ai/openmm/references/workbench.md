# OpenMM: submit once, recover and render

For a new run, reuse the [durable MD study template](../../gromacs/references/timing-study.md).
Change its model/tool/entry/semantic type to `openmm`,
`submit_openmm_workflow`, `openmm-inputs`, `openmm-input-bundle/v1`, and retain
the scientist's real source archive and parameters. Do not copy its three-repeat
example: omit `expected_repeats` unless intentionally checking dynamics-step IDs.
OpenMM's final coordinate output is **`final-structure-1.cif`**, not `.pdb`;
declare that filename in analysis outputs and deliverables. The installed
`/opt/bionemo/native_md_preview.py` produces the report and interactive 3D view.
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

Use a new **analysis-only** `scientific-workflow/v2` study, with the existing
`python-script` method and these arguments (choose actual, unused paths):

```json
{
  "script": "/workspace/openmm/preview-native-md.py",
  "inputs": [{"name": "native_manifest", "file": "/workspace/openmm/recovered/native-files.json"}],
  "parameters": {"structure_preview": true},
  "outputs": ["native-timing-report.json", "native-timings.csv", "native-timing-report.md", "md-structure-preview.html", "md-structure-preview.json", "final-structure-1.cif"]
}
```

Declare the HTML and Markdown files as `report` deliverables, CIF as `support`,
CSV as `metrics`, and JSON as `provenance`. This is one native job; for multiple
jobs declare their actual `final-structure-N.cif` outputs (maximum four views).
The durable study publishes and verifies those files without another simulation.
Deliver the completed study's actual workspace report links inline, using
`deliver_scientific_results` when answering from existing files. A raw CIF dump
or download-only link is **not** the requested inline report. The 3D view is a
final frame, not a trajectory movie or proof of convergence. Report measured
ns/day and elapsed phases; do not narrate backend GPU, image or snapshot details.
