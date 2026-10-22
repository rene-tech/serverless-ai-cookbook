# OpenMM sources and scope

- [OpenMM 8.6.1 release](https://github.com/openmm/openmm/releases/tag/8.6.1),
  pinned upstream revision `b399af4725573963b46d6c1083fdcf7a37615857`.
- [Application guide](https://docs.openmm.org/latest/userguide/application/02_running_sims.html):
  prepared input formats, explicit force fields/solvent, reporters and restart.
- [Checkpoint and State distinction](https://openmm.github.io/openmm-cookbook/latest/notebooks/tutorials/loading_and_reporting.html):
  binary checkpoints require compatible systems/platforms; portable State does
  not restore every internal/random-generator value.
- [Component licenses](https://github.com/openmm/openmm/blob/8.6.1/docs-source/licenses/Licenses.txt):
  API/Reference/CPU MIT, CUDA/OpenCL LGPL with their component notices. Do not
  describe the complete runtime as MIT-only.

The bundled example downloader retrieves public upstream test/example inputs,
verifies exact SHA-256 and retains URL/revision provenance. `alanine` is an
explicitly solvated dipeptide; `protein` is the packaged solvated villin example;
`ionic` is the upstream parameterized ionic-liquid GROMACS system, not a protein
or an aqueous solvent validation. These are software demonstration protocols,
not evidence of scientific convergence or performance on another workload.
