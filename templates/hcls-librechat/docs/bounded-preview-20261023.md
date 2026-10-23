# Bounded coordinate previews and nonfatal report presentation

A real retained-results study failed because a 7,822,621-byte mmCIF exceeded
the inline preview budget. The previous fallback only handled PDB, and the
optional preview exception prevented the measured HTML report from being written.

The helper now uses Biopython's mmCIF parser and writer to derive bounded
atom-site views. It preserves recorded coordinate strings and chain/residue
identities. Depending on size and composition, the view contains polymer atoms,
heavy atoms, backbone positions or an explicitly labelled sampled subset.
Small coordinate files retain their original bytes. The existing browser budget
applies to the derived preview, not to supported native inputs; complete native
coordinates remain unchanged. This is visualization, not trajectory reduction,
structure repair or scientific validation.

Optional conversion, parsing, viewer and presentation-size failures produce a
visible explanation and preview provenance while the verified report still
renders. Integrity failures remain errors. Both workbench recipes now declare
six stable report/preview-document outputs instead of requiring a derived
coordinate file that may be unavailable. The available coordinate subset is
embedded in the HTML; original native files remain the complete source.

## Exact release

- Source: `389458042770e8a1046bc30aefe8283ae85f957e`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:bounded-preview-20261023-3894580`.
- Digest: `sha256:962fff454d231c3ea40b31f494cc9e78fabe590ca8e10786c38a01f58df38363`.
- Portable bundle: `2026.10.23.2`; [machine-readable evidence](evidence/bounded-preview-20261023.json).

All 89 layers of the previous report-completion image are preserved (100 total),
as is its runtime configuration. All 110 canonical bundle files match source.
Seventeen recopied runtime files were compared with the base: only
`native_md_preview.py` differs; the other sixteen, including the executor,
discovery schema, measurement helpers, AF3 preparation/analysis and scientific
execution clients, retain their exact bytes. The only changed skill content is
the OpenMM/GROMACS workbench references and bundle metadata. OpenMM .7 and
BioEmu2 .2 domain bodies are unchanged.

## Bounded qualification

The 81 focused tests cover real mmCIF grammar, long/quoted chain and atom names,
precise retained coordinate strings, nucleic acids, large polymers and
nonpolymer inputs, subset sampling, unavailable viewers and preserved integrity
failures. Seventeen release-pointer/deployment-link checks also pass.

The exact published image ran with networking disabled against retained
61,153-atom native coordinates. Its report is 901,829 bytes and embeds a labelled
3,555-atom polymer view. An injected missing optional viewer still produced all
six declared documents and a complete measured report with explicit preview
unavailability. No new scientific operation was submitted.

A fresh system/qa chat loaded the actual shared skills and changed OpenMM
reference, completed one durable `python-script` phase with six deliverables,
and rendered the full HTML plus a nonblank structure during the original stream
and saved-chat reopening without Reset. It reported 50,000 steps, 100 ps,
301.556222 K, 357.205797 ns/day, 24.187737 s integration, 3.961909 s setup and
32.375748 s command wall time. Unmeasured timing boundaries remained unknown.
The exact operation ID came from the verified recovery receipt. All 53 files of
the failed study and both original chat messages retained their bytes/content;
the failure was preserved. No recovery download or scientific replay was needed.

All six maintained clients received only the preview helper and two references,
after fresh endpoint, idle-study and exact-base checks with backups. Each retained
17 protected files and its API, supervisor and worker process identities.
Two selected registry entries were refreshed; their domain bodies and 87 other
skill objects were preserved. Loaded reference hashes were checked, and each
temporary loopback inspector was closed. Existing AF3 guidance differences and
bundle metadata were preserved; these are scoped overlays, not full-bundle
byte-identical installations. No customer inference or endpoint replacement
occurred.

This qualifies bounded retained-result reporting, not new scientific execution,
convergence, capacity, cross-user isolation, arbitrary-size performance or
provider recreation. Existing-worker `native-md-timing` execution was not
requalified; fresh `python-script` helpers were. The inherited static admission
acknowledgement can remain after the dynamic study card completes. The broader
customer-ready/all-workflow verdict remains false.
