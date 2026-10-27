# Qualification record

27 October 2026, candidate. Real GPU and provider/public-path results are updated
only from exact-image executions; the checks below do not imply production readiness.

Observed:
- Official AMD64 Holoscan 5.0.0 base manifest
  `sha256:9cd60e6a35ddaa697009139ad5565cedefa0034a98bae1c12f4a5bde051f202c`.
- Actual image CUDA 13.2.51 / TensorRT 10.16.0.72. CUDA compilation passed for
  SM89, SM90, SM100 and SM120; this is not execution qualification.
- Five original upstream CPU data-preparation tests passed.
- Six portable CPU media/semantic tests passed, including an unseen generated
  recording, nondefault start/stride, malformed input, corrupted numerical output,
  and an MP4 with arbitrary-angle display rotation. Encoded-frame geometry and
  annotation orientation are consistent; ordinary H.264 frames remain byte-identical.
- Ten offline private adapter/schema/discovery/isolated-workspace tests passed;
  they exercise REST/MCP schemas without making hosted API submissions.
- The maintained launch wrapper preserves the official CUDA compatibility probe;
  CPU tests verify literal argv forwarding and PID 1 execution. GPU behavior is
  not inferred from a CPU check.

- Integral JSON frame settings normalize consistently in portable execution and
  REST/MCP compilation; booleans, fractions and nonfinite numbers are rejected.
- Five scoped-transfer CPU checks passed with mocked object HTTP responses
  and real child processes, including a conditional start marker
  that prevents replay, finite Job mode, subprocess timeout, failed input
  integrity and redirects. They also pass inside the actual portable image as
  UID10001 with a read-only root filesystem and a writable scratch mount.
- Provider Job dry-run fails with an image-length Compute label-validation error.
  Exact local CLI capture has no labels; provider-side translation is suspected.
  SDK round-trip preserves the same request. Actual Endpoint SDK dry-run also
  fails with the same label limit, with no labels and with short task labels.
  Those failed requests created no provider resource. Later short-reference
  qualification is recorded separately below.

- The finite Kubernetes Job and ConfigMap pass client-side API validation;
  the first admitted Pod remained Pending because its default Kueue flavor
  injected an H100 pool selector alongside L40S. No container/GPU execution
  occurred. The corrected task used an existing compatible L40S queue and
  completed the exact-image model test below.

Exact portable image `sha256:5a4cffcb0bde1e2a7e8f6a2e9dcbc4fb6330970286fc945a32bf7cc6eee5b66a`
passed one real finite Kubernetes Job on each of **NVIDIA L40S, H100, H200 and
RTX PRO 6000 Blackwell Server Edition**, host driver **580.173.02**, with CUDA
**13.2.51**, TensorRT **10.16.0.72** and FP32. The first three ran in eu-north1;
RTX ran in eu-south1. Every official compatibility probe reported `CUDA Driver OK`;
every actual Pod imageID matched that digest, exit was zero, and restart count
was zero. Each Job requested four
CPUs, 16 GiB RAM, one GPU and 64 GiB scratch, as UID10001 with a read-only root.

Independent output validation passed on all four devices: all 30 selected frames, 210 ordered tool
rows, finite float32 masks `[30,7,60,107]`, exact source/model/input identity,
all exported byte hashes, and an annotated 854×480 MP4 decoding all 30 frames
at 25 fps. Probabilities ranged from approximately 2.94e-7 to 0.999248; masks
from 2.57e-12 to 0.999990. All 30 frames had at least one tool probability over 0.5. These
are pipeline/regression observations, not measured clinical accuracy.

| GPU | Preparation (s) | Graph including engine build (s) | Packaging (s) | Cold frames/s |
| --- | ---: | ---: | ---: | ---: |
| L40S | 0.221 | 13.366 | 1.502 | 2.245 |
| H100 | 0.216 | 22.662 | 1.050 | 1.324 |
| H200 | 0.203 | 23.267 | 1.408 | 1.289 |
| RTX PRO 6000 Blackwell | 0.198 | 12.284 | 1.301 | 2.442 |

These single cold executions include TensorRT engine construction. They are
**not** steady-state throughput, real-time latency, a cost ranking or a
shared-service capacity result.

Coordinates matched exactly across all devices; tensors were not bitwise equal.
For the same recording/model/parameters, differences from L40S were:

| GPU | Maximum probability difference | Maximum mask difference | Mask RMSE |
| --- | ---: | ---: | ---: |
| H100 | 0.000291228 | 0.001117468 | 0.0000275743 |
| H200 | 0.000290930 | 0.001117051 | 0.0000275741 |
| RTX PRO 6000 Blackwell | 0.000673830 | 0.001101017 | 0.0000291085 |

No tool-probability decisions changed at 0.5. Each comparison changed one mask
value's side of 0.5 out of 1,348,200 values. These describe this finite regression;
they are not a universal numerical tolerance or a clinical agreement guarantee.

The separately packaged Scientific AI worker also passed one default public REST
case and one typed MCP case on L40S: each processed all 683 frames, 4,781 tool
rows, finite `[683,7,60,107]` masks and a complete 854×480, 25 fps annotated video.
Every published file was read back with its full checksum from the requested
custom/default customer-bucket prefix. These hosted results do not add a
Scientific AI dependency to this portable image or recipe.

The second public cohort passed scientific and requested-bucket checks with a
previously unseen rotation-tagged MP4: REST selected five later frames without
annotation; MCP used integral JSON numbers, stride two and a different threshold,
producing eight annotated frames at 12.5 fps. Encoded-frame geometry, complete
numerical outputs and all requested bucket files passed independent validation.
Two intentional failures also retained the unreadable-video or missing-input
cause through REST and MCP status/results, stopped after one attempt, and
advertised no successful output.

The separate shared audit passed 84 access/idempotency controls, including 28
Holoscan checks: same-request replay, changed-parameter/destination conflicts and
foreign status/result/artifact/cancel denial between two principals in one tenant.
Owner cancellation during execution, recovery and cross-tenant isolation remain
unqualified. These finite results do not establish production shared capacity.
Actual Native fallback and alternate-region worker execution are unobserved;
configured class/region mappings and verified regional image bytes do not prove
those behaviors. No sustainable shared-service capacity is claimed.

The original long-reference Job and Endpoint dry-run failures remain retained.
A later 119-character short repository reference with the **same complete digest**
passed an actual Job SDK dry-run after manifest/config/all-layer equality checks.
One finite provider Job has been accepted; actual runtime identity, GPU/driver,
scientific outputs, durable export and physical closeout remain pending. This is
not provider execution PASS. Bucket-mounted transport and Endpoint execution are
unqualified. Neither portable Kubernetes nor hosted App results substitute for
those provider checks.

The upstream application reports 300-frame execution on ARM64 GB10. That is
upstream evidence and does not qualify this AMD64 image or the target fleet.
