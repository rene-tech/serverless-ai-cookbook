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
job, `id: "gang"`; `nodes` and `gpus_per_node` select one simulation's layout.
The current implementation contract allows 1–8 nodes, 1/2/4/8 GPUs per node,
and at most 16 GPUs total. Omitted `gpus_per_node` remains one for compatibility.
The live schema decides which shapes a deployment accepts; do not restrict a
customer to the older 2–8 nodes with one GPU each, or promise unavailable shapes.
Start from [the legacy 2×1 prepared-TPR example](../examples/prepared-tpr-mpi.json),
[1×8 example](../examples/prepared-tpr-mpi-8gpu.json), or
[2×8 example](../examples/prepared-tpr-mpi-16gpu.json), adapting analysis and
output budget to the actual inputs. Read [MPI interfaces and qualification](mpi.md)
before selecting a shape or describing performance.

Use the same bundle role, artifact upload/poll/result flow and customer-bucket
export as single-GPU GROMACS. For the installed client, change `--model` to
`gromacs-mpi` and `--tool` to `submit_gromacs_mpi_workflow`; no different API key
or manually launched MPI service is needed when the user has access to the App.

One node uses an admitted Job with all its GPUs in one Pod; multiple nodes use
a complete JobSet/Kueue gang with distinct-node placement. One MPI rank is bound
to each allocated GPU, so `threads: 8` means eight OpenMP threads per rank, not
eight per entire node. Preparation and analysis execute only on the coordinator,
which alone publishes coherent checkpoints/results. A failed gang resumes the
same operation from its latest committed native checkpoint, not an arbitrary
surviving rank. Changing node/GPU shape is a new request, not an in-place retry.

Transport is operator-owned: single-node uses the CUDA-aware UCX-local path;
multi-node retains host-staged TCP until another fabric is qualified. The current
H100 full nodes have intra-node NVLink but no configured RDMA/InfiniBand fabric
between them. Do not claim measured CUDA IPC or RDMA from a build/configuration
alone. Compare the same system, external-MPI image, precision, output cadence and
offload settings on 1×1 and larger shapes before recommending strong scaling.
Report wall time and **total** occupied GPU-hours, including staging and recovery,
rather than only engine ns/day. No new multi-GPU speedup is established merely
by these examples or passing schema tests.

This distributed shape does not expose coupled replica exchange, parallel
PLUMED, CP2K QM/MM or Torch NNPot. Independent replica/window jobs on `gromacs`
remain the usual throughput-oriented choice. MPS/MIG settings belong to the
operator, not to a customer request.

## Primary references

- [GROMACS Colvars integration](https://manual.gromacs.org/2026.2/reference-manual/special/colvars.html)
- [GROMACS PLUMED integration](https://manual.gromacs.org/2026.2/reference-manual/special/plumed.html)
- [PLUMED restart behavior](https://www.plumed.org/doc-v2.10/user-doc/html/_r_e_s_t_a_r_t.html)
- [GROMACS parallel performance](https://manual.gromacs.org/2026.2/user-guide/mdrun-performance.html)
