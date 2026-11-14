# Example provenance

`fixture.py` uses only Python's standard library and creates no cloud resources.
It makes deterministic USTAR/gzip archives; it does not upload them or obtain credentials.

- `predict`: the 76-residue ubiquitin sequence from [wwPDB 1UBQ](https://www.rcsb.org/structure/1UBQ), made available under the wwPDB CC0 policy. One UTF-8 `input.fasta`, SHA256 `b1a50848a1aee66d91c1824749e13ce89650ff3aadb40bb08099f2a3444bd569`, 197 archive bytes. The archive contains the sequence only; no reference coordinates enter prediction.
- `msa-convert`: synthetic `ACDEFG` query and `ACdDEFG` insertion homolog in `hits_uniref90.a3m`. No biological homology or pairing is claimed. SHA256 `1f3425e807bf95fc36aec19919edfcb83f65b6dc138d4f26a6369f18025374fa`, 155 archive bytes. This is an input-format example, not a scientifically useful MSA.

Use one fresh request directory/idempotency key for each operation, and upload the exact generated archive to your own bound bucket. Availability and qualification come from the live model/workflow catalog, not this fixture.
