# Select one hosted contract

| App | What to preserve / check |
| --- | --- |
| `rfdiffusion` | Hotspot binders use `scaffold-motif` with an uploaded PDB, actual `input_pdb_artifact_id` and receptor/design chain blocks separated by a space, e.g. `A1-150/0 70-70`. Preserve target numbering, hotspots, seed and selected model checkpoint. See the [portable binder example and schema-gated advanced controls](../../scientific-gateway/references/portable-rfdiffusion.md); unconditional generation is a different workflow. |
| `proteina-complexa` | Supply an uploaded structure and explicit `parameters.target` for a user-defined target, or choose an exact `target_id` preset from the live `target_catalog`. These are alternative inputs. Preserve chains, residue numbering, hotspots and binder lengths; see [custom targets](proteina-targets.md). |
| `boltzgen` | Use its published design specification and manifest role. Keep target entities, designed entities and constraints distinct; not the protein-only native `boltz2` App. |
| `mosaic` | Record the exact deployed implementation/version, not an assumed paper identity. Use its source bundle/config schema and retain optimization/selection metrics and failed candidates. |
| `bindcraft` | Preserve target chains, hotspots, trajectory limits and filter settings. Report no candidates passing as a result. Model access does not independently grant a PyRosetta license. |
| `bindcraft2` | Separate versioned implementation from BindCraft1. Discover authorized availability first. Submit native scientific settings and owner-local targets/scaffolds as the `campaign` tar artifact (`bindcraft2-input-tar/v1`); `parameters.input_path` selects `settings.json` by default. Preserve native modalities, chains, hotspots, lengths, seeds and filters. |
| `bindcraft2-analysis` | CPU operations are `score`, `rank`, `filter`, `campaign-output` and `archive`. Supply structures or campaign files in the same artifact contract, selecting `input_path` and the operation's live parameters. Ranking supplied scores is not a new design or refolding run. |

BindCraft2 1.0.4 does not require PyRosetta. Its native scientific settings belong
inside the uploaded settings JSON, not invented top-level MCP fields. Check the
live schema and declared continuation capabilities before a long campaign;
upstream resume support alone does not establish hosted recovery. An exhausted
campaign with zero accepted designs is a retained negative result, not an accepted
binder. Keep native acceptance filters separate from any subsequent user-defined
ranking, and never describe predicted interface scores as experimentally measured
affinity. Access is deployment-specific; do not substitute BindCraft1 when
BindCraft2 is unavailable to the current owner.

For contracts with `parameters.source.kind: uploaded-bundle`, place
`"source":{"kind":"uploaded-bundle"}` in the parameter file alongside the
scientific settings. The existing batch client replaces it with the finalized
reference for the actual source bytes; do not invent an artifact ID. Match the
entry name, semantic type, media type and compression from the live contract.

Keep `alphafold3`, `openfold3-openbind` and `protenix-v2` verification Apps
distinct from native `openfold3`/`boltz2`. `esmfold2` and `esmfold2-fast` are
separate Apps with runtime-specific limits. Monomer refolding is not target/binder
complex prediction. RFdiffusion unconditional backbone generation is not
target-conditioned design; use its distinct motif contract for that goal.
