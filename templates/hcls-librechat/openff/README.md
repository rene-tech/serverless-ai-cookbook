# Installed OpenFF CPU runtime

The general-purpose workbench installs `/opt/openff/bin/python`; adding a skill
alone does not install its dependencies. Both `Dockerfile` and
`Dockerfile.default-release` build this environment from `conda-linux-64.lock`.
The latter extends an immutable, deployed workbench image, preserving its UI,
MD analysis and ClawBio additions. It contains no customer configuration.

The explicit Linux x86-64 lock contains 237 public conda-forge packages with
SHA-256 checksums, installed by a digest-pinned micromamba image. It pins OpenFF
Toolkit 0.18.0, Interchange 0.5.2, forcefields 2026.01.0, AmberTools 26.0,
OpenMM 8.6.1 and RDKit 2026.3.1. The helper deliberately selects Sage 2.2.1 and
AmberTools AM1-BCC, not a floating newest force field or charge model.

`verify-runtime.py` checks installed backends, AmberTools executables, force-field
availability and the CPU OpenMM Reference platform at image build time. Real
qualification additionally parameterizes a neutral and a charged molecule and
checks identity, atom counts, topology charges and output hashes independently.
No GPU is needed for these preparation steps. They do not establish MD readiness
or equivalence of a combined protein/ligand force field.

To update, solve the human-readable canonical skill `environment.yml` in an
isolated environment, export an explicit SHA-256 lock, inspect the changes, then
rebuild and rerun the installed-runtime and real-agent qualification. Never
install a replacement environment inside a customer's chat.

From the repository root:

```bash
docker build --platform linux/amd64 \
  -f templates/hcls-librechat/Dockerfile.default-release \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t scientific-ai-librechat:general-openff .
docker run --rm --entrypoint /opt/openff/bin/python \
  scientific-ai-librechat:general-openff /opt/openff-release/verify-runtime.py
```

The resolved environment adds about 3.9 GB to the local unpacked image. This is
a deployment-image pull cost, not per-request GPU loading. Registry compression
and caching determine the transferred bytes. Do not market this as a model
snapshot optimization.
