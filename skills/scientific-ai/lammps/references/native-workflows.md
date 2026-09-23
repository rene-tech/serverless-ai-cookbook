# LAMMPS continuation and advanced workflows

Continuation is opt-in. Both the initial and continuation scripts need identical
scientific context after loading their respective native restart. The typical
production tail below is illustrative: the target and cadence must come from
the scientist's protocol, not this example.

```text
include protocol.inc
dump trajectory all custom 10000 trajectory.${fs2_segment}.lammpstrj id type x y z
timer timeout ${fs2_segment_seconds} every 100
run 100000 upto
write_restart state.restart
print "$(step:%.0f)" file progress.txt screen no
```

The corresponding continuation declaration selects `in.resume`, `state.restart`,
`progress.txt` and `target_step: 100000`. `in.resume` loads `state.restart` and
then the complete context above. A production script may load a different
prepared restart initially. Keep native fix IDs where restart data depends on
them; preserve and inspect native warnings. Absolute target steps include any
preparation/equilibration steps already recorded in the restart.

Independent jobs can represent replicas or free-energy windows, but a JSON job
array does not implement exchange between simulations. Reweighting, FEP/TI,
umbrella estimates and convergence analysis require a scientifically specified
protocol and available native packages. Do not promise a specific estimator or
multi-node topology until the selected App's evidence covers it.

## Primary documentation

- [Input scripts](https://docs.lammps.org/Commands_input.html)
- [Native restart contents and limitations](https://docs.lammps.org/read_restart.html)
- [KOKKOS build/runtime behavior](https://docs.lammps.org/Speed_kokkos.html)
- [Native timer](https://docs.lammps.org/timer.html)
- [NVIDIA distribution](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/lammps)

The online LAMMPS manual moves ahead of the pinned image. Verify version-specific
commands and packages against runtime metadata and its bundled documentation.
