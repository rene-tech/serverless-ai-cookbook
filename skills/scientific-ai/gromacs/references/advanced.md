# Enhanced sampling and distributed MD

Read the live App schema and runtime qualification first. A skill may be newer
than a particular deployment; do not promise features absent from that App.

## Colvars and PLUMED on `gromacs`

The enhanced single-GPU package retains NVIDIA's GROMACS binary and adds a
pinned PLUMED 2.10 kernel. Colvars is compiled into the engine. Define the
collective variables, atom selections, units, bias method and parameters as
part of the customer's scientific protocol. Never silently add a bias to an
ordinary simulation or present a bounded metadynamics test as convergence.

Colvars: include the configuration in the input bundle and reference it through
the MDP's `colvars-active` / `colvars-configfile` options. Use an explicit seed
when appropriate. GROMACS embeds its restart state in the native checkpoint.

PLUMED: include `plumed.dat` and its referenced inputs in the bundle. An MD step
uses this shape (after preparing a compatible finite `md.tpr`):

```json
{
  "id": "biased-md",
  "command": "mdrun",
  "args": ["-s", "md.tpr", "-deffnm", "md"],
  "plumed_input": "plumed.dat",
  "expected_outputs": ["HILLS", "COLVAR"]
}
```

Change expected filenames to match the actual PLUMED configuration. The field
is relative to the step's working directory. The runtime supplies the packaged
kernel and checkpoint flags. Segmented restart must preserve the native `.cpt`
**and** bias/restart files. For an externally continued run include all of them;
the coordinates alone cannot reproduce the bias history. Inspect restart logs,
HILLS/COLVAR or Colvars history and trajectory times after recovery.

## Distributed `gromacs-mpi`

Discover `get_model_schema(model_id="gromacs-mpi", protocol="scientific-batch-v1")`.
Its typed tool is `submit_gromacs_mpi_workflow`, operation `run-workflow`, parameter
schema `fs2-serve.nebius.ai/gromacs-mpi-workflow-request/v1`. There is exactly one
job, `id: "gang"`; `nodes` chooses the gang size within the deployed bounds.
Start from [the prepared-TPR example](../examples/prepared-tpr-mpi.json), adapting
analysis to the actual trajectory cadence and filenames.

Use the same bundle role, artifact upload/poll/result flow and customer-bucket
export as single-GPU GROMACS. For the installed client, change `--model` to
`gromacs-mpi` and `--tool` to `submit_gromacs_mpi_workflow`; no different API key
or manually launched MPI service is needed when the user has access to the App.

JobSet/Kueue admit the complete gang. One rank/GPU runs per distinct node;
preparation and analysis execute only on rank zero. Only that rank publishes
coherent checkpoints/results. A failed gang resumes the same operation from its
latest committed native checkpoint, not from an arbitrary surviving rank.

The portable initial network path is host-staged TCP. Do not claim RDMA or
direct GPU communication from the presence of CUDA-aware MPI in the binary.
Compare the same system and precision on one and two GPUs before recommending
strong scaling. Report wall time and **total** GPU-hours, including staging and
recovery, rather than only engine ns/day. Large systems are better candidates.

This distributed shape does not expose coupled replica exchange, parallel
PLUMED, CP2K QM/MM or Torch NNPot. Independent replica/window jobs on `gromacs`
remain the usual throughput-oriented choice. MPS/MIG settings belong to the
operator, not to a customer request.

## Primary references

- [GROMACS Colvars integration](https://manual.gromacs.org/2026.2/reference-manual/special/colvars.html)
- [GROMACS PLUMED integration](https://manual.gromacs.org/2026.2/reference-manual/special/plumed.html)
- [PLUMED restart behavior](https://www.plumed.org/doc-v2.10/user-doc/html/_r_e_s_t_a_r_t.html)
- [GROMACS parallel performance](https://manual.gromacs.org/2026.2/user-guide/mdrun-performance.html)
