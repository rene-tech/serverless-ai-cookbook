# AMBER sources and scope

- [AMBER 2026 reference manual](https://ambermd.org/Manuals.php): MDIN, PMEMD,
  supported ensembles, precision, continuation, TI and AmberTools commands.
- [Official PMEMD and AmberTools distribution](https://ambermd.org/GetAmber.php):
  distinct engine/tool packages, standalone PMEMD26 and academic terms.
- [AmberTools](https://ambermd.org/AmberTools.php): preparation and analysis
  tools; upstream availability is not proof that every tool is exposed here.
- [Official tutorials](https://ambermd.org/tutorials/): method-specific examples;
  match versions, force fields and native inputs before adapting a protocol.
- [CPPTRAJ manual](https://amberhub.chpc.utah.edu/): trajectory analysis and
  topology/frame handling.

The portable skill is Apache-2.0 guidance. PMEMD's licence is separate. Never
upload its private source or runtime binaries with a scientific input bundle.
Only existing App grants authorize access; no separate academic authentication
mechanism is required.

Current typed preparation/analysis steps are LEaP, CPPTRAJ, ParmEd,
Antechamber/parmchk2 and MMPBSA.py, in addition to PMEMD dynamics. Discover the
deployed schema before using these: older images expose only the first three
tools. SANDER is used by MMPBSA internally, not exposed as an unrestricted native
execution command. Package presence alone is not end-to-end qualification.

AMBER26 manual sections23.6.10 and23.7 describe stochastic cell rescaling and
the neighbor-list skin, respectively. Preserve exact settings in the report;
different engines do not use identical thermostat/barostat algorithms.
