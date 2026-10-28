# Interactive recording shutdown

Native owns the existing invocation process group and sends one SIGINT when an
interactive session ends. The workflow wrapper joins that child without sending
a duplicate SIGINT while the child's HDF5 writer is closing. Its existing grace
and forced-cleanup fallback remain unchanged.

The interactive image applies `arena-graceful-interrupt.patch` separately from
the batch runtime patches. Arena defers SIGINT/SIGTERM during its simulation loop
to the existing `Engine.abort`, task `on_abort`, and `EpisodeRecorder.end_episode`
path. The outer Arena CLI closes the recorder. Aborted attempts remain aborted;
the requested `record_failures` behavior is unchanged. A valid empty recording
is possible when no samples were produced and is not itself a product error.

`apply_graceful_runtime.py` verifies the reviewed upstream source and stores
`/opt/interactive/graceful-shutdown-provenance.json`. Exact inherited patch bytes
are idempotent; unrecognized source changes fail the build. The actual isolated
interpreters must resolve the patched Arena module and installed wrapper:

```sh
/opt/i4h/arena/.venv/bin/python -I -B /opt/interactive/scripts/verify_graceful_runtime.py
/opt/i4h/interactive/.venv/bin/python -I -B /opt/interactive/scripts/verify_graceful_runtime.py --transport
```

The CPU regression uses the real Arena engine/recorder and h5py with a CPU scene,
including signals, natural completion, early failure, and empty recordings. The
subprocess probe exercises the actual workflow wrapper and real HDF5 writer:

```sh
python tests/test_graceful_recording.py
python tests/probe_graceful_workflow.py --source src/i4h_interactive/workflow.py --mode interrupt --out /tmp/owned-interrupt-proof
python tests/probe_graceful_workflow.py --source src/i4h_interactive/workflow.py --mode natural --out /tmp/owned-natural-proof
python tests/probe_graceful_workflow.py --source src/i4h_interactive/workflow.py --mode failure --out /tmp/owned-failure-proof
```

Run those probes in the CPU environment with Arena dependencies. Source-selected
tests are source evidence, not an installed-image or GPU qualification. A long
uninterruptible Kit call or authored backend teardown may still exhaust the
existing grace; the worker must retain its real cleanup/failure evidence.

Delivery retains every output byte, including incomplete or invalid files. An
archive's hashes prove transport integrity, not recording validity, episode
completion, control input, or viewer success. No untrusted customer HDF5 is
parsed by the privileged transport owner; format and scientific qualification
remain separate from delivery.
