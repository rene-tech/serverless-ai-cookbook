---
name: isaac-healthcare
description: Author and run Isaac for Healthcare scenes, tasks and workflows for robotics simulation, demonstration recording, replay, policy training and interactive research sessions through Scientific AI or the portable recipe.
license: Apache-2.0
---

# Isaac for Healthcare

Treat Isaac for Healthcare as the Scene + Task + Workflow framework. Scissor
pick-and-place is one example, not the user's required target or an eligibility
condition. Preserve the requested robot, anatomy, sensors, controller, physics,
training objective and assets. Use the pinned upstream framework's authoring
interfaces for a new task rather than disguising it as a bundled example.

Discover `isaac-healthcare` for finite batch/data/training and
`isaac-healthcare-interactive` for GUI/teleoperation with `get_model_schema`.
Use each model's current typed tools and capabilities. Upload artifacts for the
same model you intend to invoke; access to one model is not an upload grant for
the other. This guide or an image publication does not enable a hosted mode. A workflow appearing in the SDK registry means it is
discoverable; successful execution additionally depends on its assets, policy
environment, device capabilities and the qualified deployment. Report a missing
capability directly instead of substituting the scissor demo or another App.

## Projects and batch work

The general project contract uses a tenant-owned `project` TAR artifact with
semantic type `isaac-healthcare-project-tar/v2`, MIME `application/x-tar` and
compression `none`. Inspect the live schema for any changes before upload.
The archive can contain:

- `project.json`: optional default workflow/mode, relative Python package paths
  and an asset root, using `isaac-healthcare-project/v2`.
- `overlay/`: SDK-layout scenes, tasks, workflows, manifests and source packages
  merged into a private per-operation SDK tree.
- `data/`: local assets, recordings, policy checkpoints, anatomy and patient-twin
  configurations. Parameter paths refer to this archive, not the client machine.

An optional `scenarios` JSON artifact supplies labels and reset seeds:

```json
{"schema":"isaac-healthcare-scenarios/v1","scenarios":[{"name":"baseline","seed":17}]}
```

Use inspection/lint to discover the actual authored workflow and mode, scene
requirements, missing dependencies and assets. Do not infer a universal step
limit, control frequency, joint count or camera layout. Null scene controls
preserve the upstream/project defaults; an explicit episode cap cannot exceed
the selected scene's authored cap. Project source defines a different scene
when a different experiment requires one.

For an automatic test with agent-selected settings, choose an explicit mode
from the inspected workflow's capabilities. Prefer a qualified `rule-based`
mode when available; `idle` does not perform the task, `teleop` needs a user,
and policy/replay modes need their actual checkpoint/recording. If no suitable
mode is available, report that limitation. Do not change explicit user settings
or project defaults, and do not treat registry presence as GPU qualification.

For simulation, preserve explicit mode, physics, environment count, camera,
episode/attempt and reset settings. For replay, supply the retained recording
and actual episode indices; retain its initial-state and runtime identity.
The batch operation names are `inspect`, `lint`, `simulate`, `replay`, `train`,
`evaluate`, `export`, `dataset-inspect` and `dataset-convert`; discover which are
available on the caller's deployment. For training/evaluation/export or dataset
conversion, use the current typed operation and its installed backend. Preserve optimizer, randomization,
checkpoint, dataset and sensor settings. Never silently change training into
inference, replace a missing checkpoint, or claim a dry run trained a policy.

Retain the operation and idempotency identity once accepted. Disconnects call
for polling/retrieval of that same operation. Ambiguous acceptance is not
permission to submit again. Download verified result/artifact references;
report executed work, measured task success, limits reached and missing values
separately. Integrity validation and `task_complete=false` can coexist. A
completed simulation or training run does not establish clinical validity.

## Interactive work

When the deployed contract exposes them, use
`start_isaac_interactive_session`, `get_isaac_interactive_session`,
`attach_isaac_interactive_session`, `stop_isaac_interactive_session` and
`get_isaac_interactive_result`. A session has its own workspace and native
admission identity. Reconnect to the same session after a browser disconnect;
attachment does not create a new session or extend its original deadline.
Retain that session ID for status and result recovery. Report ready only after
the actual simulator, advancing video and intended controls work. Report a
returned initialization failure as a failure even when transport is connected;
execution outcome, output delivery and resource release are separate facts.

Keep browser authentication, native claims and media-relay credentials out of
messages, source and downloadable examples. Use the returned authenticated
viewer, not a raw simulator signaling or UDP address. An HTTP response or
WebSocket connection alone does not prove working WebRTC media. Distinguish
simulated teleoperation from connectivity to the user's physical devices.

## Portable execution

The [portable recipe](https://github.com/rene-tech/serverless-ai-cookbook/tree/main/templates/job-isaac-healthcare)
contains the same runtime contract for local containers, Kubernetes and Nebius
Serverless. Choose a finite Job for unattended work and a qualified persistent
session for interactive use. Respect the user's supplied NVIDIA entitlement.
Rendering/streaming and training have different hardware requirements; use
measured compatibility rather than treating one tested GPU as the only option.
Stage HDF5/checkpoints on POSIX scratch and transfer complete verified outputs
to durable storage. Preserve original data and diagnostics during cleanup.
