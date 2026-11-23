---
name: runai-boltz2-reference
description: Run the Scientific AI Boltz 2.2.1 reference structure workflow from Nextflow and verify its owner artifact.
license: Apache-2.0
---

# Boltz 2.2.1 reference structures

## Predict

Discover the authorized `boltz2-reference` model and its `predict` workflow
before running it. The service supplies the chosen public reference protein.
The [versioned request](request.json) selects `1UBQ`. Set `reference` to
`1L2Y` in your own copy to choose Trp-cage.

Install the checked Scientific AI skills bundle. Use Nextflow 26.10.7 and
Python 3. Export `SCIENTIFIC_AI_URL` for your service origin and
`SCIENTIFIC_AI_TOKEN_FILE` for your approved rotating token file. Set
`SCIENTIFIC_AI_SKILLS_DIR` to the installed skills directory and
`SCIENTIFIC_AI_WORK_DIR` to a work directory in your own storage. Use a distinct
stable `SCIENTIFIC_AI_SUBMISSION_KEY` per logical submission. Run from a
launch directory in your own storage.

```sh
nextflow run "$SCIENTIFIC_AI_SKILLS_DIR/runai-scientific-gateway/nextflow/v1/main.nf" \
  --request "$SCIENTIFIC_AI_SKILLS_DIR/runai-boltz2-reference/request.json" \
  --service_url "$SCIENTIFIC_AI_URL" --submission_key "$SCIENTIFIC_AI_SUBMISSION_KEY" \
  -work-dir "$SCIENTIFIC_AI_WORK_DIR"
```

Keep the task cache and work directory in your storage. Use `-resume` with the
same request, key and work directory to reuse completed results or reattach to
an admitted run after restarting the wrapper. The stage emits the run ID,
its verified manifest and exactly one `data/result.json` file. The result
contains the reference ID and the predicted structure as mmCIF text.

To stop a queued run, call the same version’s `client.py cancel` with the
stage’s `sciai-run-id.txt`. An in-flight inference returns HTTP 409 and
continues to its terminal state.
