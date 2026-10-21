# Input semantics and provenance

Adapted from the public RosettaCommons/NVIDIA RFD4-Proteina generation and
annotated-CIF skills at source revision
`ed63183a7f2703a6dc2e4add3314c265b7e4ffcb`.
The hosted candidate uses the matched public flow/autoencoder bundle from
`nvidia/RFD4-Proteina` revision `a06e2509c7033b010fc43614e9fd840303588502`.
The live App schema and its release evidence remain authoritative; these pins
are provenance, not proof that every upstream workflow is hosted or qualified.

## Choose an input, not a different model

- **Unconditional generation:** the pinned upstream
  [monomer-short.cif.zst](https://github.com/RosettaCommons/RFD4-Proteina/blob/ed63183a7f2703a6dc2e4add3314c265b7e4ffcb/data/benchmarks/monomer/monomer-short.cif.zst)
  specifies a 100-residue monomer. It is a design specification, not a known
  experimentally validated output. Decompress to a new `.cif` before upload.
- **Conditional generation:** use validated annotations for known sequence,
  fixed coordinates, target hotspots or motif regions. Clearly identify which
  parts the model must design. A target structure alone does not define a binder
  design task; hotspot conditioning is trained with the target sequence and
  coordinates conditioned and the partner generated.
- **Partial diffusion:** supply the intended existing structure and explicit
  supported partial-diffusion setting; do not reinterpret it as unconditional
  generation or promise a particular RMSD.

For authoring, use the pinned upstream
[annotated-CIF workflow](https://github.com/RosettaCommons/RFD4-Proteina/blob/ed63183a7f2703a6dc2e4add3314c265b7e4ffcb/skills/rfd4-proteina-annotated-cif/SKILL.md)
and [annotation reference](https://github.com/RosettaCommons/RFD4-Proteina/blob/ed63183a7f2703a6dc2e4add3314c265b7e4ffcb/docs/reference/annotations.md).
Import `rfproteina.conditions` before parsing with the pinned authoring libraries;
otherwise annotation columns can be lost. Inspect masks, chains, chemistry and
conditioning counts, then save/reload and compare the intended annotations.
Do not claim these authoring tools exist locally unless their imports succeed.
The hosted API does not install them, fetch arbitrary paths or accept Hydra/YAML
overrides. Stop with the missing preparation requirement rather than dropping it.

Generated CIFs can contain input/provenance annotations (`SA_SRC`, `SA_CRDSRC`,
`SA_IDXGRPSRC`, `SA_UII`). Preserve them for scientific analysis; use a derived
display copy only if the viewer requires conversion. A coordinate viewer is not
an annotation/adherence validator.

Scope adaptation: upstream GPU setup, scheduler flags, local checkpoint paths,
optional oracle containers, beam search and evaluation commands are deliberately
not copied into this hosted skill. They are not accepted model parameters.
The upstream BSD notice is retained in [LICENSE](../LICENSE).
