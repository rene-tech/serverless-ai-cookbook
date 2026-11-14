# Molecular example provenance

`fixture.py` constructs the canonical 76-residue ubiquitin sequence from
[experimental structure 1UBQ](https://www.rcsb.org/structure/1UBQ) for sequence-only
prediction. The experimental coordinates are **not** submitted to prediction.

The other examples use the two-chain GCN4 leucine-zipper sequence from the pinned
[BioEmu2 example](https://github.com/microsoft/bioemu2/blob/f99e0d899a2548ee6d9d54b6854b2bc35b6652d5/examples/boltz/protein_ligand.yaml).
The A3Ms contain only the query sequence; they are not evolutionary alignments.
`gcn4-initial.cif` is a retained BioEmu2-generated GCN4 conformation with complete
native atom ordering, created with MDTraj 1.11.1.post2. It is a synthetic starting
state for transport/propagation examples, not an experimental observation or a
claim about dynamics accuracy. Its SHA-256 is
`d6e59854c4400a4ca786e5d27152ecf0b61e58ed4741c434b89452fe4e241625`.

BioEmu2 source is MIT licensed. Review the live model's hosted-use and scientific
limitations separately; this example does not grant a commercial entitlement or
clear every dependency and bundled data licence.
