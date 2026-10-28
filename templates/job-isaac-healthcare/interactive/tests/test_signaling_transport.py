"""Real bridge/Native ASGI chain with CPU process and Kit protocol doubles.

No network, GPU, admission, cluster or provider operation is performed. Native
edge claim injection and Kit execution are explicit doubles; both production
transport applications and all handshake validation execute unchanged.
"""

import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import hmac
import json
import ssl
import time
from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from i4h_interactive.bridge import application as bridge_application
from i4h_interactive.native import NoRedirectConnect, application as native_application
from i4h_interactive.signaling import SIGNALING_HEADER, encode_signaling


SID = "ses-76543210abcdef98"
SERVICE = "test-private-service-authority-" * 2


def chain():
    model = "ordinary-interactive"
    image = "registry.example/ordinary@sha256:" + "7" * 64
    key = b"q" * 32
    stamp = datetime.fromtimestamp(time.time() + 60, timezone.utc).isoformat()
    deadline = datetime.fromisoformat(stamp).timestamp()
    owner = {"tenant": "tenant-one", "owner": "owner-one", "model": model}
    target = {"cluster": "north", "variant": None, "id": model, "image": image, "gpu_class": None}
    state = SimpleNamespace(native_connections=[], kit_connections=[], processes=[], attaches=[], releases=[], frames=[], kit_close_codes=[], cancel_requested=False, kit_peers=[])

    class API:
        # This boundary has no method for allocating/admitting another session.
        async def attach(self, sid, connection, actual_model):
            assert (sid, connection, actual_model) == (SID, "existing-native-connection", model)
            state.attaches.append((sid, connection))
            return {"id": sid, "owner": owner, "deadline_at": stamp}

        async def watch(self, sid, actual_owner):
            assert sid == SID and actual_owner == owner
            return {"deadline_at": stamp, "cancel_requested": state.cancel_requested}

        async def release(self, sid, connection, outcome):
            assert (sid, connection) == (SID, "existing-native-connection")
            assert state.processes[-1].state == "stopped"
            state.releases.append(outcome)
            return {"id": sid, "status": "ended"}

    class Process:
        def __init__(self, config):
            self.config, self.child, self.state = config, None, "created"
            state.processes.append(self)

        async def start(self):
            self.child = SimpleNamespace(returncode=None)
            self.state = "running"

        async def wait_signaling(self):
            return None

        async def stop(self, reason):
            assert reason == "native_session_close"
            self.state = "stopped"

    class Kit:
        def __init__(self):
            self.queue = asyncio.Queue()
            state.kit_peers.append(self)

        def __aiter__(self):
            return self

        async def __anext__(self):
            value = await self.queue.get()
            if value is None:
                raise StopAsyncIteration
            return value

        async def send(self, data):
            await self.queue.put(data)

        async def close(self, code=1000):
            state.kit_close_codes.append(code)
            await self.queue.put(None)

    async def kit_connect(uri, **options):
        state.kit_connections.append((uri, options))
        return Kit()

    app = native_application(
        API(), model_id=model, expected_image=image, runtime_revision="ordinary-runtime",
        start_key=key, prepare_start=lambda *args: {"session_id": SID, "deadline_at": deadline, "signal_port": 49100},
        process_factory=Process, connect_factory=kit_connect, poll_seconds=0.01,
    )

    class NativeConnection:
        def __init__(self, uri, options):
            state.native_connections.append((uri, options))
            assert options["additional_headers"] == {"x-serverless2-session-claim": "retained-single-use-claim"}
            assert options["ssl"].check_hostname and options["ssl"].verify_mode == ssl.CERT_REQUIRED
            assert options["proxy"] is None and options["subprotocols"] == ["x-nv-sessionid." + SID]
            self.incoming, self.outgoing = asyncio.Queue(), asyncio.Queue()

        async def __aenter__(self):
            # Simulate only the existing Native edge's already-authenticated
            # claim→Pod headers. The real Native worker application runs below.
            scope = {"type": "websocket", "asgi": {"version": "3.0", "spec_version": "2.3"},
                     "scheme": "ws", "path": "/v1/isaac/stream", "raw_path": b"/v1/isaac/stream",
                     "query_string": b"", "root_path": "", "client": ("127.0.0.1", 1),
                     "server": ("127.0.0.1", 2), "subprotocols": ["x-nv-sessionid." + SID],
                     "headers": [(b"x-serverless2-session", SID.encode()),
                                 (b"x-serverless2-connection", b"existing-native-connection")]}
            self.task = asyncio.create_task(app(scope, self.incoming.get, self.outgoing.put))
            await self.incoming.put({"type": "websocket.connect"})
            accepted = await asyncio.wait_for(self.outgoing.get(), 2)
            assert accepted == {"type": "websocket.accept", "subprotocol": "x-nv-sessionid." + SID, "headers": []}
            return self

        async def __aexit__(self, *args):
            await self.incoming.put({"type": "websocket.disconnect", "code": 1000})
            await asyncio.wait_for(self.task, 2)

        async def send(self, data):
            frame = json.loads(data)
            state.frames.append(frame)
            await self.incoming.put({"type": "websocket.receive", "text": data})

        async def recv(self):
            event = await asyncio.wait_for(self.outgoing.get(), 3)
            if event["type"] == "websocket.close":
                raise StopAsyncIteration
            assert event["type"] == "websocket.send" and "text" in event
            return event["text"]

        def __aiter__(self):
            return self

        async def __anext__(self):
            return await self.recv()

    mapping = {"region": "north", "target": target, "native_endpoint": "wss://native.example/v1/isaac/stream", "runtime_revision": "ordinary-runtime"}
    bridge = bridge_application(service_token=SERVICE, targets=[mapping], connect_factory=lambda uri, **options: NativeConnection(uri, options))
    start = {"type": "isaac.session.start", "session_id": SID, "image": image, "runtime_revision": "ordinary-runtime",
             "region": "north", "target": target, "deadline_at": deadline, "start": {}, "display": {}}
    start["start_signature"] = hmac.new(key, json.dumps(start, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(), hashlib.sha256).hexdigest()
    payload = {"session_id": SID, "claim": "retained-single-use-claim", "deadline_at": deadline, "startup_timeout_s": 2, "start": start}
    return app, bridge, payload, state


def signaling(peer="sdk-peer-01", sid=SID):
    return {"peer_id": peer, "version": "2", "peer_role": "1", "pairing_id": sid}


def headers(value=None, nonce="nonce-one", authorization=None):
    return {"Authorization": authorization or "Bearer " + SERVICE,
            "x-isaac-attach-nonce": nonce,
            SIGNALING_HEADER: value if value is not None else encode_signaling(signaling(), SID)}


def wait_status(client, predicate):
    end = time.monotonic() + 2
    while time.monotonic() < end:
        value = client.get("/sessions/" + SID, headers={"Authorization": "Bearer " + SERVICE}).json()
        if predicate(value):
            return value
        time.sleep(0.005)
    raise AssertionError("CPU transport state did not settle")


def test_exact_sdk_handshake_reconnect_uses_one_native_lease_and_process():
    _, app, payload, state = chain()
    with TestClient(app) as client:
        assert client.post("/sessions", json=payload, headers={"Authorization": "Bearer " + SERVICE}).status_code == 202
        wait_status(client, lambda value: value["state"] == "ready")
        for number, peer in enumerate(("ordinary-browser-54321", "ordinary-browser-reconnected-98765")):
            value = signaling(peer)
            with client.websocket_connect("/sessions/" + SID + "/attach",
                    headers=headers(encode_signaling(value, SID), nonce=f"nonce-{number}"),
                    subprotocols=["x-nv-sessionid." + SID]) as socket:
                socket.send_text("unchanged-sdk-signaling-data")
                assert socket.receive_text() == "unchanged-sdk-signaling-data"
                assert len(state.processes) == len(state.attaches) == len(state.native_connections) == 1
                assert state.processes[0].config["deadline_at"] == payload["deadline_at"]
                assert state.releases == []
                socket.close()
                wait_status(client, lambda value: not value["viewer_attached"])
            wait_status(client, lambda value: not value["viewer_attached"])
        expected = [
            f"ws://127.0.0.1:49100/sign_in?peer_id={peer}&version=2&peer_role=1&pairing_id={SID}"
            for peer in ("ordinary-browser-54321", "ordinary-browser-reconnected-98765")]
        assert [uri for uri, _ in state.kit_connections] == expected
        attaches = [frame for frame in state.frames if frame["type"] == "viewer.attach"]
        assert [frame["signaling"] for frame in attaches] == [signaling(peer) for peer in ("ordinary-browser-54321", "ordinary-browser-reconnected-98765")]
        assert attaches[0]["peer_id"] != attaches[1]["peer_id"]
        assert all(frame["peer_id"] != frame["signaling"]["peer_id"] for frame in attaches)
        assert len(state.native_connections) == 1
        assert client.post("/sessions", json=payload, headers={"Authorization": "Bearer " + SERVICE}).status_code == 200
        assert len(state.native_connections) == 1
    assert len(state.attaches) == len(state.releases) == len(state.processes) == 1
    assert state.processes[0].state == "stopped"


@pytest.mark.parametrize("bad", [
    "peer_id=x&peer_id=y&version=2&peer_role=1&pairing_id=" + SID,
    "peer_id=x&version=2&peer_role=1&pairing_id=" + SID + "&token=not-allowed",
    "peer_id=x&version=2&peer_role=1&pairing_id=ses-1111111111111111",
    "peer_id=x&version=3&peer_role=1&pairing_id=" + SID,
    "peer_id=x&version=2&peer_role=0&pairing_id=" + SID,
    "peer_id=https%3A%2F%2Fother.example&version=2&peer_role=1&pairing_id=" + SID,
    "peer_id=%0D%0Awrong&version=2&peer_role=1&pairing_id=" + SID,
    "peer_id=x&version=2&peer_role=1",
])
def test_bad_query_has_no_kit_connection_or_new_native_work(bad):
    _, app, payload, state = chain()
    with TestClient(app) as client:
        client.post("/sessions", json=payload, headers={"Authorization": "Bearer " + SERVICE})
        wait_status(client, lambda value: value["state"] == "ready")
        with pytest.raises(WebSocketDisconnect) as failure:
            with client.websocket_connect("/sessions/" + SID + "/attach", headers=headers(bad)):
                pass
        assert failure.value.code == 1008
        assert state.kit_connections == [] and state.releases == []
        assert len(state.native_connections) == len(state.attaches) == len(state.processes) == 1
        # Invalid metadata didn't consume the nonce or damage the existing lease.
        with client.websocket_connect("/sessions/" + SID + "/attach", headers=headers()) as socket:
            socket.send_text("same-owner-valid-handshake")
            assert socket.receive_text() == "same-owner-valid-handshake"
            socket.close()
            wait_status(client, lambda value: not value["viewer_attached"])


def test_private_auth_duplicate_headers_nonce_and_unknown_sid_stay_fail_closed():
    _, app, payload, state = chain()
    with TestClient(app) as client:
        client.post("/sessions", json=payload, headers={"Authorization": "Bearer " + SERVICE})
        wait_status(client, lambda value: value["state"] == "ready")
        duplicated = httpx.Headers(list(headers().items()) + [(SIGNALING_HEADER, encode_signaling(signaling(), SID))])
        cases = [(SID, headers(authorization="Bearer wrong-service-owner")), (SID, duplicated),
                 ("ses-1111111111111111", headers()), (SID + "/ignored", headers())]
        for sid, value in cases:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect("/sessions/" + sid + "/attach", headers=value):
                    pass
        assert state.kit_connections == [] and len(state.native_connections) == 1
        with client.websocket_connect("/sessions/" + SID + "/attach", headers=headers()) as socket:
            socket.send_text("one-peer"); assert socket.receive_text() == "one-peer"
            socket.close()
            wait_status(client, lambda value: not value["viewer_attached"])
        wait_status(client, lambda value: not value["viewer_attached"])
        with pytest.raises(WebSocketDisconnect) as failure:
            with client.websocket_connect("/sessions/" + SID + "/attach", headers=headers()):
                pass
        assert failure.value.code == 1008 and len(state.kit_connections) == 1 and len(state.native_connections) == 1


@pytest.mark.parametrize("change", [
    {"pairing_id": "ses-1111111111111111"}, {"version": "wrong"}, {"token": "not-allowed"}, {"peer_id": "https://other.example"},
])
def test_native_revalidates_typed_map_before_kit_connection(change):
    app, _, payload, state = chain()
    with TestClient(app) as client:
        with client.websocket_connect("/v1/isaac/stream", headers={"x-serverless2-session": SID,
                "x-serverless2-connection": "existing-native-connection"}, subprotocols=["x-nv-sessionid." + SID]) as socket:
            socket.send_json(payload["start"])
            assert socket.receive_json()["type"] == "isaac.session.signaling_ready"
            socket.send_json({"type": "viewer.attach", "peer_id": "internal-peer", "signaling": {**signaling(), **change}})
            evidence = socket.receive_json()
            assert evidence["type"] == "isaac.session.execution" and evidence["outcome"] == "error"
    assert state.kit_connections == [] and len(state.attaches) == len(state.releases) == 1


def test_fixed_loopback_client_does_not_follow_http_redirect():
    async def check():
        response = Response(302, "Found", Headers({"Location": "ws://untrusted.example/sign_in"}))
        error = InvalidStatus(response)
        ordinary = connect("ws://127.0.0.1:49100/sign_in", proxy=None)
        bounded = NoRedirectConnect("ws://127.0.0.1:49100/sign_in", proxy=None)
        assert ordinary.process_redirect(error) == "ws://untrusted.example/sign_in"
        assert bounded.process_redirect(error) is error
    asyncio.run(check())
