"""Private Kit-close evidence through the actual Native ASGI boundary."""

import hashlib
import json
import logging
import time

import pytest
from starlette.testclient import TestClient
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from test_signaling_transport import SID, chain, signaling


@pytest.mark.parametrize("kind", ["keepalive", "private_reason", "clean"])
def test_kit_close_diagnostic_preserves_viewer_error_and_native_lease(kind, monkeypatch, caplog):
    app, _, payload, state = chain()
    secret = "untrusted URL https://example.invalid/?token=do-not-log"
    error = {
        "keepalive": ConnectionClosedError(None, Close(1011, "keepalive ping timeout")),
        "private_reason": ConnectionClosedError(Close(4000, secret), Close(1000, ""), True),
        "clean": None,
    }[kind]
    caplog.set_level(logging.WARNING, logger="i4h_interactive.native")
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/isaac/stream",
            headers={"x-serverless2-session": SID, "x-serverless2-connection": "existing-native-connection"},
            subprotocols=["x-nv-sessionid." + SID],
        ) as socket:
            socket.send_json(payload["start"])
            assert socket.receive_json()["type"] == "isaac.session.signaling_ready"
            socket.send_json({"type": "viewer.attach", "peer_id": "private-peer", "signaling": signaling()})
            assert socket.receive_json() == {"type": "viewer.attached", "peer_id": "private-peer"}
            peer = state.kit_peers[0]
            original_next = type(peer).__anext__

            async def fail_after_echo(self):
                value = await original_next(self)
                if value == "close-now":
                    self.close_code = 1000 if error is None else 1006
                    if error is not None:
                        raise error
                    raise StopAsyncIteration
                return value

            monkeypatch.setattr(type(peer), "__anext__", fail_after_echo)
            # Wake any already-waiting iterator, then the patched fake peer
            # supplies an actual websockets close exception to Native.
            socket.send_json({"type": "viewer.data", "peer_id": "private-peer", "binary": False, "data": "arm"})
            assert socket.receive_json()["data"] == "arm"
            socket.send_json({"type": "viewer.data", "peer_id": "private-peer", "binary": False, "data": "close-now"})
            assert socket.receive_json() == {"type": "viewer.error", "peer_id": "private-peer", "code": "kit_viewer_closed"}
            assert len(state.attaches) == len(state.processes) == len(state.kit_connections) == 1
            assert state.releases == [] and state.processes[0].state == "running"
            assert state.processes[0].config["deadline_at"] == payload["deadline_at"]
            assert state.kit_connections[0][1]["ping_interval"] is None
            assert not {"ping_timeout", "close_timeout"} & state.kit_connections[0][1].keys()
            socket.close()
            end = time.monotonic() + 2
            while not state.releases and time.monotonic() < end:
                time.sleep(0.005)
            assert len(state.releases) == 1

    records = [r for r in caplog.records if r.name == "i4h_interactive.native" and r.msg == "Kit viewer transport ended: %s"]
    assert len(records) == 1
    encoded = records[0].args[0]
    assert len(encoded) < 1024 and secret not in encoded and SID not in encoded and "private-peer" not in encoded
    observed = json.loads(encoded)
    assert observed["phase"] == "kit_receive"
    assert observed["exception_type"] == ("ConnectionClosedError" if error else None)
    assert observed["final_close_code"] == (1006 if error else 1000)
    if kind == "keepalive":
        assert observed["received"] is None
        assert observed["sent"] == {"code": 1011, "reason": "keepalive ping timeout", "reason_sha256": None}
    elif kind == "private_reason":
        assert observed["received"] == {"code": 4000, "reason": None, "reason_sha256": hashlib.sha256(secret.encode()).hexdigest()}
        assert observed["sent"] == {"code": 1000, "reason": "", "reason_sha256": None}
    else:
        assert observed["received"] is observed["sent"] is None
    assert len(state.releases) == 1 and state.processes[0].state == "stopped"
