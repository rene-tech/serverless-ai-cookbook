---
name: binder-design-campaigns
description: Plan and run bounded hosted RFdiffusion, Proteina-Complexa, BoltzGen, Mosaic, BindCraft or BindCraft2 campaigns, retaining target identity, seeds, filters, artifacts and negative candidates. Use for comparative binder-design batches and follow-up evaluation, not unsupported upstream deployment recipes.
license: Apache-2.0 AND CC-BY-4.0
---

# Binder-design campaigns

Read `scientific-batch` for transport and `protein-binder-design` for the
RFdiffusion/ProteinMPNN route. Adapt domain guidance from NVIDIA BioNeMo's
Complexa target/design/sweep/evaluate skills to these hosted Apps; do not launch
upstream Docker/NGC services or assume an upstream CLI flag is a gateway field.

## Freeze the experiment

Record target identity, selected chains/epitope, intended design operation,
sequence/structure source, binder constraints, exact model/runtime, seeds,
candidate count and filter thresholds. Define acceptance metrics and budget
before submitting a sweep. A PDB filename is not necessarily a target task ID.
Ask only for missing scientific choices, not approval already given for the run.

Read [model distinctions](references/model-contracts.md) for the selected App,
then its live `get_model_schema`, parameter schema and `input_artifact_contract`.
Do not load every model schema when only one is being used.
For Proteina-Complexa, read [custom targets](references/proteina-targets.md):
an uploaded target structure, selected chains/residues, hotspots and binder
lengths define a user target. Catalog tasks are optional presets; do not replace
the user's target with a preset or infer unsupported status from a missing ID.

## Execute and evaluate

For RFdiffusion, prefer the [hosted campaign contract](../scientific-gateway/references/portable-campaign.md)
when advertised by the live schema: one typed operation, finalized manifest,
key and result prefix. `num_designs` is then the 1–64 design batch size;
`campaign.total_designs` and `max_parallelism` bound total work and eligible
GPU chunks. Check the guide's qualification boundary and account capacity;
root admission reservations are not GPU counts. The retained local campaign
helper is client-driven compatibility, not a hosted background owner.
In LibreChat, register a complete durable study for additional models and
dependent analyses, using one batch phase for this hosted campaign. See the
[RFdiffusion study example](references/rfdiffusion-study.md). Connecting plain
MCP does not install LibreChat's study tools.
Each distinct parameter/seed combination has one stable
idempotency key and receipt directory. Respect queue/concurrency policy; pending
capacity is not a reason to change a key. Preserve failed/filtered/empty outputs
in the campaign table. Do not loosen filters or select only successful seeds to
make a campaign appear successful.

Unknown admission fences additional requests. Reconcile only the saved exact request
and key; observe already accepted IDs without replacement submissions. A failed
or held child is not permission to replay science. Stopping new admissions does
not cancel existing work; use its supported operation control explicitly.

Retain partial-result manifests when present; incomplete work is not full success.
Download every manifest-declared design, sequence and score artifact; verify
hashes before interpreting them. Compare exact chains and residue numbering
when refolding or computing RMSD/contacts. Use the existing design-artifact,
structure and report phases where available. Retain candidate lineage from
target and seed through sequence, backbone, refold and final selection.

Report per-model candidate counts, accepted/rejected filters, measured latency,
queue time if available, and compute usage only when returned/measured. Scores
from different model families are not calibrated to each other. Confidence,
contacts and RMSD do not prove binding or efficacy; shortlisted designs remain
research hypotheses for independent evaluation.
