# Separate transport and Arena environments

The GPU worker starts its trusted controller with
`/opt/i4h/interactive/.venv/bin/python -I -B`. This clean environment contains
only the pinned interactive package and transport dependencies. Installing it
does not change the portable image's Arena packages or versions.

The nonsecret worker configuration names `runtime_python`, normally
`/opt/i4h/arena/.venv/bin/python`. After applying the same process/user/Landlock
boundary, the controller uses that interpreter to run its installed
`workflow.py` file. This wrapper uses only the standard library before loading
the portable runtime inside Arena. Project inspection, imports, policy services
and Kit therefore use the preserved Arena environment. The controller does not
insert its own packages into Arena's import path or install a transport package
there. `runtime_python` is operator configuration, never a request parameter.

Verify both environments with their actual interpreters: the controller's
dependencies must pass its dependency check; Arena's complete distribution
inventory and portable source hashes must equal the exact base image. Retain
upstream/base dependency diagnostics separately from any newly introduced
conflict. Run hostile-child tests with the installed controller and actual Arena
child, without mounting replacement production modules. GPU rendering, NVENC,
WebRTC and full workload behavior still need qualification on the final image.
