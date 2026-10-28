"""CPU policy-contract checks; live CNI enforcement is a separate release gate."""

import importlib.util
from pathlib import Path

import pytest


def render(**changes):
    source = Path(__file__).parents[1] / "render_relay.py"
    spec = importlib.util.spec_from_file_location("relay_scope", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = dict(namespace="relay-system", worker_namespace="customer-workers",
                model="authored-workflow", image="example.test/turn@sha256:" + "1" * 64,
                pod_cidr=["10.32.0.0/14", "10.40.0.0/14"], hostname="turn.example.test",
                tls_secret="turn-tls", auth_secret="turn-auth", relay_min=53000,
                relay_max=53015, relay_address_mode="private-pod")
    args.update(changes)
    return module.render(**args)["items"]


def matches(selector, labels):
    assert set(selector) <= {"matchLabels"}
    return all(labels.get(k) == v for k, v in selector.get("matchLabels", {}).items())


def allows_egress(policy, namespace, labels, protocol, port):
    # Evaluate standard NetworkPolicy AND within a peer / OR between rules.
    for rule in policy["spec"].get("egress", []):
        peer_ok = any(matches(peer.get("namespaceSelector", {}), {"kubernetes.io/metadata.name": namespace})
                      and matches(peer.get("podSelector", {}), labels) for peer in rule.get("to", [{}]))
        port_ok = any(p.get("protocol", "TCP") == protocol and p["port"] <= port <= p.get("endPort", p["port"])
                      for p in rule.get("ports", []))
        if peer_ok and port_ok:
            return True
    return False


@pytest.mark.parametrize("namespace,labels,protocol,port,allowed", [
    ("customer-workers", {"serving.kserve.io/inferenceservice": "authored-workflow"}, "UDP", 47998, True),
    ("customer-workers", {"serving.kserve.io/inferenceservice": "authored-workflow"}, "TCP", 47998, False),
    ("customer-workers", {"serving.kserve.io/inferenceservice": "authored-workflow"}, "UDP", 53, False),
    ("customer-workers", {"serving.kserve.io/inferenceservice": "different-model"}, "UDP", 47998, False),
    ("different-namespace", {"serving.kserve.io/inferenceservice": "authored-workflow"}, "UDP", 47998, False),
    ("kube-system", {"k8s-app": "coredns"}, "UDP", 53, False),
    ("kube-system", {"k8s-app": "coredns"}, "TCP", 53, False),
    ("customer-workers", {}, "UDP", 47998, False),
])
def test_namespace_model_protocol_and_port_are_all_required(namespace, labels, protocol, port, allowed):
    policy = next(obj for obj in render() if obj["kind"] == "NetworkPolicy" and obj["metadata"]["namespace"] == "relay-system")
    assert allows_egress(policy, namespace, labels, protocol, port) is allowed


def test_dedicated_process_has_no_host_namespace_or_service_account_authority():
    objects = render()
    deployment = next(obj for obj in objects if obj["kind"] == "Deployment")
    pod = deployment["spec"]["template"]["spec"]
    assert pod["hostNetwork"] is pod["hostPID"] is pod["hostIPC"] is False
    assert pod["automountServiceAccountToken"] is False
    assert [item["name"] for item in pod["containers"]] == ["turn"]
    assert not pod.get("initContainers")
    assert pod["containers"][0]["securityContext"]["capabilities"] == {"drop": ["ALL"]}
    assert all("hostPath" not in volume for volume in pod["volumes"])
    assert not any(obj["kind"] in {"Secret", "Namespace"} for obj in objects)


def test_operator_allocation_range_does_not_depend_on_present_nodes():
    config = next(obj for obj in render() if obj["kind"] == "ConfigMap")["data"]["turnserver.conf"]
    assert "allowed-peer-ip=10.32.0.0-10.35.255.255\n" in config
    assert "allowed-peer-ip=10.40.0.0-10.43.255.255\n" in config
    assert "denied-peer-ip=0.0.0.0-255.255.255.255\n" in config
    assert "no-tcp-relay\n" in config
    # There is no node-name selector, GPU selector, or current-address inventory.
    pod = next(obj for obj in render() if obj["kind"] == "Deployment")["spec"]["template"]["spec"]
    assert "nodeName" not in pod and "nodeSelector" not in pod


def test_private_relay_has_only_public_tls_service_port():
    service = next(obj for obj in render(service_port=5349) if obj["kind"] == "Service")
    assert service["spec"]["ports"] == [{"name": "turn-tls", "port": 5349, "targetPort": 5349, "protocol": "TCP"}]
