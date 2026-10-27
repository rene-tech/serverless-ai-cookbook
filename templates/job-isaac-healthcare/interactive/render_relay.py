"""Render a CPU-only TURN deployment for operator review; never calls Kubernetes."""

import argparse
import ipaddress
import json
import re
from pathlib import Path


def render(
    *,
    namespace,
    worker_namespace,
    model,
    image,
    public_ip,
    pod_cidr,
    hostname,
    tls_secret,
    auth_secret,
    relay_min,
    relay_max,
    service_port=443,
):
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("pin the reviewed coturn image by digest")
    if not 1024 < relay_min <= relay_max <= 65535 or not 1 <= service_port <= 65535:
        raise ValueError("operator-selected relay range/port is invalid")
    public_ip = str(ipaddress.IPv4Address(public_ip))
    networks = sorted(
        {
            ipaddress.IPv4Network(c)
            for c in ([pod_cidr] if isinstance(pod_cidr, str) else pod_cidr)
        }
    )
    if not networks:
        raise ValueError("at least one actual worker Pod CIDR is required")
    for value in (
        namespace,
        worker_namespace,
        model,
        hostname,
        tls_secret,
        auth_secret,
    ):
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", value):
            raise ValueError("invalid Kubernetes/DNS identity")
    name = "isaac-interactive-turn"
    labels = {"app.kubernetes.io/name": name}
    config = "\n".join(
        [
            "listening-port=3478",
            "tls-listening-port=5349",
            "no-tcp",
            "no-udp",
            "no-dtls",
            "secure-stun",
            "no-tlsv1",
            "no-tlsv1_1",
            "fingerprint",
            "use-auth-secret",
            f"realm={hostname}",
            f"external-ip={public_ip}",
            f"min-port={relay_min}",
            f"max-port={relay_max}",
            "cert=/tls/tls.crt",
            "pkey=/tls/tls.key",
            "no-cli",
            "no-multicast-peers",
            "no-tcp-relay",
            "no-software-attribute",
            "no-stdout-log",
            "log-file=/state/turn.log",
            "pidfile=/state/turn.pid",
            "denied-peer-ip=0.0.0.0-255.255.255.255",
            *[
                f"allowed-peer-ip={network.network_address}-{network.broadcast_address}"
                for network in networks
            ],
            "",
        ]
    )
    # The shared secret is read from the mounted Secret into an in-memory config,
    # never a Pod command-line argument or source/configmap value.
    launcher = "umask 077\ncat /config/turnserver.conf > /state/turnserver.conf\nprintf 'static-auth-secret=%s\\n' \"$(cat /auth/secret)\" >> /state/turnserver.conf\nexec turnserver -c /state/turnserver.conf"
    ports = [
        {
            "name": "turn-tls",
            "port": service_port,
            "targetPort": 5349,
            "protocol": "TCP",
        }
    ]
    ports += [
        {"name": f"media-{p}", "port": p, "targetPort": p, "protocol": "UDP"}
        for p in range(relay_min, relay_max + 1)
    ]
    deployment = {
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
                            "name": "turn",
                            "image": image,
                            "command": ["/bin/sh", "-ec", launcher],
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {"cpu": "1", "memory": "1Gi"},
                                "limits": {"cpu": "2", "memory": "2Gi"},
                            },
                            "readinessProbe": {
                                "tcpSocket": {"port": 5349},
                                "periodSeconds": 5,
                            },
                            "volumeMounts": [
                                {
                                    "name": "config",
                                    "mountPath": "/config",
                                    "readOnly": True,
                                },
                                {"name": "tls", "mountPath": "/tls", "readOnly": True},
                                {
                                    "name": "auth",
                                    "mountPath": "/auth",
                                    "readOnly": True,
                                },
                                {"name": "state", "mountPath": "/state"},
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "config", "configMap": {"name": name}},
                        {"name": "tls", "secret": {"secretName": tls_secret}},
                        {"name": "auth", "secret": {"secretName": auth_secret}},
                        {"name": "state", "emptyDir": {"medium": "Memory"}},
                    ],
                },
            },
        },
    }
    cm = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": namespace},
        "data": {"turnserver.conf": config},
    }
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"type": "LoadBalancer", "selector": labels, "ports": ports},
    }
    worker_selector = {"serving.kserve.io/inferenceservice": model}
    relay_selector = {
        "namespaceSelector": {
            "matchLabels": {"kubernetes.io/metadata.name": namespace}
        },
        "podSelector": {"matchLabels": labels},
    }
    media_port = {"protocol": "UDP", "port": 47998}
    worker_policy = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": name + "-media", "namespace": worker_namespace},
        "spec": {
            "podSelector": {"matchLabels": worker_selector},
            "policyTypes": ["Ingress"],
            "ingress": [{"from": [relay_selector], "ports": [media_port]}],
        },
    }
    relay_policy = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "podSelector": {"matchLabels": labels},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [
                {
                    "ports": [
                        {"protocol": "TCP", "port": 5349},
                        {"protocol": "UDP", "port": relay_min, "endPort": relay_max},
                    ]
                }
            ],
            "egress": [
                {
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "kubernetes.io/metadata.name": worker_namespace
                                }
                            },
                            "podSelector": {"matchLabels": worker_selector},
                        }
                    ],
                    "ports": [media_port],
                }
            ],
        },
    }
    return {
        "apiVersion": "v1",
        "kind": "List",
        "items": [cm, deployment, service, worker_policy, relay_policy],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "namespace",
        "worker-namespace",
        "model",
        "image",
        "public-ip",
        "hostname",
        "tls-secret",
        "auth-secret",
    ):
        p.add_argument("--" + name, required=True)
    p.add_argument(
        "--pod-cidr",
        action="append",
        required=True,
        help="repeat for each actual worker Pod CIDR",
    )
    p.add_argument("--relay-min", type=int, required=True)
    p.add_argument("--relay-max", type=int, required=True)
    p.add_argument("--service-port", type=int, default=443)
    p.add_argument("--output", type=Path, required=True)
    args = vars(p.parse_args())
    output = args.pop("output")
    with output.open("x") as f:
        json.dump(render(**args), f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
