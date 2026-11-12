# Binding predictions and interface geometry

Start from a defined protein–protein complex and explicit partner chains. A
mutation to a residue absent from the structure is an input problem, not a zero
effect. Record original chain/residue/insertion identifiers and any derived
mapping. Unresolved atoms, nonstandard residues and assembly ambiguity must remain
visible. These methods do not replace experimental affinity or specificity tests.

## StaB-ddG

Discover `stab-ddg` and use its live schema. This is the learned StaB-ddG model,
not a generic folding-stability calculation. Positive predicted binding ΔΔG means
weaker binding under the model's mutant-minus-wild-type convention. Confirm the
returned sign and units; retain the checkpoint and full multi-mutation request.

Upload one **uncompressed tar** as manifest entry `workload`, semantic type
`stab-ddg-workload-tar/v1`, MIME `application/x-tar`, compression `none`.
`parameters.pdb_file` resolves from the archive root, without an enclosing-folder
rewrite. The PDB must contain one explicitly selected structural model and the
requested partner chains. Put partner and mutation definitions in typed
parameters, **not an uploaded mutation CSV**; the runtime produces its own
upstream CSV from these verified fields.

For a complex whose actual chain A residue 27 is ARG, the parameter shape is:

```json
{
  "pdb_file": "complex.pdb",
  "partner_a": ["A"],
  "partner_b": ["B"],
  "variants": [{"id": "R27P", "mutations": [
    {"chain": "A", "residue_number": 27, "insertion_code": "", "wild_type": "R", "mutant": "P"}
  ]}]
}
```

This is a shape example, not evidence that residue 27 is ARG in your structure.
Verify original PDB chain/residue/insertion identifiers and N/CA/C/O at each
mutation site. Partner chain sets must be disjoint; variant IDs and mutated
sites within a variant must be unique. Package `complex.pdb` at the tar root
with `tar -cf workload.tar complex.pdb`, then use the portable batch helper with
`--model stab-ddg --tool submit_stab_ddg --operation predict-binding-ddg`, the role/MIME above,
your parameter file, and one new output directory/stable idempotency key.

The current adapter defaults are 20 Monte Carlo draws, seed 0, 0.1 Å backbone
noise and a 10,000-token microbatch. Confirm the live defaults and retain the
actual values; changing the noise changes the scientific protocol. Sampling
standard error is unknown for one draw, not zero. Variation across draws is
computational sampling variation, not calibrated experimental uncertainty. Do
not rank two near-equal predictions as a proven physical difference.

## PyRosetta interface metrics

Discover `pyrosetta-interface-metrics`. State the requested interface and retain
the score function, packing options and seed. Report buried solvent-accessible
area in Å², dimensionless shape complementarity and dimensionless PackStat under
their returned definitions. Do not divide dSASA by two or call interface energy
mutation ΔΔG without an explicit matching definition. PackStat is stochastic;
compare matched sampling settings.

Packing and relaxation can alter the input structure. Request them only when
scientifically intended and preserve the original. InterfaceAnalyzer's supported
protein–protein use does not establish protein–ligand applicability.

## Flex ddG

Discover `rosetta-flex-ddg`. Use the pinned published backrub ensemble and its
WT/mutant bound/unbound calculations. A quick InterfaceAnalyzer score, a single
relaxed structure or a mutation-only energy difference is not Flex ddG.

The published protocol recommends 35 independent trajectories and 35,000 backrub
trials per trajectory. Its short tutorial smoke example is explicitly
insufficient for a scientific conclusion. Report the actual protocol, replicates,
seed, score function, convergence and ensemble spread. Rosetta energy units are
not automatically physical kcal/mol. Preserve raw state/replicate outputs so a
reported mutation effect can be reconstructed.

The pinned Rosetta resfile parser supports blank or uppercase-letter insertion
codes for mutations. If an input uses a different code, retain it and explain
the parser limitation; do not silently change the mutation target. Any agreed
derived numbering must preserve a checked original-to-derived mapping.

Primary sources: [StaB-ddG](https://github.com/LDeng0205/StaB-ddG),
[Rosetta InterfaceAnalyzer](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer),
[published Flex ddG implementation](https://github.com/Kortemme-Lab/flex_ddG_tutorial).
