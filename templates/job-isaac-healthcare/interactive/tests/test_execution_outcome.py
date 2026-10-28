"""Finite CPU regressions for authenticated worker/bridge outcomes; no GPU or network."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import importlib
import json
import threading
import time
import types

import pytest
from starlette.testclient import TestClient


def load_portable(name):
    return importlib.import_module("i4h_interactive." + name)


def fixture():
    sid, key = "ses-0123456789abcdef", b"q" * 32
    assert len(key) == 32
    model, image = "general-interactive", "registry.test/runtime@sha256:" + "a" * 64
    # Match the Native wire timestamp before signing; never relax runtime equality.
    native_deadline = datetime.fromtimestamp(time.time() + 60, timezone.utc).isoformat()
    envelope = {
        "type": "isaac.session.start",
        "session_id": sid,
        "image": image,
        "runtime_revision": "ordinary-project",
        "deadline_at": datetime.fromisoformat(native_deadline).timestamp(),
        "start": {"project": {"artifact": "ordinary-scene"}},
        "display": {},
    }
    canonical = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    envelope["start_signature"] = hmac.new(key, canonical, hashlib.sha256).hexdigest()
    owner = types.SimpleNamespace(
        service=types.SimpleNamespace(
            profile=types.SimpleNamespace(model_id=model), start_key=key
        )
    )
    native = types.SimpleNamespace(
        value={"id": sid, "status": "attached", "outcome": None}
    )
    bridge = types.SimpleNamespace(
        starts=[
            {
                "session_id": sid,
                "start": envelope,
                "claim": "synthetic-single-use-claim",
                "startup_timeout_s": 3,
                "deadline_at": envelope["deadline_at"],
            }
        ],
        observed={},
    )
    return owner, native, bridge, None, None


def native_evidence(
    tmp_path,
    owner,
    native,
    bridge,
    *,
    ready=False,
    exit_code=1,
    cancelled=False,
    cleanup="stopped",
    preparation_error=None,
    delivery_failed=False,
):
    mod = load_portable("native")
    envelope = bridge.starts[0]["start"]
    sid = envelope["session_id"]
    deadline = envelope["deadline_at"]
    stamp = datetime.fromtimestamp(deadline, timezone.utc).isoformat()
    identity = {
        "tenant": "tenant",
        "owner": "alice",
        "model": owner.service.profile.model_id,
    }
    processes, releases, timeline = [], [], []
    ended = threading.Event()

    class API:
        async def attach(self, actual, connection, model):
            assert (actual, model) == (sid, identity["model"])
            return {"id": sid, "owner": identity, "deadline_at": stamp}

        async def watch(self, actual, actual_owner):
            assert (actual, actual_owner) == (sid, identity)
            return {
                "deadline_at": stamp,
                "cancel_requested": cancelled
                and bool(processes)
                and processes[0].child is not None,
            }

        async def release(self, actual, connection, outcome):
            assert cleanup == "stopped"
            assert preparation_error or timeline[-1] == "finalized"
            releases.append(outcome)
            native.value.update(
                status="ended",
                phase="ended",
                outcome=outcome,
                ended_at="2030-01-01T00:01:00Z",
                cancel_requested=cancelled,
            )
            ended.set()
            return {"id": actual, "status": "ended"}

    class Process:
        def __init__(self, config):
            self.child, self.state = None, "created"
            processes.append(self)

        async def start(self):
            self.child = types.SimpleNamespace(returncode=None if ready else exit_code)
            self.state = "starting"

        async def wait_signaling(self):
            if ready:
                self.state = "signaling"
                return
            await asyncio.Event().wait()

        async def stop(self, reason):
            self.state = cleanup
            timeline.append("joined")

    def finalize():
        timeline.append("finalized")
        if delivery_failed:
            raise OSError("synthetic output publication failure")

    def prepare(*args):
        if preparation_error:
            raise ValueError(preparation_error)
        return {
            "session_id": sid,
            "deadline_at": deadline,
            "signal_port": 49100,
            "closeout_file": str(tmp_path / "process-closeout.json"),
            "log_file": str(tmp_path / "execution.log"),
            "_finalize": finalize,
        }

    (tmp_path / "execution.log").write_text(
        'Traceback (most recent call last):\n  File "authored_scene.py", line 8, in build_scene\nValueError: missing authored asset patient_scene.usd; token=synthetic-secret https://internal.example/signed\n'
    )
    app = mod.application(
        API(),
        model_id=identity["model"],
        expected_image=envelope["image"],
        runtime_revision=envelope["runtime_revision"],
        start_key=owner.service.start_key,
        prepare_start=prepare,
        process_factory=Process,
        poll_seconds=0.01,
    )
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/isaac/stream",
            headers={
                "x-serverless2-session": sid,
                "x-serverless2-connection": "connection",
            },
            subprotocols=["x-nv-sessionid." + sid],
        ) as ws:
            ws.send_json(envelope)
            if ready:
                assert ws.receive_json()["type"] == "isaac.session.signaling_ready"
                processes[0].child.returncode = exit_code
            evidence = ws.receive_json()
            if cleanup == "stopped":
                assert ended.wait(3)
        health = client.get("/healthz")
    assert health.status_code == (
        503 if cleanup == "cleanup_unknown" or delivery_failed else 200
    )
    if not preparation_error:
        assert json.loads((tmp_path / "execution-outcome.json").read_text()) == evidence
    assert releases == ([] if cleanup == "cleanup_unknown" else [evidence["outcome"]])
    tunnel = load_portable("bridge").Tunnel(
        deepcopy(bridge.starts[0]), "wss://native.test/v1/isaac/stream"
    )
    tunnel.record_execution(evidence)
    bridge.observed.update(state="ended", execution=deepcopy(tunnel.execution))
    return evidence, releases


@pytest.mark.parametrize(
    "ready,exit_code,cancelled,cleanup,outcome,phase",
    [
        (False, 0, False, "stopped", "error", "initialization"),
        (False, 1, False, "cleanup_unknown", "error", "initialization"),
        (True, 0, False, "stopped", "done", "running"),
        (True, 0, False, "cleanup_unknown", "done", "running"),
        (True, 7, False, "stopped", "error", "running"),
        (False, 0, True, "stopped", "cancelled", "initialization"),
    ],
)
def test_observed_initialization_and_cleanup_remain_separate(
    tmp_path, ready, exit_code, cancelled, cleanup, outcome, phase
):
    owner, native, bridge, _, _ = fixture()
    evidence, releases = native_evidence(
        tmp_path,
        owner,
        native,
        bridge,
        ready=ready,
        exit_code=exit_code,
        cancelled=cancelled,
        cleanup=cleanup,
    )
    assert evidence["outcome"] == outcome and evidence["phase"] == phase
    assert evidence["signaling_ready"] is ready
    assert evidence["cleanup"] == (
        "unknown" if cleanup == "cleanup_unknown" else "settled"
    )
    assert native.value["status"] == (
        "attached" if cleanup == "cleanup_unknown" else "ended"
    )
    assert releases == ([] if cleanup == "cleanup_unknown" else [outcome])


@pytest.mark.parametrize("ready,phase", [(False, "initialization"), (True, "delivery")])
def test_secondary_delivery_failure_preserves_initialization_cause(
    tmp_path, ready, phase
):
    owner, native, bridge, _, _ = fixture()
    evidence, _ = native_evidence(
        tmp_path, owner, native, bridge, ready=ready, exit_code=0, delivery_failed=True
    )
    assert evidence["phase"] == phase and evidence["outcome"] == "error"


@pytest.mark.parametrize("ready", [False, True])
def test_real_bridge_tunnel_receives_bound_terminal_frame(tmp_path, ready):
    owner, native, bridge, store, info = fixture()
    evidence, _ = native_evidence(
        tmp_path, owner, native, bridge, ready=ready, exit_code=0
    )
    envelope = deepcopy(bridge.starts[0])
    messages = (
        [{"type": "isaac.session.signaling_ready", "session_id": native.value["id"]}]
        if ready
        else []
    ) + [evidence]

    class Upstream:
        def __init__(self):
            self.messages = list(map(json.dumps, messages))

        async def send(self, raw):
            assert json.loads(raw) == envelope["start"]

        async def recv(self):
            return self.messages.pop(0)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.messages:
                raise StopAsyncIteration
            return self.messages.pop(0)

    class Connection:
        async def __aenter__(self):
            return Upstream()

        async def __aexit__(self, *args):
            pass

    tunnel = load_portable("bridge").Tunnel(
        envelope,
        "wss://native.test/stream",
        connect_factory=lambda *args, **kwargs: Connection(),
    )
    asyncio.run(tunnel.run())
    assert tunnel.execution == evidence and tunnel.state == "ended"
    assert tunnel.error is None and "claim" not in tunnel.value
