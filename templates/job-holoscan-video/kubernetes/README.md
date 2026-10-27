# Finite Holoscan Job on your Kubernetes cluster

This path runs the same portable image on an NVIDIA Kubernetes cluster,
including an on-premises cluster. It uses neither the provider Serverless API
nor Scientific AI. Install/configure the NVIDIA Container Toolkit and device
plugin through your existing cluster owner. Use the exact image and GPU/driver
combination recorded in `../QUALIFICATION.md`; a successful CPU check does not
establish GPU compatibility.

Start from `job.yaml`. Set your registry's immutable digest and select a GPU
class you have qualified, using node affinity/selectors that match your cluster.
The example requests one GPU, four CPUs, 16 GiB RAM and 64 GiB local scratch.
Resize scratch using the recorded-video formula in the main README. The generic
manifest selects AMD64; it does not imply that every GPU architecture is tested.
Adjust the `nvidia.com/gpu` toleration to the taints your cluster actually uses.
Use your normal registry pull Secret or node identity if the image is private.

On clusters managed by Kueue or another admission controller, select an existing
operator-approved LocalQueue/resource flavor compatible with the requested GPU
selector. Set the Job's `kueue.x-k8s.io/queue-name` label to that cluster-specific
queue. A generic default queue may inject an incompatible pool selector after
admission even when Kubernetes client/server dry-run passes. Inspect the actual
admitted Pod selectors and workload flavor before attributing Pending to GPU
availability or model compatibility. Do not create or change cluster queues or
policies as part of this recipe.

Build `input.tar` from the pinned model, its license, `parameters.json`, and your
video. The parameter `video_file` selects its relative member path. Obtain a
scoped HTTPS GET for that exact input object and a scoped HTTPS PUT for a fresh
output object from your existing object-storage service. This can be your own
S3-compatible service. Keep the transfer file private; example structure:

```json
{
  "input": {"url": "SCOPED_HTTPS_GET", "sha256": "INPUT_TAR_SHA256", "size_bytes": 12345},
  "output": {"url": "SCOPED_HTTPS_PUT", "max_bytes": 268435456, "headers": {"Content-Type": "application/x-tar"}},
  "command_sha256": "SHA256_OF_KUBERNETES_COMMAND_JSON",
  "execution_timeout_s": 1800
}
```

Use `sha256sum input.tar kubernetes/command.json` and the input file's actual byte
size. No Endpoint claim/idle mode is used. The container runs the portable CLI
through the official NVIDIA compatibility launcher. Scripts are read-only
ConfigMap files; scoped URLs are read-only Secret data, not command arguments.
UID/GID 10001 and fsGroup 10001 make the scratch and capability mounts usable.
There is no service-account token, HTTP port, Service or new scheduler.

Create reviewed local resource documents first. Commands below run from the
recipe directory and assume an existing namespace you own:

```bash
kubectl -n "$NAMESPACE" create configmap holoscan-video-run-001 \
  --from-file=transfer.py=provider/transfer.py \
  --from-file=run_bundle.py=provider/run_bundle.py \
  --from-file=command.json=kubernetes/command.json \
  --dry-run=client -o yaml > scripts.yaml
kubectl -n "$NAMESPACE" create secret generic holoscan-video-run-001-io \
  --from-file=transfer.json="$PRIVATE_TRANSFER_JSON" \
  --dry-run=client -o yaml > capability.private.yaml
chmod 600 capability.private.yaml
kubectl -n "$NAMESPACE" apply --dry-run=client \
  -f scripts.yaml -f capability.private.yaml -f kubernetes/job.yaml
```

Keep `capability.private.yaml` out of Git and shared logs. Review image, placement,
resources, capabilities and output prefix, then apply those exact documents
through your cluster's normal admission process. Use a new consistent Job,
ConfigMap, Secret and output prefix for each intended execution.

The Job has `backoffLimit: 0`, `restartPolicy: Never`, one completion/parallelism,
and an 1800-second total deadline. `podReplacementPolicy: Failed` avoids starting
a replacement while a previous Pod is terminating; verify support on your cluster.
Failed or interrupted model work is not automatically retried by this recipe.
Do not manually replay an uncertain Job before reconciling its Pod and outputs.
The deadline includes startup/pull/transfer, so allow enough time for output
export when selecting the inner execution timeout.

```bash
kubectl -n "$NAMESPACE" get job holoscan-video-run-001
kubectl -n "$NAMESPACE" logs job/holoscan-video-run-001
kubectl -n "$NAMESPACE" get pods -l job-name=holoscan-video-run-001 \
  -o jsonpath='{range .items[*].status.containerStatuses[*]}{.imageID}{"\n"}{end}'
```

Retain the actual Pod `imageID`, node GPU/driver, logs and output checksum.
Download the output tar and verify `result.json`, ordered tracking rows, finite
mask tensors and actual annotated-video frame count. A successful Pod exit
alone is insufficient. The transfer inventory includes its scientific exit
code and all complete exported files; a failure can still export useful logs.

After retaining evidence, delete only this Job, ConfigMap and capability Secret.
Cancel early by deleting this exact Job and confirming its Pod terminates; no
automatic retry should be submitted. Remove only its owned temporary object
prefix when no longer needed. Durable outputs live outside the Pod's scratch.

Provider Serverless Job/Endpoint submission remains a separate qualification:
the current digest label-validation defect is recorded in `provider/README.md`
and is not repaired by a Kubernetes execution.
