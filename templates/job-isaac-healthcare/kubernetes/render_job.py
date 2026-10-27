"""Render a standalone Kubernetes Job; never creates cluster resources."""

import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--image", required=True, help="Your registry image pinned by sha256 manifest digest")
parser.add_argument("--name", default="isaac-healthcare-run-001")
parser.add_argument("--namespace", default="default")
parser.add_argument("--input-pvc", default="isaac-inputs")
parser.add_argument("--output-pvc", default="isaac-results")
parser.add_argument("--gpu-node-selector", default="nvidia.com/gpu.product=NVIDIA-L40S")
parser.add_argument("--image-pull-secret", help="Existing registry Secret name; no credentials")
parser.add_argument("--deadline-seconds", type=int, default=7200)
parser.add_argument("--uid", type=int, default=10001)
parser.add_argument("--gid", type=int)
parser.add_argument("--accept-eula", action="store_true", required=True,
                    help="Confirm that you accept the applicable NVIDIA simulator and Kit terms")
args = parser.parse_args()
if not re.fullmatch(r"[^\s@]+@sha256:[a-f0-9]{64}", args.image):
    parser.error("--image must contain an immutable sha256 manifest digest")
if args.deadline_seconds < 1 or args.uid < 1 or (args.gid is not None and args.gid < 1):
    parser.error("deadline and non-root UID/GID must be positive")
if "=" not in args.gpu_node_selector:
    parser.error("--gpu-node-selector must be label=value for your RTX-capable GPU nodes")
label, value = args.gpu_node_selector.split("=", 1)
if not label or not value:
    parser.error("GPU node selector label and value must be nonempty")
job = json.loads(Path(__file__).with_name("job.template.json").read_bytes())
job["metadata"].update(name=args.name, namespace=args.namespace)
job["spec"]["activeDeadlineSeconds"] = args.deadline_seconds
pod = job["spec"]["template"]["spec"]
pod["nodeSelector"] = {"kubernetes.io/arch": "amd64", "kubernetes.io/os": "linux", label: value}
gid = args.uid if args.gid is None else args.gid
pod["securityContext"].update(runAsUser=args.uid, runAsGroup=gid, fsGroup=gid)
if args.image_pull_secret:
    pod["imagePullSecrets"] = [{"name": args.image_pull_secret}]
container = pod["containers"][0]
container["image"] = args.image
container["args"][-1] = "/output/" + args.name
for variable in container["env"]:
    if variable["value"] == "${ACCEPT_EULA}":
        variable["value"] = "Y"
pod["volumes"][0]["persistentVolumeClaim"]["claimName"] = args.input_pvc
pod["volumes"][1]["persistentVolumeClaim"]["claimName"] = args.output_pvc
print(json.dumps(job, indent=2))
