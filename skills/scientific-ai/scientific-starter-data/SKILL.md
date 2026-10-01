---
name: scientific-starter-data
description: Find and use the customer's installed scientific starter datasets, model recipes and provenance manifest from their workspace without inventing paths or substituting demo data for a user's experiment.
license: Apache-2.0
---

# Starter data

Use `scientific-gateway` for model contracts. Discover the actual workspace root
and starter manifest with the client file tools; don't assume a historical
tenant, bucket name or seed-pack version. If absent, explain how the operator can
seed it, rather than inventing files or copying another tenant's artifacts.

Read the pack README/index and only the selected recipe. Record source/license,
pack version, input paths and hashes. Check that the caller's live catalog still
exposes the recipe's App and that its current schema matches the recipe. A
catalog addition does not guarantee a starter fixture exists yet.

For an example run, explain that these are demo/reference inputs. Preserve the
original fixtures and write outputs into a new caller-owned study directory.
Never replace user-supplied data with a fixture to obtain a passing response.
Use the durable file clients; local paths are not already-finalized artifacts.

## Molecular-dynamics examples in the hosted workbench

When the workbench exposes `run_starter_example_mcp_environment-execution`, use
it for a requested existing MD example: give `case_directory`, the selected
`model`, and a new `output_directory`. It performs the manifest/hash/recipe
checks below and passes unchanged inputs to the existing batch client. Follow
its job ID with `read_execution`, then use `deliver_scientific_results` with
`kind: native-md` and the returned output directory. Do not search unrelated
historical runs or reconstruct the submission in a shell. Custom protocols and
additional scientific analyses still use the relevant engine/workflow skill.
The following CLI procedure is for clients without that typed launcher.

The pack README's `run-example.py` assumes downloaded POSIX files. Do not run
that script directly on the `/workspace` Object Storage mount, or install a
new Python environment inside a chat. Use the already installed, bucket-aware
scientific-batch client from `gromacs`, `amber`, `namd` or `lammps` instead.
This changes artifact transport, not the native simulation protocol.

Read the chosen case's `recipes.json`, the engine's `parameters.json` and
`input-manifest.template.json`. Verify their bytes and `input.tar.gz` against
the pack's `manifest.json` (`objects`: `path`, `sha256`, `size_bytes`). Keep the
native archive and parameter JSON unchanged. Resolve the selected recipe's
`model_id`, `tool_name`, `arguments.operation`, `arguments.service_class`, and
the manifest entry's name, semantic type, media type and compression against
the live model schema. Do not pass the entire recipe/request envelope as the
parameters document.

For the existing v3 GROMACS alanine examples, after those checks, use:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model gromacs --tool submit_gromacs_workflow --operation run-workflow \
  --source /workspace/examples/v3/molecular-dynamics/alanine-quickstart/gromacs/input.tar.gz \
  --parameters /workspace/examples/v3/molecular-dynamics/alanine-quickstart/gromacs/parameters.json \
  --entry-name gromacs-inputs --semantic-type gromacs-input-bundle/v1 \
  --media-type application/x-tar --compression gzip \
  --output /workspace/studies/CHOSEN_NEW_STUDY \
  --idempotency-key CHOSEN_STABLE_ID --display-name 'Alanine introductory run'
```

Choose a new output directory and stable idempotency identity once. Adapt only
the paths and discovered transport metadata for other installed cases/engines.
Use `execute_command` and follow its durable execution identity. The client
checks the live schema, retains admission state, and streams hash-verified
results back to the bucket using local seekable staging. The client also writes
verified native filenames under `native/result-00/` (one directory per result),
with exact byte hashes and authenticated workspace links in `native-files.json`.
Use the returned `native_outputs` directory/link and that manifest. Do not rename
`output-NN.artifact`, reconstruct mappings by array position, base64-encode links,
or rewrite the native files. The transport order is not the engine's file order.
Do not rerun the simulation to recover a file.

If an earlier runner already completed the operation but could not save files:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --recover-operation-id EXISTING_OPERATION_ID \
  --output /workspace/studies/NEW_RECOVERY_DIRECTORY
```

This performs reads only, verifies every artifact and writes a recovery receipt.
Keep the original failed directory and operation identity for diagnosis. Report
native execution checks and the pack's sampling limitations separately from
successful transport; the introductory run is not converged scientific sampling.

If a reference result is included, check whether it is measured or illustrative,
and match its exact inputs/model/options before comparing. Fixture availability,
schema acceptance and scientific reproduction are three different claims.
