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
