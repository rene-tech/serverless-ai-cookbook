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

## Installed CPU analysis environment

This workbench has a separate Python 3.11 interpreter at
`/opt/md-analysis/bin/python`. Its pinned analysis packages are NumPy 1.26.4,
SciPy 1.16.3, MDAnalysis 2.10.0, ParmEd 4.3.1, Matplotlib 3.10.7, Pillow 12.3.0 and
netCDF4 1.6.5. It uses the existing system FFmpeg/ffprobe for CPU video encoding.
Inspect the actual installed versions without making an API call:

```sh
/opt/md-analysis/bin/python /opt/md-analysis/inventory.py
```

Use this interpreter for trajectory readers, topology inspection, numerical
analysis and plotting. Keep `/opt/scientific-client/bin/python` for the hosted
API helper above; do not upgrade it to add analysis packages. The analysis
environment does not install local GROMACS, LAMMPS, NAMD or AMBER simulators.
Discover and invoke the granted hosted Apps for dynamics. Library availability
is not a scientific-validation or customer-readiness claim: verify real file
formats, atom mapping, units, periodic cells, frame/time coverage and native
provenance for each analysis. Keep raw downloaded files unchanged, and write
derived tables, figures, aligned display coordinates and videos separately.

## Comparing engines

Use one canonical topology/coordinate set, not four independently solvated
systems. Inventory the installed engines, converters, force-field files and
renderers before promising outputs. Preserve a master Amber topology when
comparing ff14SB; NAMD can read it natively, whereas GROMACS/LAMMPS need explicit
conversion and validation. Re-read actual output parameters: atom ordering/types,
masses, charges, bonded and LJ terms, combining rules, exclusions and AMBER1–4
electrostatic/LJ scaling. Compare identical-coordinate decomposed energies and,
where available, forces before dynamics. Native Coulomb constants, long-range
mesh accuracy and dispersion corrections can differ; disclose and quantify
them rather than changing charges to make total energies coincide.

TIP3P representations differ. A master topology may encode an H–H bond instead
of an HOH angle. Do not drop that potential or choose an approximate water angle
without proof. Native rigid-water/constraint adapters must preserve the original
target geometry. LAMMPS hybrid bond/angle styles also require coefficient replay
after reading native restart files; a restart alone may not contain them.

Keep physical cutoffs, thermodynamic targets, timestep, stage lengths, seeds and
trajectory cadence explicit. Solver-specific constraint/thermostat/barostat
differences must be recorded. Retain failed variants; a repaired configuration
is a new input identity. Compare ensemble properties and phi/psi distributions,
not matching chaotic frames or convergence inferred from one nanosecond.

For comparative videos, unwrap each molecule, center and align the peptide to
one reference, use identical camera/representation/frame cadence/playback, and
label each engine. Preserve original trajectories separately. Missing pressure
calculations, native timings or frames are missing data, not zeros or estimates
presented as measurements.
