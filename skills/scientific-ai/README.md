# Scientific AI skills

One customer-facing source for the Nebius Scientific AI workbench and other
MCP-compatible agents. LibreChat installs this exact directory at `/app/skill`.
Skills teach the **hosted** APIs; they do not deploy NVIDIA services, grant model
access, or install an entire workbench on a customer's computer.

## Select the scientific service

For the managed **Run:ai scientific service**, start with
[`runai-scientific-gateway`](runai-scientific-gateway/SKILL.md), then the
`runai-<model>` skill. These additive skills cover 14 models and 32 explicitly
indexed workflows; `manifest.json.runai_workflows` maps every workflow to its
instructions. They use the supplied scientific API URL, standard REST/MCP and
the caller's bound bucket. Native Run:ai administration and the older artifact
manifest protocol are separate interfaces. The unprefixed skills retain their
existing backend instructions. Discover the current model/schema and skill link;
bundle inclusion does not certify live model availability or scientific accuracy.

## Install a release

Download the `scientific-ai-skills-*.tar.gz` and `SHA256SUMS` assets from
[Releases](https://github.com/rene-tech/serverless-ai-cookbook/releases).
For the original backend's laptop/Claude Code file transport, also download `scientific-ai-client-*.tar.gz` and
its `.sha256` file from the **same release**. The skills archive contains
instructions; the client archive contains `upload-artifact.py`,
`invoke-scientific-batch.py`, `invoke-native.py` and their dependencies manifest.
Installing skills does not put these helpers in your skills directory or PATH.
Follow the [portable installation](scientific-gateway/references/portable-client.md)
for that separate client directory.
Verify the checksum and extract the archive. From its `scientific-ai` directory:

```bash
python3 bundle.py verify
python3 bundle.py install --dest /absolute/path/to/your/agents/skills
```

Choose the destination documented by your agent (for example its project skills
directory). Nothing auto-installs globally. An identical install is a no-op;
conflicting existing skills are reported without overwrite. For upgrades, use
a new versioned destination and switch the client after verification. Restart
or reload the client's skills. Configure your Scientific AI MCP URL and user API
key through its normal secret configuration, never in a skill or chat message.

You can also check out a pinned `scientific-ai-skills-*` tag and run the same
commands from `skills/scientific-ai`. `main` is the integrated development source;
a release tag and checksummed asset are the reproducible installation.

## Coverage

`manifest.json` maps all 37 catalog Apps observed on 2026-09-20 to workflow skills
and records the reviewed upstream revisions. Eight new workflows cover speech,
clinical ASR evaluation, single-cell integration, microscopy, SAM2, binder
campaigns, starter data and MindEval. Existing clinical documentation and all
scientific model skills are included with their scripts/references.

The MD additions cover GROMACS (single-GPU and separately identified MPI),
LAMMPS and NAMD. Their instructions use the same durable client and file bridge.
LAMMPS/NAMD onboarding is still under qualification; inclusion here does not
claim live App availability or GPU process snapshot support. Always discover
the caller's current catalog and exact-runtime limitations.

The `openff` skill covers optional **CPU** ligand parameterization, force-field
compatibility and measured export checks. It is not another catalog App and does
not install its required environment. See its explicit dependency contract.

The additive `rfd4-proteina` skill covers hosted annotated-CIF generation with
the public matched flow/autoencoder release, artifact verification and inline
structure viewing. It is distinct from `rfdiffusion` and `proteina-complexa`;
oracle/search workflows and remote YAML inputs are not advertised. Its presence
in the bundle does not establish deployment or caller access.

For the original hosted backend, start with `scientific-gateway`; load only skills relevant to your task. For
non-LibreChat clients, see its [portable client contract](scientific-gateway/references/portable-client.md).
For event participants using Claude Code, start with
[`scientific-ai-hackathon`](scientific-ai-hackathon/SKILL.md), including its
MCP setup and short walkthrough. It uses the same caller-authorized model API.
Client-specific tools are conditional, not promised by downloading Markdown.
`manifest.json.client_requirements` explicitly labels every skill's required
client/runtime and optional LibreChat sections. `workbench_*`, workspace viewers
and scientific-study supervision are not installed by connecting the hosted
model MCP. Plain clients can use the separately packaged
`scientific-ai-client-*.tar.gz` for the same verified upload/manifest/submit/poll/
download flow; see the portable guide and its complete RFdiffusion example.
Private upstream Nebius infrastructure skills are optional operator extensions
and are not redistributed here. Adapted NVIDIA guidance is attributed in
[NOTICE.md](NOTICE.md), not advertised as an unmodified NVIDIA-verified package.

## Maintain and qualify

Every model onboarding must update the model-to-skill map and supply meaningful
workflow guidance or an explicit existing route. Test examples against the exact
model contract, include failure/recovery expectations, and preserve evidence
bound to source, client and runtime. Do not add a model by editing a second skill
tree or copying upstream deployment commands into the hosted customer workflow.

```bash
python3 -m pytest tests clinical-documentation/scripts -q
python3 bundle.py lock
python3 bundle.py verify
python3 bundle.py check-catalog
python3 bundle.py build --output /absolute/release-output
```

From the repository root, package the exact existing file clients alongside the
skill release (no workbench/API or duplicate transport implementation):

```bash
python3 templates/hcls-librechat/scripts/package-scientific-client.py \
  --output /absolute/client-release-output
```

Run the affected workbench tests from the repository root as well. `lock` updates
the release file inventory after intentional edits; it is not a test. This
release tests instruction contracts, deterministic helpers and installation.
It does not newly certify scientific accuracy or all model/GPU/snapshot modes.
See [RELEASE.md](RELEASE.md) for measured results and remaining gaps.

Historical templates still contain archived upstream/vendor skill copies. Do
not bulk-install every skill found anywhere in this repository; install this
explicit path or the release asset so there is only one active definition.
