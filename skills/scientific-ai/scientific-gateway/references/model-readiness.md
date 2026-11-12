# Model readiness and data residency

Evidence snapshot: 2026-11-12. [Detailed JSON](model-readiness.json).

The 79 entries below come from a saved authorized catalog, not a promise that every account can access every model. The original catalog was captured on 11 November 2026; later scoped receipts are joined separately. Always discover models and contracts with your own credentials.

Availability, historical successful runs and whole-release qualification are different. Positive measurement records are not unique requests; nonpositive records can include intentional negatives, bounded unfinished work or validation failures. The table preserves unknown gates instead of treating configuration or one successful run as production readiness.

## Latest scoped checks

- **RFdiffusion core:** hotspot binder design with automatic Complex base and explicit Complex beta checkpoints, plus unconditional Base backbone generation, passed ordinary REST/MCP checks on H100 in eu-north1. Three intentional negative cases were separately qualified.
- **Portable RF campaigns:** three designs completed in two sequential chunks (2+1), reusing the uploaded source. Public artifacts and owner-bucket exports matched, and completed reentry made no network or inference calls. This is not unwrapped concurrent-capacity or experimental-affinity qualification.
- **BindCraft2:** version 1.0.4 design/analysis contracts are discoverable for approved internal research identities. Earlier bounded design/rank runs retain their exact scope. Ordinary typed-MCP CPU score passed under SYSTEM and an explicitly authorized existing owner, with public REST/MCP results, four downloadable artifacts and complete owner export verified. The bounded GPU example also passed on L40S in eu-north1: one attempt, seven finite structures, one native-filter-accepted design, and 18 public artifacts plus the complete owner export verified. These computational outcomes are not experimental binding or calibrated affinity/Kd.
- **ProteinMPNN:** one ordinary typed-MCP request using inline PDB input, scalar temperature `0.1` and 100 requested sequences passed on L40S in eu-north1. All 100 sample labels, 20-residue outputs, probability normalization, REST/MCP results and two owner-export files were verified. File upload, larger structures and concurrent capacity were not exercised by this check.
- **Recorded usage:** eight retained owned handles, including failed/cancelled stages and existing recovery-family handles, matched across REST, typed MCP and native data. Two foreign-owner reads were denied. Unknown values remain unknown; this does not certify final invoices, credit balances or arbitrary family sums.
- **Catalog changes:** actual modern subscription initial notification/refetch, deliberate client reconnect and legacy revision polling passed. Live catalog/grant mutation, forced server disconnection and selection of both backend replicas were not demonstrated; dynamic-change/revocation checks retain separate CPU-test scope.
- **RFdiffusion advanced controls:** three bounded H100 workflows passed scientific/output checks: partial diffusion with sequence preservation, motif masking with compactness guidance, and C2 symmetry with zero noise plus contact guidance. The first two retain the sampling release; C2 uses the corrected launcher release. This does not qualify every option combination or every GPU/region.
- **Hosted RF campaign:** one typed-MCP operation completed 65 hotspot backbones on H100 in eu-north1, in nine single-attempt GPU chunks with `max_parallelism=4`. All structures, ten public artifacts, eleven owner-export files and whole REST/MCP results were verified. Partial output was available during execution; later chunks started after client disconnect, and portable result recovery made no new inference. The 1,000-design template remains CPU-only; all-GPU capacity, experimental affinity and the separate LibreChat study template are unqualified.

- **Admission reservation reporting:** one intentional CPU-only failure reported a held root reservation through REST and typed MCP; one explicit cancellation changed it to released, matching native status and account reservation counts of 0 → 1 → 0. No GPU attempt ran. Retained 65-design RFdiffusion and 100-sequence ProteinMPNN status/result metadata remained unchanged apart from the added released-state field where applicable. This does not prove automatic release after a delay.

## Residency boundaries

Configured execution regions are eligibility declarations, not proof of placement for every request. Actual execution and the owner bucket region are separate. Read the authenticated `/v1/storage` binding for your bucket endpoint/region. This snapshot does not perform an all-write-path audit or certify PHI, clinical use or regulatory residency.

Chai-1 external MSA/template search is explicitly opt-in and can transmit submitted sequences. Local or user-supplied inputs are separate. No blanket external-service claim is made for other models.

## Model matrix

| Model | Configured execution regions | Historical positive / total records | Recent scoped passes (ordinary / pinned / other) | Full current release |
| --- | --- | ---: | ---: | --- |
| abodybuilder3 | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| ace-step-1-5 | eu-north1 | 7 / 10 | 0 / 0 / 0 | not established |
| admet-ai | eu-north1 | 2 / 2 | 0 / 0 / 0 | not established |
| alphafold3 | eu-north1, eu-south1 | 8 / 8 | 0 / 0 / 0 | not established |
| altumage | eu-north1, eu-south1 | 8 / 8 | 0 / 0 / 0 | not established |
| amber | eu-north1, eu-south1 | 66 / 68 | 0 / 0 / 0 | not established |
| antifold | eu-north1, eu-south1 | 0 / 0 | 0 / 3 / 0 | not established |
| Independent Qwen3.6 27B FP8 App | eu-north1 | 6 / 7 | 0 / 0 / 0 | not established |
| Protenix independent App | eu-north1 | 6 / 7 | 0 / 0 / 0 | not established |
| bindcraft | eu-north1 | 1 / 7 | 0 / 0 / 0 | not established |
| bindcraft2 | eu-north1 | 0 / 0 | 3 / 4 / 0 | not established |
| bindcraft2-analysis | eu-north1 | 0 / 0 | 4 / 1 / 0 | not established |
| bioemu2 | eu-north1, eu-south1 | 9 / 9 | 0 / 0 / 0 | not established |
| boltz2 | eu-north1 | 7 / 7 | 0 / 0 / 0 | not established |
| boltzgen | eu-north1 | 6 / 8 | 0 / 0 / 0 | not established |
| cellpose-cpsam-v2 | eu-north1, eu-south1 | 7 / 7 | 0 / 0 / 0 | not established |
| chai1 | eu-north1, eu-south1 | 0 / 0 | 2 / 3 / 0 | not established |
| cosmos-transfer2-5-2b | eu-north1 | 6 / 8 | 0 / 0 / 0 | not established |
| cosmos3-lerobot-augmentation | eu-north1 | 3 / 3 | 0 / 0 / 0 | not established |
| cosmos3-nano | eu-north1 | 11 / 11 | 0 / 0 / 0 | not established |
| ctoxpred2 | eu-north1 | 2 / 2 | 0 / 0 / 0 | not established |
| diar-streaming-sortformer-4spk-v2-1 | eu-north1, eu-south1 | 8 / 8 | 0 / 0 / 0 | not established |
| diffdock | eu-north1, eu-south1 | 8 / 8 | 0 / 0 / 0 | not established |
| esm-if1 | eu-north1, eu-south1 | 0 / 0 | 0 / 3 / 0 | not established |
| esm2-3b | eu-north1, eu-south1 | 3 / 3 | 0 / 0 / 0 | not established |
| esm2-650m | eu-north1, eu-south1 | 3 / 3 | 0 / 0 / 0 | not established |
| esmc-300m | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| esmc-600m | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| esmc-6b | eu-north1, eu-south1 | 0 / 0 | 1 / 2 / 0 | not established |
| esmfold2 | eu-north1, eu-south1 | 8 / 8 | 0 / 0 / 0 | not established |
| esmfold2-fast | eu-north1, eu-south1 | 8 / 8 | 0 / 0 / 0 | not established |
| evo2-40b | eu-north1 | 5 / 5 | 0 / 0 / 0 | not established |
| genmol | eu-north1 | 7 / 7 | 0 / 0 / 0 | not established |
| gromacs | eu-north1, eu-south1 | 87 / 91 | 0 / 0 / 0 | not established |
| gromacs-mpi | eu-north1, eu-south1 | 78 / 82 | 0 / 0 / 0 | not established |
| holoscan-endoscopy | eu-north1, eu-south1 | 4 / 4 | 0 / 0 / 0 | not established |
| igbert | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| isaac-healthcare | eu-north1, eu-south1 | 1 / 1 | 0 / 0 / 0 | not established |
| isaac-healthcare-interactive | unknown | 0 / 2 | 0 / 0 / 0 | not established |
| lammps | eu-north1, eu-south1 | 53 / 71 | 0 / 0 / 0 | not established |
| magpie-tts-multilingual-357m | eu-north1 | 6 / 14 | 0 / 0 / 0 | not established |
| mdprecheck | eu-north1 | 2 / 2 | 0 / 0 / 0 | not established |
| mindguard-4b | eu-north1 | 8 / 9 | 0 / 0 / 0 | not established |
| mindguard-8b | eu-north1 | 8 / 9 | 0 / 0 / 0 | not established |
| molmim | eu-north1, eu-south1 | 8 / 8 | 0 / 0 / 0 | not established |
| monai-spleen-ct | eu-north1, eu-south1 | 4 / 4 | 0 / 0 / 0 | not established |
| mosaic | eu-north1, eu-south1 | 8 / 13 | 0 / 0 / 0 | not established |
| msa-search-pdb70 | eu-north1 | 2 / 2 | 0 / 0 / 0 | not established |
| namd | eu-north1, eu-south1 | 68 / 78 | 0 / 0 / 0 | not established |
| nanobodybuilder2 | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| nemotron-speech-en-0-6b | eu-north1, eu-south1 | 8 / 10 | 0 / 0 / 0 | not established |
| nemotron-speech-en-medical-0-6b | eu-north1 | 8 / 11 | 0 / 0 / 0 | not established |
| nemotron-speech-multilingual-0-6b | eu-north1, eu-south1 | 8 / 11 | 0 / 0 / 0 | not established |
| nv-reason-cxr-3b | eu-north1 | 7 / 7 | 0 / 0 / 0 | not established |
| nv-segment-ct | eu-north1 | 7 / 14 | 0 / 0 / 0 | not established |
| openfold2 | eu-north1, eu-south1 | 7 / 7 | 0 / 0 / 0 | not established |
| openfold3 | eu-north1, eu-south1 | 8 / 15 | 0 / 0 / 0 | not established |
| openfold3-openbind | eu-north1, eu-south1 | 9 / 15 | 0 / 0 / 0 | not established |
| openmm | eu-north1, eu-south1 | 66 / 73 | 0 / 0 / 0 | not established |
| parakeet-realtime-eou-120m-v1 | eu-north1, eu-south1 | 8 / 9 | 0 / 0 / 0 | not established |
| phenoage | eu-north1 | 2 / 2 | 0 / 0 / 0 | not established |
| proteina-complexa | eu-north1, eu-south1 | 6 / 9 | 0 / 0 / 0 | not established |
| proteinmpnn | eu-north1, eu-south1 | 8 / 9 | 1 / 0 / 0 | not established |
| protenix-v2 | eu-north1 | 7 / 13 | 0 / 0 / 0 | not established |
| pyrosetta-interface-metrics | eu-north1, eu-south1 | 2 / 2 | 0 / 0 / 0 | not established |
| qwen3-6-27b-fp8 | eu-north1 | 6 / 10 | 0 / 0 / 0 | not established |
| qwen3-8b | eu-north1 | 7 / 7 | 0 / 0 / 0 | not established |
| rfd4-proteina | eu-north1, eu-south1 | 9 / 12 | 0 / 0 / 0 | not established |
| rfdiffusion | eu-north1 | 6 / 7 | 6 / 0 / 0 | not established |
| rosetta-flex-ddg | eu-north1, eu-south1 | 2 / 2 | 0 / 0 / 0 | not established |
| sam2-1-hiera-large | eu-north1, eu-south1 | 9 / 12 | 0 / 0 / 0 | not established |
| saprot-1-3b | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| saprot-650m | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| saprot-inverse-folding | eu-north1, eu-south1 | 0 / 0 | 1 / 3 / 0 | not established |
| scvi-scanvi | eu-north1, eu-south1 | 8 / 11 | 0 / 0 / 0 | not established |
| sdxl | eu-north1 | 7 / 7 | 0 / 0 / 0 | not established |
| stab-ddg | eu-north1, eu-south1 | 1 / 2 | 0 / 0 / 0 | not established |
| wan2-2-i2v-nim | eu-north1 | 5 / 5 | 0 / 0 / 0 | not established |
| wan2-2-t2v-nim | eu-north1 | 5 / 6 | 0 / 0 / 0 | not established |

The JSON records operations, per-GPU observations, tested scope and explicit unknown recovery, isolation, capacity and notebook gates. Exact private operational identities and provenance stay with the maintainers. Missing or untested evidence is not hardware incompatibility.
