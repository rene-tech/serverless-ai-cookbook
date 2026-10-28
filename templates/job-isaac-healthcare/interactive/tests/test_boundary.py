import asyncio
import hashlib
import hmac
import json
import sys
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from i4h_interactive.bridge import Tunnel
from i4h_interactive.contract import authenticate, kit_arguments, turn_credentials
from i4h_interactive.native import NativeSessionAPI
from i4h_interactive.native import application as native_application
from i4h_interactive.process import SessionProcess
from starlette.testclient import TestClient


def config(tmp_path):
    return {
        "session_id": "ses-0123456789abcdef",
        "command": [sys.executable, "-c", "import time; time.sleep(60)"],
        "work_dir": str(tmp_path / "session"),
        "browser_origin": "https://app.test",
        "media_host": "10.0.0.5",
        "signal_port": 49100,
        "media_port": 47998,
        "proxy_port": 49200,
        "deadline_at": time.time() + 60,
        "stop_grace_seconds": 1,
        "startup_timeout_seconds": 1,
        "network_mode": "turn-relay",
        "turn_url": "turns:turn.test:443?transport=tcp",
    }


def test_official_sdk_auth_wire_owner_origin_and_secret_stripping(tmp_path):
    c, token = config(tmp_path), "x" * 43
    headers = {
        "origin": c["browser_origin"],
        "sec-websocket-protocol": f"x-nv-sessionid.{c['session_id']}, Authorization.Bearer.{token}",
    }
    assert authenticate(headers, c, token) == [f"x-nv-sessionid.{c['session_id']}"]
    for changed in (
        {**headers, "origin": "https://other.test"},
        {
            **headers,
            "sec-websocket-protocol": headers["sec-websocket-protocol"].replace(
                c["session_id"], "another"
            ),
        },
        {**headers, "authorization": "Bearer " + token},
    ):
        with pytest.raises(PermissionError):
            authenticate(changed, c, token)


def test_native_deadline_turn_scope_and_general_launch_arguments(tmp_path):
    c = config(tmp_path)
    ice = turn_credentials(b"s" * 40, c["session_id"], c["deadline_at"], c["turn_url"])
    assert ice["iceTransportPolicy"] == "relay"
    assert (
        ice["iceServers"][0]["username"] == f"{int(c['deadline_at'])}:{c['session_id']}"
    )
    args = kit_arguments(c, width=1280.0, height=720, fps=30.0)
    assert "--/app/window/width=1280" in args
    assert any(x.endswith("targetFps=30") for x in args)


def test_real_cpu_process_is_joined_and_not_restarted(tmp_path):
    async def run():
        p = SessionProcess(config(tmp_path))
        await p.start()
        pid = p.child.pid
        with pytest.raises(RuntimeError, match="twice"):
            await p.start()
        await p.stop("test_owner_stop")
        assert (
            p.state == "stopped"
            and p.child.returncode is not None
            and p.child.pid == pid
        )
        assert (
            json.loads((tmp_path / "session" / "process-closeout.json").read_text())[
                "media_ready"
            ]
            is None
        )

    asyncio.run(run())


def test_native_attach_rejects_wrong_owner_before_process():
    class Response:
        status_code = 200

        def json(self):
            return {
                "id": "ses-0123456789abcdef",
                "status": "attached",
                "connection": "conn",
                "owner": {"tenant": "a", "owner": "b", "model": "wrong"},
            }

    class HTTP:
        async def request(self, *args, **kwargs):
            return Response()

    class Token:
        def read_text(self):
            return "synthetic-pod-token"

    async def run():
        api = NativeSessionAPI("https://native.test", "/not-read", http=HTTP())
        api.token_file = Token()
        with pytest.raises(ValueError, match="owner"):
            await api.attach("ses-0123456789abcdef", "conn", "isaac")

    asyncio.run(run())


def test_viewer_disconnect_keeps_same_native_tunnel_for_reconnect():
    class Upstream:
        def __init__(self):
            self.sent = []
            self.tunnel = None

        async def send(self, raw):
            frame = json.loads(raw)
            self.sent.append(frame)
            if frame["type"] == "viewer.attach":
                await self.tunnel.viewer.put({"type": "viewer.attached"})

    class Socket:
        async def accept(self, **kwargs):
            pass

        async def receive(self):
            return {"type": "websocket.disconnect"}

        async def close(self, **kwargs):
            raise AssertionError("same session should attach")

    async def run():
        signaling = {"peer_id": "ordinary-sdk-peer", "version": "2", "peer_role": "1",
                     "pairing_id": "ses-0123456789abcdef"}
        t = Tunnel(
            {"session_id": "ses-0123456789abcdef", "startup_timeout_s": 1, "deadline_at": time.time() + 60},
            "wss://native.test",
        )
        t.upstream = Upstream()
        t.upstream.tunnel = t
        t.state = "ready"
        t.ready.set()
        await t.attach(Socket(), signaling)
        await t.attach(Socket(), {**signaling, "peer_id": "reconnected-sdk-peer"})
        assert t.state == "ready" and t.upstream is not None
        assert [x["type"] for x in t.upstream.sent] == [
            "viewer.attach",
            "viewer.detach",
            "viewer.attach",
            "viewer.detach",
        ]
        assert [x["signaling"]["peer_id"] for x in t.upstream.sent if x["type"] == "viewer.attach"] == [
            "ordinary-sdk-peer", "reconnected-sdk-peer"]
        assert t.upstream.sent[0]["peer_id"] != t.upstream.sent[2]["peer_id"]

    asyncio.run(run())


@pytest.mark.parametrize("delivery_failure", [False, True])
def test_actual_native_protocol_reconnect_then_owner_cancel_joins_before_release(
    delivery_failure,
):
    sid, model, key = "ses-0123456789abcdef", "isaac-interactive", b"s" * 32
    deadline = time.time() + 60
    stamp = datetime.fromtimestamp(deadline, UTC).isoformat()
    deadline = datetime.fromisoformat(stamp).timestamp()
    owner = {"tenant": "a", "owner": "b", "model": model}
    events = []

    class API:
        cancelled = False

        async def attach(self, actual, connection, actual_model):
            assert (actual, connection, actual_model) == (sid, "connection", model)
            events.append("native_attach")
            return {"id": sid, "deadline_at": stamp, "owner": owner}

        async def watch(self, actual, actual_owner):
            assert actual == sid and actual_owner == owner
            return {"deadline_at": stamp, "cancel_requested": self.cancelled}

        async def release(self, actual, connection, outcome):
            assert events[-1] == "process_joined"
            assert outcome == ("error" if delivery_failure else "cancelled")
            events.append("native_release")
            return {"id": actual, "status": "ended"}

    class Process:
        def __init__(self, cfg):
            self.child = None
            self.state = "created"

        async def start(self):
            events.append("process_start")
            self.child = SimpleNamespace(returncode=None)

        async def wait_signaling(self):
            self.state = "signaling"

        async def stop(self, reason):
            self.state = "stopped"
            events.append("process_joined")

    class Kit:
        def __init__(self):
            self.q = asyncio.Queue()

        def __aiter__(self):
            return self

        async def __anext__(self):
            data = await self.q.get()
            if data is None:
                raise StopAsyncIteration
            return data

        async def send(self, data):
            await self.q.put(data)

        async def close(self):
            await self.q.put(None)

    connections = []

    async def connect(*args, **kwargs):
        connections.append((args, kwargs))
        return Kit()

    api = API()

    def finalize():
        if delivery_failure:
            raise RuntimeError("synthetic unknown PUT outcome")

    app = native_application(
        api,
        model_id=model,
        expected_image="image",
        runtime_revision="r1",
        start_key=key,
        prepare_start=lambda *args: {
            "session_id": sid,
            "deadline_at": deadline,
            "signal_port": 49100,
            "_finalize": finalize,
        },
        process_factory=Process,
        connect_factory=connect,
        poll_seconds=0.01,
    )
    envelope = {
        "type": "isaac.session.start",
        "session_id": sid,
        "image": "image",
        "runtime_revision": "r1",
        "region": "test-region",
        "target": {
            "cluster": "test-cluster",
            "variant": None,
            "id": model,
            "image": "image",
            "gpu_class": None,
        },
        "deadline_at": deadline,
        "start": {},
        "display": {},
    }
    envelope["start_signature"] = hmac.new(
        key,
        json.dumps(
            envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
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
            assert ws.receive_json()["type"] == "isaac.session.signaling_ready"
            ws.send_json({"type": "viewer.attach", "peer_id": "first", "signaling": {
                "peer_id": "sdk-first", "version": "2", "peer_role": "1", "pairing_id": sid}})
            assert ws.receive_json() == {"type": "viewer.attached", "peer_id": "first"}
            ws.send_json(
                {
                    "type": "viewer.data",
                    "peer_id": "first",
                    "binary": False,
                    "data": "ordinary-signaling",
                }
            )
            assert ws.receive_json()["data"] == "ordinary-signaling"
            ws.send_json({"type": "viewer.detach", "peer_id": "first"})
            # Cancelling our own reader is no longer emitted as a Kit failure.
            ws.send_json({"type": "viewer.attach", "peer_id": "second", "signaling": {
                "peer_id": "sdk-second", "version": "2", "peer_role": "1", "pairing_id": sid}})
            assert ws.receive_json() == {"type": "viewer.attached", "peer_id": "second"}
            assert events.count("process_start") == 1
            api.cancelled = True
            while True:
                event = ws.receive()
                if event["type"] == "websocket.close":
                    break
        health = client.get("/healthz")
        assert health.status_code == (503 if delivery_failure else 200)
        assert client.get("/livez").status_code == 200
    assert events == [
        "native_attach",
        "process_start",
        "process_joined",
        "native_release",
    ]
    assert [args[0] for args, _ in connections] == [
        f"ws://127.0.0.1:49100/sign_in?peer_id=sdk-{peer}&version=2&peer_role=1&pairing_id={sid}"
        for peer in ("first", "second")]
    assert all(kwargs == {"subprotocols": [f"x-nv-sessionid.{sid}"], "proxy": None,
                          "max_size": 1024 * 1024, "max_queue": 2, "open_timeout": 10}
               for _, kwargs in connections)


def test_delivery_uses_exact_sha_length_and_preserves_bytes_after_unknown_put(
    tmp_path, monkeypatch
):
    from i4h_interactive import delivery

    data = tmp_path / "output"
    data.mkdir()
    (data / "ordinary-result.json").write_text('{"recorded": true}\n')
    calls = []

    def put(url, *, content, headers, **kwargs):
        payload = b"".join(content)
        assert headers["X-FS2-Artifact-SHA256"] == hashlib.sha256(payload).hexdigest()
        assert int(headers["Content-Length"]) == len(payload)
        calls.append(url)
        raise TimeoutError("synthetic lost PUT ACK")

    monkeypatch.setattr(delivery.httpx, "put", put)
    with pytest.raises(TimeoutError):
        delivery.deliver(
            tmp_path,
            "session-ordinary",
            {
                "archive_put_url": "https://app.test/archive",
                "receipt_put_url": "https://app.test/receipt",
            },
        )
    assert calls == ["https://app.test/archive"]
    receipt = json.loads((tmp_path / "delivery.json").read_text())
    assert delivery.sha(tmp_path / "output.tar") == receipt["archive"]["sha256"]
    assert (data / "ordinary-result.json").is_file()


def test_own_pod_ip_requires_exact_unique_hostname_mapping(tmp_path):
    from i4h_interactive.native_server import own_pod_ip

    hosts = tmp_path / "hosts"
    hosts.write_text(
        "127.0.0.1 localhost\n10.48.1.5 actual-pod\n10.48.1.6 unrelated-pod\n"
    )
    assert own_pod_ip("actual-pod", hosts) == "10.48.1.5"
    with pytest.raises(RuntimeError, match="unambiguous"):
        own_pod_ip("absent-pod", hosts)
    hosts.write_text(hosts.read_text() + "10.48.1.7 actual-pod\n")
    with pytest.raises(RuntimeError, match="unambiguous"):
        own_pod_ip("actual-pod", hosts)


def test_baked_settings_pin_postpublication_image_and_consume_secret(tmp_path):
    from i4h_interactive.native_server import consume_start_key, load_settings

    path = tmp_path / "worker.json"
    path.write_text(
        json.dumps(
            {
                "image_env": "EXPECTED",
                "start_key_env": "KEY",
                "runtime_python": "/opt/i4h/arena/.venv/bin/python",
            }
        )
    )
    env = {"EXPECTED": "registry.example/worker@sha256:" + "a" * 64, "KEY": "b" * 64}
    config = load_settings(path, env)
    assert config["image"] == env["EXPECTED"]
    assert consume_start_key(config, env) == bytes.fromhex("b" * 64)
    assert "KEY" not in env
    env["EXPECTED"] = "registry.example/worker:mutable"
    with pytest.raises(ValueError, match="immutable"):
        load_settings(path, env)


def test_policy_is_actually_sealed_without_python_memfd_api(monkeypatch):
    import os

    from i4h_interactive.isolation import sealed_policy

    monkeypatch.delattr(os, "memfd_create", raising=False)
    fd = sealed_policy({"uid": 123456, "command": ["/usr/bin/true"]})
    try:
        assert json.loads(os.read(fd, 4096))["uid"] == 123456
        with pytest.raises(PermissionError):
            os.write(fd, b"changed")
        with pytest.raises(PermissionError):
            os.ftruncate(fd, 0)
    finally:
        os.close(fd)


def test_relay_uses_exact_multiple_worker_cidrs_and_model_selector():
    import runpy
    from pathlib import Path

    render = runpy.run_path(str(Path(__file__).parents[1] / "render_relay.py"))[
        "render"
    ]
    manifest = render(
        namespace="relay",
        worker_namespace="models",
        model="ordinary-variant",
        image="registry.example/turn@sha256:" + "c" * 64,
        public_ip="192.0.2.1",
        pod_cidr=["10.6.5.0/24", "10.0.39.0/24"],
        hostname="turn.example",
        tls_secret="turn-tls",
        auth_secret="turn-auth",
        relay_min=52000,
        relay_max=52003,
    )
    cm, _, service, worker_policy, relay_policy = manifest["items"]
    assert [
        s
        for s in cm["data"]["turnserver.conf"].splitlines()
        if s.startswith("allowed-peer-ip=")
    ] == [
        "allowed-peer-ip=10.0.39.0-10.0.39.255",
        "allowed-peer-ip=10.6.5.0-10.6.5.255",
    ]
    assert worker_policy["spec"]["podSelector"]["matchLabels"] == {
        "serving.kserve.io/inferenceservice": "ordinary-variant"
    }
    assert relay_policy["spec"]["egress"][0]["ports"] == [
        {"protocol": "UDP", "port": 47998}
    ]
    assert {p["protocol"] for p in service["spec"]["ports"]} == {"TCP", "UDP"}
