# Molecular dynamics from a laptop

Install the separate `scientific-ai-client` archive and its Python dependencies
using the client archive's `README.md` or the skill's `portable-client.md`.
The commands below run
inside that directory, with `SCIENTIFIC_MODELS_MCP_URL` and
`SCIENTIFIC_MODELS_API_KEY` supplied through your environment. No LibreChat or
`/opt/bionemo` installation is required.

Choose an existing example from your own bucket or local files. Read its
`recipes.json`, engine `parameters.json`, `input-manifest.template.json` and
starter `manifest.json`; verify the selected bytes and hashes. Preserve the
native protocol and paths inside `input.tar.gz`. A local `$file` or `$manifest`
recipe placeholder is not a finalized artifact reference.

## Submit the selected recipe

Discover the model and exact named tool first. The ordinary MD tools accept a
gzip-compressed tar containing all coordinates, topology/include files and
native inputs referenced by `parameters.json`, with their relative paths intact.
They do not strip an extra enclosing archive directory.

| Model | Typed tool | Manifest entry | Recommended semantic type |
| --- | --- | --- | --- |
| `gromacs` | `submit_gromacs_workflow` | `gromacs-inputs` | `gromacs-input-bundle/v1` |
| `amber` | `submit_amber_workflow` | `amber-inputs` | `amber-input-bundle/v1` |
| `namd` | `submit_namd_workflow` | `namd-inputs` | `namd-input-bundle/v1` |
| `lammps` | `submit_lammps_workflow` | `lammps-inputs` | `lammps-input-bundle/v1` |
| `openmm` | `submit_openmm_workflow` | `openmm-inputs` | `openmm-input-bundle/v1` |

Use `application/x-tar` and `gzip`; the archive's actual bytes must be gzip tar.
The current MD contract distinguishes these recommended labels from the
reader's enforced entry name and integrity checks. MPI and MD precheck have
their own contracts; do not substitute them into this table.

For a selected GROMACS example, set `EXAMPLE_DIRECTORY` to its actual engine
directory. `parameters.json` contains **only the engine parameters**, not the
whole recipe or scientific-run envelope:

```bash
EXAMPLE_DIRECTORY=/absolute/path/to/selected-example/gromacs
.venv/bin/python invoke-scientific-batch.py \
  --model gromacs --tool submit_gromacs_workflow --operation run-workflow \
  --source "$EXAMPLE_DIRECTORY/input.tar.gz" \
  --parameters "$EXAMPLE_DIRECTORY/parameters.json" \
  --entry-name gromacs-inputs --semantic-type gromacs-input-bundle/v1 \
  --media-type application/x-tar --compression gzip \
  --output ./runs/md-example --idempotency-key md-example-001 \
  --display-name 'Selected GROMACS example' --wait-seconds 180
```

The client validates the live parameters before uploading, finalizes the source
and manifest, and discovers the tool's envelope. It automatically wraps native
MD requests as `request`; callers must not put that wrapper in the parameters
file. Change only transport paths and discovered model/tool/entry labels when
running another existing engine recipe. Do not silently alter scientific settings.

## Direct typed MCP calls use an envelope

A starter recipe's `arguments` is the scientific request body. These MD tools
take **two top-level arguments**: `request` and `idempotency_key`. Passing
`operation`, `parameters` and `input_manifest` directly at the tool's top level
is invalid. The staged protein tools may use that flat shape; inspect the
selected tool's schema instead of reusing one shape for every model.

After the normal upload helper has finalized your complete manifest, this
local construction preserves one selected recipe and uses its real pointer:

```python
import json
from pathlib import Path

recipes = json.loads(Path("recipes.json").read_text())["recipes"]
recipe, = [item for item in recipes if item["model_id"] == "gromacs"]
request = dict(recipe["arguments"])
request["input_manifest"] = json.loads(Path("manifest-upload/artifact.json").read_text())
arguments = {"request": request, "idempotency_key": "md-example-001"}
Path("mcp-arguments.json").write_text(json.dumps(arguments, indent=2) + "\n")
```

Validate this object against `submit_gromacs_workflow.inputSchema`, then pass
its exact contents to that named MCP tool. Do not submit it again if the helper
already admitted the run. REST uses the discovered scientific request body;
the `request` wrapper above belongs to this typed MCP contract.

## Follow the existing operation

Exit 75 means incomplete observation or delivery, not a new request. Continue
the same receipt directory without uploading or repeating the simulation:

```bash
.venv/bin/python invoke-scientific-batch.py \
  --observe-output ./runs/md-example --wait-seconds 180
```

Retain the operation ID, native output manifest and verified filenames. For a
missing local receipt, use the existing `--recover-operation-id` path with a
new directory. Use `resume_scientific_run` only when the current operation's
checkpoint contract advertises supported continuation; an introductory example
or successful file download does not establish converged scientific sampling.
