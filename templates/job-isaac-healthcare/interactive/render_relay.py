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
    public_ip=None,
    pod_cidr,
    hostname,
    tls_secret,
    auth_secret,
    relay_min,
    relay_max,
    service_port=443,
    relay_address_mode=None,
    name="isaac-interactive-turn",
):
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("pin the reviewed coturn image by digest")
    if not 1024 < relay_min <= relay_max <= 65535 or not 1 <= service_port <= 65535:
        raise ValueError("operator-selected relay range/port is invalid")
    # A supplied public NAT address retains the original explicit NAT topology.
    # Without one, use the same-region private Pod-IP relay over public TLS only.
    relay_address_mode = relay_address_mode or (
        "public-nat" if public_ip is not None else "private-pod"
    )
    if relay_address_mode not in {"private-pod", "public-nat"}:
        raise ValueError("relay address mode must be private-pod or public-nat")
    if relay_address_mode == "public-nat":
        if public_ip is None:
            raise ValueError("public-nat requires the actual public relay IPv4")
        public_ip = str(ipaddress.IPv4Address(public_ip))
    elif public_ip is not None:
        raise ValueError("private-pod advertises its Pod IPv4; omit public-ip")
    networks = sorted(
        {
            ipaddress.IPv4Network(c)
            for c in ([pod_cidr] if isinstance(pod_cidr, str) else pod_cidr)
        }
    )
    if not networks:
        raise ValueError("at least one operator-bound worker allocation CIDR is required")
    for value in (
        namespace,
        worker_namespace,
        model,
        hostname,
        tls_secret,
        auth_secret,
        name,
    ):
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", value):
            raise ValueError("invalid Kubernetes/DNS identity")
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
            *([f"external-ip={public_ip}"] if public_ip else []),
            f"min-port={relay_min}",
            f"max-port={relay_max}",
            "relay-threads=2",
            "cert=/state/current/tls.crt",
            "pkey=/state/current/tls.key",
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
    # The supervisor reads authority only from mounted Secrets and copies one
    # atomic TLS revision before SIGUSR2 reload; no secret enters the Pod argv.
    launcher = (Path(__file__).parent / "turn-supervisor.sh").read_text()
    ports = [
        {
            "name": "turn-tls",
            "port": service_port,
            "targetPort": 5349,
            "protocol": "TCP",
        }
    ]
    ports += (
        [
            {"name": f"media-{p}", "port": p, "targetPort": p, "protocol": "UDP"}
            for p in range(relay_min, relay_max + 1)
        ]
        if relay_address_mode == "public-nat"
        else []
    )
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
                    "hostNetwork": False,
                    "hostPID": False,
                    "hostIPC": False,
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
                            "command": ["/bin/sh", "/config/turn-supervisor.sh"],
                            "env": [
                                {
                                    "name": "POD_IP",
                                    "valueFrom": {
                                        "fieldRef": {"fieldPath": "status.podIP"}
                                    },
                                },
                                {"name": "TURN_REALM", "value": hostname},
                            ],
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
                        {
                            "name": "tls",
                            "secret": {"secretName": tls_secret, "defaultMode": 288},
                        },
                        {
                            "name": "auth",
                            "secret": {"secretName": auth_secret, "defaultMode": 288},
                        },
                        {
                            "name": "state",
                            "emptyDir": {"medium": "Memory", "sizeLimit": "32Mi"},
                        },
                    ],
                },
            },
        },
    }
    cm = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": namespace},
        "data": {"turnserver.conf": config, "turn-supervisor.sh": launcher},
    }
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "type": "LoadBalancer",
            "externalTrafficPolicy": "Cluster",
            "selector": labels,
            "ports": ports,
        },
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
                {"ports": [{"protocol": "TCP", "port": 5349}]},
                {
                    **(
                        {
                            "from": [
                                {
                                    "namespaceSelector": {
                                        "matchLabels": {
                                            "kubernetes.io/metadata.name": worker_namespace
                                        }
                                    },
                                    "podSelector": {"matchLabels": worker_selector},
                                }
                            ]
                        }
                        if relay_address_mode == "private-pod"
                        else {}
                    ),
                    "ports": [
                        {"protocol": "UDP", "port": relay_min, "endPort": relay_max}
                    ],
                },
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
    items = [cm, deployment, service, worker_policy, relay_policy]
    if relay_address_mode == "private-pod":
        items.append(
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": name + "-return", "namespace": worker_namespace},
                "spec": {
                    "podSelector": {"matchLabels": worker_selector},
                    "policyTypes": ["Egress"],
                    "egress": [
                        {
                            "to": [relay_selector],
                            "ports": [
                                {
                                    "protocol": "UDP",
                                    "port": relay_min,
                                    "endPort": relay_max,
                                }
                            ],
                        }
                    ],
                },
            }
        )
    return {
        "apiVersion": "v1",
        "kind": "List",
        "items": items,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "namespace",
        "worker-namespace",
        "model",
        "image",
        "hostname",
        "tls-secret",
        "auth-secret",
    ):
        p.add_argument("--" + name, required=True)
    p.add_argument(
        "--public-ip",
        help="actual public NAT relay address; selects public-nat when mode is omitted",
    )
    p.add_argument(
        "--relay-address-mode",
        choices=["private-pod", "public-nat"],
        help="defaults to private-pod unless public-ip is supplied",
    )
    p.add_argument(
        "--name",
        default="isaac-interactive-turn",
        help="operator-owned relay resource name",
    )
    p.add_argument(
        "--pod-cidr",
        action="append",
        required=True,
        help="repeat for each authoritative worker allocation CIDR, excluding Service CIDRs",
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
