# CPU GROMACS preparation in the Scientific AI workbench

The additive `Dockerfile.gromacs-prep` installs GROMACS 2026.4 into
`/opt/gromacs-prep/2026.4`, with `gmx` on PATH. It preserves the existing client,
skills, login state and agent configuration. Actual simulations still run through
Scientific AI; this CPU build is for preparation, inspection and analysis, not a
replacement MD executor or performance-qualified simulation runtime.

## Source and compatibility

- Official source: `https://ftp.gromacs.org/gromacs/gromacs-2026.4.tar.gz`.
- SHA-256: `58eda60979b124fcf9dff8b1b63cedfbc72fdb36d99e921dc1bdc310571098b6`.
- Builder: pinned Python 3.12.15 Debian 12 image; CMake 3.31.6, GCC 12.
- CPU-only, no external MPI/OpenMP/hwloc/FFT dependencies; portable SIMD setting.
- Installed prefix is approximately 29 MB, including upstream data and COPYING.
  Runtime dynamic dependencies are the standard Debian 12 C/C++ libraries.
- Default parent is the compact scientific-progress/inline-results image
  `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:a3d7e7228fb02eb470aa1269d549a1b1975efb5a78dc505b37898e7d0bbea8f0`,
  sourced from cookbook commit `544eb8d17f6c185b7ab2fb626cec35cf1ee33434`.
  This avoids the retired parent's Docker layer-depth limit. The overlay also
  installs verified skills `2026.10.16.6` and their matching core instructions.
- Each image build runs the real preparation acceptance below. Pass the exact
  current workbench digest with `--build-arg WORKBENCH_BASE=...`; never replace a
  newer client with an old example base merely to add these tools.

From repository root:

```sh
docker buildx build --load --file templates/hcls-librechat/Dockerfile.gromacs-prep \
  --build-arg WORKBENCH_BASE=YOUR_QUALIFIED_WORKBENCH_DIGEST \
  --build-arg HCLS_IMAGE_REVISION=YOUR_COMMITTED_SOURCE_SHA \
  --tag scientific-ai-workbench:gromacs-prep .
```

## Real acceptance

`scripts/gromacs-prep/verify.py` runs native commands, not mocked responses:

1. Build a 648-atom / 216-water fixture from installed coordinates, a genuine
   topology with force-field includes, and explicit MDP. `grompp` runs without
   `-maxwarn`, retaining processed topology, effective settings and commands.
2. Dump/check the TPR, convert its duration from 1 ns to 10 ns, extract coordinates,
   and check atom count. Compare the entire dumped system before/after, allowing
   only the filename header and intended `nsteps` difference.
3. Confirm original inputs remain unchanged and missing topology fails clearly.
4. Optionally inspect an explicitly supplied read-only TPR and repeat a 10 ns
   duration-only conversion in the new output directory. This is not a repair.

```sh
python3 /opt/hcls-librechat/gromacs-prep/verify.py \
  --output /tmp/gromacs-prep-acceptance-NEW
# Optional private input, never checked into the cookbook:
python3 /opt/hcls-librechat/gromacs-prep/verify.py \
  --output /tmp/gromacs-prep-input-NEW --tpr /workspace/input/simulation.tpr
```

The fixture is a tool-compatibility test, not production scientific validation.
It runs no `mdrun`, makes no API calls and requires no customer key. JSON records
source identities, hashes, commands, results and the explicit qualification bound.
`test_gromacs_prep.py` separately tests installer idempotence, prior file/link
preservation, rollback and refusal to overwrite subsequent operator changes.

## Existing instance: no-restart additive patch

Only an authorized operator performs this after QA qualification. Export the
`/opt/gromacs-prep/2026.4` prefix from the exact qualified image, archive/checksum
it, and verify that checksum after staging in the target. Copy the installer and
acceptance script from the same source revision. Do not pull in a different
GROMACS build, change dependencies in place or replace the running endpoint.

Run acceptance with the staged binary before activation, then install:

```sh
python3 verify.py --gmx /tmp/STAGED/2026.4/bin/gmx --output /tmp/prep-qa-NEW
python3 install.py install --source /tmp/STAGED/2026.4
gmx --version
```

The installer copies an immutable versioned prefix, verifies its identity and
atomically changes only `/usr/local/bin/gmx`. It records the previous command
and a receipt. Run the command through the environment-execution shell too;
container root access alone does not prove the user's execution path works.

Rollback uses the returned receipt path:

```sh
python3 install.py rollback --receipt /opt/gromacs-prep/patches/PATCH_ID/receipt.json
```

Rollback restores the previous command and retains the prefix/evidence, avoiding
interruption of any process already using it. Neither action changes chats,
customer workspace inputs, API credentials, jobs or running studies. Update the
default image as well: an instance patch alone is not a future-install fix.

## Scientific scope

A TPR contains inspectable coordinates/settings; duration-only conversion does
not require the original `.gro/.top/.mdp`. Physical reconstruction does require
complete, validated sources and scientific intent. Derived precheck reconstructions
are not automatically equivalent originals. Geometry/chirality findings must not
be claimed repaired by a new duration, minimization or successful preprocessing.
The skill preserves optional precheck consent and original-input hashes, requests
only genuinely missing choices, and rechecks authorized changes without asking
for the same permission twice.

Official command references: [convert-tpr](https://manual.gromacs.org/current/onlinehelp/gmx-convert-tpr.html),
[grompp](https://manual.gromacs.org/current/onlinehelp/gmx-grompp.html),
[editconf](https://manual.gromacs.org/current/onlinehelp/gmx-editconf.html).
