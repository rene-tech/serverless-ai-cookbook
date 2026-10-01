# Small-molecule force fields for GROMACS

Choose a method compatible with the rest of the system. For a question asking
what to use, explain the options and the compatibility decision; do not run a
parameterization or demand temperature, timestep and simulation length first.
Do not invent exact stereocentre/atom counts by visually reading SMILES.

## Selection

- **Amber-family protein setup:** GAFF2 with a stated charge method (often
  AM1-BCC) is a conventional ligand route. AmberTools prepares parameters;
  use a validated converter such as ACPYPE or ParmEd for GROMACS. `pdb2gmx`
  does not parameterize arbitrary small-molecule ligands.
- **CHARMM-family protein/membrane setup:** consider CGenFF, checking its
  parameter and charge penalty scores. Availability/licensing and parameter
  quality are separate questions; a large penalty needs investigation, not an
  invented assurance. Do not claim one family is universally less accurate.
- **OpenFF:** Sage is the OpenFF **2.x** small-molecule force-field family;
  Parsley is **1.x**. Pin a specific `.offxml` version. The Toolkit assigns
  parameters; Interchange exports them to GROMACS. Assess compatibility with
  protein/lipid/water parameters, nonbonded conventions and 1–4 interactions
  when combining components. Engine-readable files alone do not prove validity.

Keep these distinctions precise: Sage is a small-molecule force field, not a
replacement protein force field. Standard Sage and CHARMM use Lorentz–Berthelot
mixing (arithmetic size, geometric well depth); do not invent a difference there.
Combining components still requires validating the exact parameter sets and
special pair terms. Sage 2.2.1 scales 1–4 LJ by 0.5 and electrostatics by 1/1.2;
CHARMM uses unscaled 1–4 electrostatics and atom-type-specific 1–4 LJ parameters.
CGenFF is the conventional starting point with CHARMM36m; check penalty scores
and refine uncertain parameters. Neither successful export nor a finite energy
proves predictive accuracy. Do not prescribe reparameterizing a protein with Sage.
See the [CHARMM-GUI compatibility FAQ](https://charmm-gui.org/?doc=faq) and
[SMIRNOFF specification](https://openforcefield.github.io/standards/standards/smirnoff/).

For an isolated organic ligand, OpenFF Sage is a reasonable option, not a
guarantee of molecule-specific accuracy. For a receptor-bound ligand, ask which
protein/membrane force-field family is being used only if needed to finalize the
choice. A supplied SMILES fixes chemical identity/stereochemistry only to the
extent it is fully specified; preserve the exact string and validate it with
RDKit/OpenFF rather than manually rewriting it.

## CPU preparation and dependencies

The RDKit + AmberTools AM1-BCC + OpenFF Sage preparation path does not require a
GPU. CUDA belongs to the later simulation stage if the chosen engine uses it.
AM1-BCC/SQM, conformer generation and export can run on CPUs. Do not silently
substitute NAGL or another charge model merely because it is installed or faster.

Check the selected Python environment once for `openff.toolkit`,
`openff.interchange`, force-field data and the selected charge backend. The
workbench's ordinary analysis interpreter is `/opt/scientific-client/bin/python`;
the presence of RDKit there does not establish that OpenFF is installed.
If OpenFF is absent, report the missing dependency and affected deliverables.
Do not explore every interpreter or try pip/apt/conda installations inside a
customer's task. An operator-prepared environment is a separate setup step.
Official OpenFF installation uses conda-forge, which supplies the coordinated
dependencies; do not force-install yanked unofficial PyPI packages.

When the operator has provisioned `/opt/openff/bin/python`, use the packaged
`/opt/bionemo/prepare-openff.py --help` and run that helper with the exact SMILES,
an explicit installed Sage `.offxml`, and a fresh output directory. It uses CPU
AmberTools AM1-BCC, writes GROMACS files and a hash manifest, and keeps charges
if a later export fails. It creates an **artificial empty export box**, not a
solvated MD-ready system. Do not claim `grompp` or cross-engine energy validation:
the helper does not perform them. Its receipt states the checks actually made.
If this interpreter is absent, stop with that concrete dependency; do not hunt
for or create temporary environments in a customer's chat.

## Execution contract

When execution is requested and dependencies are present:

1. Parse and validate identity, stereochemistry, protonation/formal charge.
2. Generate or preserve the requested conformer, recording the method/seed.
3. Assign the chosen partial charges once and persist them for reuse. Check
   charge sum, missing parameters and conversion conventions.
4. Use the installed Toolkit/Interchange API to create and export the system.
   The documented shape is `forcefield.create_interchange(topology)` followed
   by `interchange.to_gromacs(prefix="system")`. Consult the installed version's
   documentation for options; do not invent constructor or export arguments.
5. Verify the actual `.top`/included topology files and `.gro`, their atom
   identity/order, charges, bonded/nonbonded parameters and units. Preserve
   versions, force-field digest, commands, seeds and the charge method. A lone
   `system.xml` is not the requested GROMACS input bundle.

Missing files, failed export or a nonzero exit code means incomplete work. Do
not recompute charges to repair a reporting-only bug when the charges have been
saved. A final result must identify the actual files, not a planned file list.

## Primary references

- [Official installation](https://docs.openforcefield.org/en/latest/install.html)
- [Toolkit optional backends](https://docs.openforcefield.org/projects/toolkit/en/stable/installation.html)
- [Official Sage-to-GROMACS/Amber example and validation](https://docs.openforcefield.org/en/latest/examples/openforcefield/openff-toolkit/using_smirnoff_in_amber_or_gromacs/export_with_interchange.html)
- [Interchange](https://docs.openforcefield.org/projects/interchange/en/stable/)
- [GAFF](https://ambermd.org/antechamber/gaff.html)
- [CGenFF](https://mackerell.umaryland.edu/charmm_ff.shtml#cgenff)
