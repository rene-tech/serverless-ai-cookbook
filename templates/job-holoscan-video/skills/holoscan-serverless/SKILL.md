---
name: holoscan-serverless
description: Build and run a finite Holoscan 5 recorded endoscopy tool-tracking Job on premises or in Nebius Serverless, validating probabilities, locations, masks and annotated video.
---

# Holoscan recorded video

Use the recipe's `README.md`, Dockerfile, `QUALIFICATION.md` and current CLI help.
Run the actual C++ Holoscan/TensorRT graph with pinned CAMMA ONNX weights.
`--inference false` and synthetic replay do not qualify neural inference.

The portable image is independent of Scientific AI. For cloud execution, build and
push it to the user's registry, pin its manifest digest, select an actually
qualified GPU/runtime, mount owned input/model and durable output storage, and
run one finite Job. Keep secrets in configured credentials/secret stores.

Current qualification records provider Job and Endpoint digest submissions
blocked by a Compute label-length validation error. Preserve immutable references
and report that gap; changing clients or shortening to a mutable tag is not a
qualified repair. Use the independent `kubernetes/README.md` or Docker path when
the user authorizes that execution environment, retaining their exact-image
GPU qualification requirements.

Accept ordinary supported video recordings. Preserve requested frame count,
start, stride and overlay controls. Zero count means all remaining selected
frames. Explain that subsampling changes recurrent context and every recording
begins with zero state; resizing is explicit, not a clinical geometry claim.

Inspect terminal status **and** result.json, seven tracking rows per frame,
finite mask tensor with `[frames,7,60,107]` shape, hashes and optional decodable
annotated MP4. Record exact image/model/source identity and measurements.
Report incomplete/failed work with the observed cause and correction.

Use a unique output prefix per Job and local scratch sized for decoded RGB.
Cancel only the selected Job; retain results before deleting it. Deleting a Job
does not delete its separately mounted bucket. Persistent streams, device
capture and real-time end-to-end latency require separate qualification. This
research model is not a clinical diagnostic or physical control system.
