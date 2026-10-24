---
name: protein-scoring
description: Compare protein variants, binder interfaces and developability using ESM-2, StaB-ddG, PyRosetta interface metrics or Flex ddG; route FoldX and CamSol requests when those licensed tools are available.
---

# Protein scoring

Choose the measurement that answers the question. These tools produce different
quantities; do not combine their raw values into an unexplained overall score.

| Question | Tool and interpretation |
| --- | --- |
| Which substitutions are favoured by a protein language model? | ESM-2 650M or 3B: sequence log scores, not physical energies. Read [ESM-2](references/esm2.md). |
| How does a mutation change protein–protein binding? | StaB-ddG: learned binding ΔΔG prediction. Flex ddG: the published Rosetta ensemble protocol. Read [binding and interfaces](references/binding.md). |
| How well does an existing interface pack? | PyRosetta: buried solvent-accessible area, shape complementarity and PackStat. These describe a structure, not experimental affinity. |
| Is a variant stable or soluble? | FoldX and CamSol measure different properties. Read [licensed methods](references/licensed-methods.md) and check actual availability first. |

Use `scientific-gateway` to discover the caller's authorised Apps and their live
input schemas. Model availability and licensed access come from that response,
not this installed skill. Do not invent a tool, silently swap a model, or install
a restricted package when the requested App is unavailable. Once the exact tool
is found, use it without repeated discovery searches.

Use `scientific-batch` for owned-file upload, submission, observation and verified
result recovery. Preserve the returned native operation ID; never resubmit to
obtain a report. Inputs may come from the user's structures or verified design
outputs from RFD4, Proteina-Complexa, BindCraft, BoltzGen or ProteinMPNN. Keep their
sequence and chain identifiers traceable to the scoring input. A predicted
complex does not become an experimentally validated binding pose by being scored.

Before submission, resolve the reference sequence/structure, biological assembly,
partner chains and mutation numbering. Validate the wild-type residue at every
site, including insertion codes. Ask only about consequential ambiguities; do
not silently renumber, truncate, relax, drop chains, change protonation, or remove
ligands. Record any explicitly selected preparation separately from the original.

Report a sortable table with candidate identifiers, original mutations, score,
units, sign convention, checkpoint/protocol, preparation, seed/ensemble size and
warnings. Keep model scores, computational sampling error and predictive
uncertainty distinct. Compare methods on matched inputs and settings; ESM length
normalisation and Rosetta score-function choices matter. Inspect agreement and
disagreement rather than claiming that several correlated scores prove efficacy.

For a requested report, create a complete HTML report from verified results and
render it inline using the workbench's owned-workspace preview. CSV/JSON downloads
are supplementary. Include missing or failed results explicitly and retain their
actionable error and operation ID. Report measured variants/sequences/residues
and rates when available; do not expose internal GPU or scheduling details.
