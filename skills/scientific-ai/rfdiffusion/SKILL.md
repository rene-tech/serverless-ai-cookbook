---
name: rfdiffusion
description: Generate research protein backbones or scaffold motifs with the rfdiffusion scientific batch model (operations design-backbone and scaffold-motif).
license: Apache-2.0 AND CC-BY-4.0
---

# rfdiffusion (scientific batch)

Public model ID `rfdiffusion`; MCP `submit_rfdiffusion` or
`submit_scientific_run` (`model_id: "rfdiffusion"`). Shared batch mechanics
(artifact upload, run document, polling): `scientific-batch`.

## Run document

`operation` selects `"design-backbone"` or `"scaffold-motif"`; `parameters`
come from `get_model_schema` and its `input_artifact_contract`; customers do
not need the operator's source checkout. For `design-backbone`, upload a
text/plain human-readable provenance note, not a PDB; typed `contigs`,
`num_designs`, `seed` and `diffuser_T` determine this unconditional run.
For `scaffold-motif`, follow that operation's distinct published source role
and structure contract. Reference the finalized manifest in `input_manifest`.
Suggested `service_class: "customer-batch"`
unless the key grants otherwise.

For a campaign, read [hosted campaign usage](../scientific-gateway/references/portable-campaign.md)
and check whether the live schema advertises `parameters.campaign`. Use one
normal typed submission with `campaign.total_designs` and `max_parallelism`;
`num_designs` becomes the 1–64 design batch size per GPU chunk. Preserve one
manifest/key/operation and inspect partial-result counts and account admission
reservations. A root reservation is not a GPU-capacity limit. The linked guide
records a verified 65-design hotspot campaign; its 1,000-design template retains
CPU-only planning evidence, not measured throughput or scientific success.

## Result

Designed backbone PDB/mmCIF artifacts. Chain into `proteinmpnn` (sequence
design) and a structure model (verification) per `protein-binder-design`.
Backbones are research hypotheses, not demonstrated binders. Check release
evidence for the exact runtime and workflow; this skill is not a live-readiness
certificate.
