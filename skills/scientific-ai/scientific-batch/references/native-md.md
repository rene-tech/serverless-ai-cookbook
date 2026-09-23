# Native molecular-dynamics transport

This shared reference applies to GROMACS, LAMMPS, NAMD and AMBER. A skill being
installed is not evidence that its App is released or granted to this user.
Discover the exact App and schema first. AMBER is not interchangeable with these
engines; do not silently translate its inputs to another simulator.

## Files and submission

Keep all relative-path input dependencies in one directory: native scripts,
topology, coordinates, force-field/potential includes and matching restart/bias
files. Preserve original bytes and provenance. The common
[bundle helper](../../gromacs/scripts/make-input-bundle.py) creates a reproducible
gzip tar outside that directory and reports its measured hash and length:

```sh
python3 /app/skill/gromacs/scripts/make-input-bundle.py \
  --source /workspace/md/inputs --output /workspace/md/input.tar.gz
```

This path is for the hosted workbench. In another client resolve the helper
relative to its installed skill directory. The helper is engine-independent.
Put model parameters in a separate JSON file, not a scientific-run envelope and
not inside the input directory. Inspect files before assigning their names in
that JSON. Native examples are protocol templates, not validated customer data.

The existing client selects the engine contract through discovery. Substitute
the actual App/tool/source role below; never paste archive bytes into MCP:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model lammps --tool submit_lammps_workflow --operation run-workflow \
  --source /workspace/md/input.tar.gz --parameters /workspace/md/parameters.json \
  --entry-name lammps-inputs --semantic-type lammps-input-bundle/v1 \
  --media-type application/x-tar --compression gzip \
  --output /workspace/md/receipt --idempotency-key md-campaign-replica-01 \
  --display-name 'MD campaign replica 01'
```

For NAMD these identifiers are `namd`, `submit_namd_workflow`, `namd-inputs`
and `namd-input-bundle/v1`. Discovery is authoritative if identifiers change.
For AMBER use `amber`, `submit_amber_workflow`, `amber-inputs` and
`amber-input-bundle/v1`.
Authentication is supplied by the configured client; do not read keys into chat.
`/opt/bionemo` is a retained installation path, not the platform product name.
In LibreChat prefer the existing durable study executor from `scientific-batch`
for workflows that should remain observable after a chat disconnect.

The client validates parameters before uploading, creates the real immutable
input manifest and submits once. Save its receipt directory and operation ID.
Rerun the identical command with that directory to resume observation; do not
create a new key just because capacity is queued. Corrected scientific inputs
are a new experiment and need a new receipt and idempotency identity.

## Storage and continuation

`output_destination: customer-bucket` uses the submitting user's assigned bucket.
`output_prefix` is a relative prefix, not a bucket selector. The engine writes
native local files; the companion publishes closed generations to object storage.
Customer storage is not an in-process POSIX mount for the simulator.

Manifests retain original filenames, sizes and SHA-256 values, referencing
content-addressed objects. Preserve these manifests plus all trajectory parts,
restart files, native logs and bias state. A later generation cannot reconstruct
files that a native script deliberately overwrote before publication.

Platform retry restores the last committed generation of the same workflow.
An interrupted uncommitted segment may run again. Cancellation does not promise
a final checkpoint. Native continuation does not make an independent replica;
stochastic state may not be bitwise serializable. Persistent CUDA/CRIU process
snapshots are a separate capability: require exact-runtime evidence before
claiming they work or estimating their cold-start benefit.

The default workspace budget is 4 GiB and wall budget six hours. Read current
schema limits before requesting more. These requests do not enlarge bucket
quotas; individual files over 5 GiB are not currently qualified. Select output
cadence with the scientist so trajectories fit the scientific question and
storage allowance. Never silently reduce trajectory output to pass a test.

## Evidence to return

Retrieve the final result, verified artifacts and bucket manifests. Return links
to the actual files and a concise report: operation/job IDs, engine/image,
input/protocol hashes, atom count, simulated steps/time and units, ensemble,
seeds, expected versus observed frames, restart continuity, warnings and relevant
energy/temperature/pressure diagnostics. Report queue time, setup time, native
execution and checkpoint/export time separately where measured.

Do not call file presence, successful process exit or a short stable trajectory
scientific convergence. Free-energy results additionally need declared windows,
sampling, estimator, overlap, uncertainty and convergence analysis. MD does not
replace docking or automatically parameterize ligands.
