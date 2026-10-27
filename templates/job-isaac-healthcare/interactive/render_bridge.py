"""Render the private transport-only CPU bridge. No Kubernetes API calls."""

import argparse
import json
import re
from pathlib import Path


def render(
    namespace,
    image,
    config_name,
    tls_secret,
    token_secret,
    trust_bundle_config=None,
    trust_bundle_key="ca.crt",
):
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("immutable bridge image required")
    for value in (namespace, config_name, tls_secret, token_secret):
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", value):
            raise ValueError("invalid Kubernetes identity")
    name = "isaac-interactive-bridge"
    labels = {"app.kubernetes.io/name": name}
    result = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {
                    "replicas": 1,
                    "strategy": {"type": "Recreate"},
                    "selector": {"matchLabels": labels},
                    "template": {
                        "metadata": {"labels": labels},
                        "spec": {
                            "automountServiceAccountToken": False,
                            "securityContext": {
                                "runAsNonRoot": True,
                                "runAsUser": 65532,
                                "runAsGroup": 65532,
                                "fsGroup": 65532,
                                "seccompProfile": {"type": "RuntimeDefault"},
                            },
                            "containers": [
                                {
                                    "name": "bridge",
                                    "image": image,
                                    "args": [
                                        "--config",
                                        "/config/bridge.json",
                                        "--token-file",
                                        "/auth/token",
                                        "--tls-cert",
                                        "/tls/tls.crt",
                                        "--tls-key",
                                        "/tls/tls.key",
                                    ],
                                    "securityContext": {
                                        "readOnlyRootFilesystem": True,
                                        "allowPrivilegeEscalation": False,
                                        "capabilities": {"drop": ["ALL"]},
                                    },
                                    "resources": {
                                        "requests": {"cpu": "250m", "memory": "256Mi"},
                                        "limits": {"cpu": "1", "memory": "1Gi"},
                                    },
                                    "ports": [{"containerPort": 8443, "name": "https"}],
                                    "readinessProbe": {
                                        "tcpSocket": {"port": "https"},
                                        "periodSeconds": 5,
                                    },
                                    "volumeMounts": [
                                        {
                                            "name": n,
                                            "mountPath": "/" + n,
                                            "readOnly": True,
                                        }
                                        for n in ("config", "auth", "tls")
                                    ],
                                }
                            ],
                            "volumes": [
                                {"name": "config", "configMap": {"name": config_name}},
                                {
                                    "name": "auth",
                                    "secret": {"secretName": token_secret},
                                },
                                {"name": "tls", "secret": {"secretName": tls_secret}},
                            ],
                        },
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {
                    "type": "ClusterIP",
                    "selector": labels,
                    "ports": [{"name": "https", "port": 8443, "targetPort": 8443}],
                },
            },
        ],
    }
    if trust_bundle_config is not None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", trust_bundle_config):
            raise ValueError("invalid operator trust-bundle ConfigMap name")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", trust_bundle_key):
            raise ValueError("invalid trust-bundle key")
        pod = result["items"][0]["spec"]["template"]["spec"]
        pod["volumes"].append(
            {
                "name": "native-trust",
                "configMap": {
                    "name": trust_bundle_config,
                    "items": [{"key": trust_bundle_key, "path": "ca.crt"}],
                },
            }
        )
        container = pod["containers"][0]
        container["volumeMounts"].append(
            {"name": "native-trust", "mountPath": "/native-trust", "readOnly": True}
        )
        container["env"] = [{"name": "SSL_CERT_FILE", "value": "/native-trust/ca.crt"}]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("namespace", "image", "config-name", "tls-secret", "token-secret"):
        p.add_argument("--" + name, required=True)
    p.add_argument(
        "--trust-bundle-config",
        help="operator-approved CA bundle for Native endpoint TLS",
    )
    p.add_argument("--trust-bundle-key", default="ca.crt")
    p.add_argument("--output", type=Path, required=True)
    args = vars(p.parse_args())
    output = args.pop("output")
    with output.open("x") as f:
        json.dump(render(**args), f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
