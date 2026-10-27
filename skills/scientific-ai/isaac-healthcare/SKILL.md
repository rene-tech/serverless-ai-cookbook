---
name: isaac-healthcare
description: Run finite Isaac for Healthcare simulations with scenario seeds, recorded trajectories, RGB sensors and explicit task outcomes, through Scientific AI or the standalone Docker/Serverless recipe.
license: Apache-2.0
---

# Isaac for Healthcare simulation

For hosted execution, discover App `isaac-healthcare` with `get_model_schema`
and use its current typed tool, expected `submit_isaac_healthcare`. Use existing
scientific artifact upload/finalization and durable operation polling. Do not
infer availability from this skill or substitute another App when absent.

The initial workflow is the actual i4h v0.9.0 **rule-based scissor pick-and-place**
simulation. Upload one `scenarios` artifact with semantic type
`isaac-healthcare-scenarios/v1`, MIME `application/json`, compression `none`:

```json
{"schema":"isaac-healthcare-scenarios/v1","scenarios":[{"name":"baseline","seed":17}]}
```

Submit operation `simulate`. Preserve requested episodes, attempts, seeds,
physics and camera settings. Null `episode_steps` uses the upstream 600-step
scene cap at 60 Hz; an explicit lower cap may produce an unfinished task. Names
are arbitrary scientific labels. Do not introduce fixture hashes or rename
inputs to make optimization work.

Retain the operation/idempotency identity after submission and resume polling
that operation after disconnect. Download `result.json` and `simulation.tar`
through their artifact references. Inspect HDF5 actions/joints, room/wrist RGB,
initial state, task segments, patch/asset provenance and terminal outcomes. An
explicit `cameras=false` run must contain no camera images. Report `task_complete=false`
as unsuccessful simulation task completion even when structural validation
passed. HDF5 v1 excludes the termination/reset sample, so the last recorded
image is not the final success criterion. No claim of clinical validity follows.

For on-premises or provider Serverless execution, use the standalone
[recipe](../../../templates/job-isaac-healthcare/README.md). It shares the exact
portable execution package with the hosted worker and needs no Scientific AI
token. Check the operator's NVIDIA simulator/component/asset terms before
accepting the EULA. Use RTX-capable hardware; H100/H200 do not provide Isaac
rendering's RT cores. Stage HDF5 on local POSIX scratch before copying completed
files to object storage.

Do not infer support for learned policies, training, interactive WebRTC,
ultrasound or physical-device control from this workflow. Those modes require
their own contracts and execution evidence. Preserve real simulator errors,
partial results and cancellation state rather than rerunning accepted work.
