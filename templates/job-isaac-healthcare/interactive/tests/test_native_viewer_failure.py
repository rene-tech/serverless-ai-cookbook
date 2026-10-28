"""A Kit signaling socket failure must not terminate its Native GPU session."""

import time

import pytest
from starlette.testclient import TestClient
from websockets.exceptions import ConnectionClosedError

import test_signaling_transport as transport
from test_signaling_transport import SID, signaling


def failing_chain(monkeypatch, phase, error):
    actual_application = transport.native_application
    injected = [False]

    def application(*args, **kwargs):
        connect = kwargs["connect_factory"]

        async def failure_connect(uri, **options):
            if phase == "connect" and not injected[0]:
                injected[0] = True
                raise error
            peer = await connect(uri, **options)
            original_send, original_close = peer.send, peer.close

            async def send(data):
                if phase == "send" and data == "close-now" and not injected[0]:
                    injected[0] = True
                    raise error
                await original_send(data)

            async def close(code=1000):
                if phase == "close" and not injected[0]:
                    injected[0] = True
                    raise error
                await original_close(code)

            peer.send, peer.close = send, close
            return peer

        kwargs["connect_factory"] = failure_connect
        return actual_application(*args, **kwargs)

    monkeypatch.setattr(transport, "native_application", application)
    return transport.chain()


def start_and_fail(socket, payload, phase):
    socket.send_json(payload["start"])
    assert socket.receive_json()["type"] == "isaac.session.signaling_ready"
    socket.send_json({"type": "viewer.attach", "peer_id": "first-peer", "signaling": signaling()})
    if phase != "connect":
        assert socket.receive_json() == {"type": "viewer.attached", "peer_id": "first-peer"}
        if phase == "send":
            socket.send_json({"type": "viewer.data", "peer_id": "first-peer", "binary": False, "data": "close-now"})
        else:
            socket.send_json({"type": "viewer.detach", "peer_id": "first-peer", "close_code": 1000})
    assert socket.receive_json() == {"type": "viewer.error", "peer_id": "first-peer", "code": "kit_viewer_closed"}


def released(state):
    end = time.monotonic() + 2
    while not state.releases and time.monotonic() < end:
        time.sleep(0.005)
    assert len(state.releases) == 1


@pytest.mark.parametrize("phase,error", [
    ("connect", ConnectionClosedError(None, None)),
    ("send", ConnectionClosedError(None, None)),
    ("close", ConnectionClosedError(None, None)),
    ("connect", OSError("local Kit connection unavailable")),
    ("connect", TimeoutError("local Kit handshake timed out")),
])
def test_kit_failure_then_reattach_keeps_native_claim_process_and_deadline(monkeypatch, phase, error):
    app, _, payload, state = failing_chain(monkeypatch, phase, error)
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/isaac/stream",
            headers={"x-serverless2-session": SID, "x-serverless2-connection": "existing-native-connection"},
            subprotocols=["x-nv-sessionid." + SID],
        ) as socket:
            start_and_fail(socket, payload, phase)
            assert state.releases == [] and state.processes[0].state == "running"
            # Buffered data for the known closed viewer is drained, without
            # granting a viewer or replaying the original Native claim.
            socket.send_json({"type": "viewer.data", "peer_id": "first-peer", "binary": False, "data": "buffered-before-close"})
            socket.send_json({"type": "viewer.attach", "peer_id": "next-peer", "signaling": signaling("next-sdk-peer")})
            assert socket.receive_json() == {"type": "viewer.attached", "peer_id": "next-peer"}
            socket.send_json({"type": "viewer.data", "peer_id": "next-peer", "binary": False, "data": "same-kit-process"})
            assert socket.receive_json()["data"] == "same-kit-process"
            assert len(state.attaches) == len(state.processes) == 1
            assert state.processes[0].config["deadline_at"] == payload["deadline_at"]
            assert state.releases == []
            socket.close()
            released(state)
    assert state.processes[0].state == "stopped"


@pytest.mark.parametrize("invalid", ["unknown-peer", "malformed-data"])
def test_viewer_transport_failure_does_not_hide_invalid_native_protocol(monkeypatch, invalid):
    app, _, payload, state = failing_chain(monkeypatch, "send", ConnectionClosedError(None, None))
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/isaac/stream",
            headers={"x-serverless2-session": SID, "x-serverless2-connection": "existing-native-connection"},
            subprotocols=["x-nv-sessionid." + SID],
        ) as socket:
            start_and_fail(socket, payload, "send")
            socket.send_json({"type": "viewer.data", "peer_id": "unknown-peer" if invalid == "unknown-peer" else "first-peer",
                              "binary": invalid == "malformed-data", "data": "!invalid-base64!"})
            receipt = socket.receive_json()
            assert receipt["type"] == "isaac.session.execution" and receipt["outcome"] == "error"
            released(state)
    assert state.releases == ["error"] and state.processes[0].state == "stopped"
