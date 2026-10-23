# Visible isolated atoms in bounded structure previews

A retained 2,997,924-atom result correctly produced a labelled 5,700-position
CA subset, but the viewer showed an empty scene. All positions were finite and
all atoms were isolated. Cartoon fell back to Sticks, which had no bonds to
draw. The same browser rendered the bonded 61,153-atom control's 3,555-atom
polymer subset normally. Adding spheres exposed the existing positions without
changing the camera, coordinates or bond arrays.

The viewer now defaults to **Atom positions** when every atom is isolated and
keeps isolated atoms visible as spheres in other representations, including
explicit Sticks. Its status explains this representation. It adds no connections
for isolated atoms and leaves ordinary parsing/bond inference unchanged. Full
bonded structures keep their existing Cartoon default. The exercised additive
Cartoon + sticks branch now uses GLModel's supported `setStyle(..., true)` API;
the previous `model.addStyle` call raised a TypeError.

This changes presentation only. Coordinate selection, preview budgets, native
input support and complete retained files are unchanged. The maintained
template explicitly copies `life-science/bionemo-librechat/viewer-mcp.py` to
`/opt/bionemo/viewer-mcp.py`; the additive default-image Dockerfile now copies
that source too.

## Exact release

- Source: `20da61c7705cfdb5037fd4fff17d64d745a6b363`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:sparse-preview-20261023-20da61c`.
- Digest: `sha256:be5adc6c39b5ef7909d382d7122e56c79336edf11b1a94342df05f4765ea08f6`.
- Portable bundle: `2026.10.23.3`; [machine-readable evidence](evidence/sparse-preview-20261023.json).

The image preserves all 100 base layers (112 total) and runtime configuration.
All 110 canonical bundle files match source. Of 19 compared runtime/library
files, only the viewer changes; the other 18 retain their exact base bytes.
The only skill changes are the two [MD budget references](md-budget-guidance-20261023.md)
and bundle metadata. OpenMM .7 and BioEmu2 .2 domain bodies are unchanged.

## Bounded qualification and activation

All 126 focused structure, analysis, preview and bundle tests passed. A browser
regression exercised Atom positions, Sticks, Cartoon and Cartoon + sticks on
actual retained sparse and bonded coordinates, checking pixels and unchanged
coordinates/bonds. The exact image produced byte-identical HTML with networking
disabled. Release-pointer and deployment-link checks passed separately.

A fresh system/qa chat loaded the actual shared/OpenMM skills and workbench
reference, then completed two durable `python-script` phases with 12 verified
deliverables. Both full reports appeared in the original open conversation and
on saved reopening without Reset. The 5,700 isolated positions remain visible
in Sticks; the 3,555-atom control retains its Cartoon. Both HTML outputs exactly
match the image-qualified bytes. Operation IDs and measured metrics match the
retained receipts; unmeasured timing boundaries remain explicitly unknown.
No recovery download or scientific submission occurred.

Original evidence was preserved: 69 file paths/sizes, 47 small-file hashes,
four plan/receipt hashes and four chat messages matched. The 22 larger files
were not rehashed solely for preservation checking. The new report remains a
separate derived result. Agent planning before CPU admission took roughly nine
minutes; this observation does not identify a cause or qualify planning latency.
An automation stability wait while scrolling the control timed out; ordinary
scrolling displayed it without changing the page or viewer source.

All six retained clients received exactly the viewer and two budget-reference
files, with fresh idle/base checks and backups. Each preserved 19 protected
files, existing study receipts and API/supervisor/worker process identities.
Two registry entries were refreshed; their domain bodies and 87 other objects
were preserved. Loaded reference hashes were verified and temporary loopback
inspectors closed. Existing custom guidance and connection scope were retained;
these are scoped overlays, not full-bundle replacements. No customer inference,
client replacement or restart occurred.

New MD `python-script` reports import the viewer from disk and receive this fix
without a restart. Already saved HTML embeds its old JavaScript and is unchanged.
Existing direct-MCP structure-viewer processes cache their module; this overlay
does not reload them or qualify their updated behavior. New default-image
processes receive the new source. Existing-worker `native-md-timing` execution
was not requalified. Scientific execution, convergence, arbitrary-size rendering,
capacity, isolation and full scientist-client readiness remain outside this
presentation qualification.
