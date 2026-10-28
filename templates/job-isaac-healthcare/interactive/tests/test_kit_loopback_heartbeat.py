"""CPU loopback protocol fidelity and the unchanged Native lifecycle bounds."""

import asyncio
import contextlib
import time
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient
from websockets.asyncio.client import connect
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.frames import OP_PING

import i4h_interactive.native as native
from test_sdk_signaling import QUERY, SID as PORTABLE_SID, portable_fixture
from test_signaling_transport import SID, chain, signaling


def kit_options(role):
    if role == "portable":
        client, _, _, factory, token = portable_fixture()
        with client.websocket_connect(
            "/signaling/sign_in?" + QUERY,
            headers={"origin": "https://app.test"},
            subprotocols=["x-nv-sessionid." + PORTABLE_SID, "Authorization.Bearer." + token],
        ) as socket:
            socket.send_text("ordinary-offer")
            assert socket.receive_text() == "ordinary-offer"
        return factory.calls[0][1]
    app, _, payload, state = chain()
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/isaac/stream",
            headers={"x-serverless2-session": SID, "x-serverless2-connection": "existing-native-connection"},
            subprotocols=["x-nv-sessionid." + SID],
        ) as socket:
            socket.send_json(payload["start"])
            assert socket.receive_json()["type"] == "isaac.session.signaling_ready"
            socket.send_json({"type": "viewer.attach", "peer_id": "private-peer", "signaling": signaling()})
            assert socket.receive_json()["type"] == "viewer.attached"
            socket.close()
            end = time.monotonic() + 2
            while not state.releases and time.monotonic() < end:
                time.sleep(0.005)
            assert len(state.releases) == 1
    return state.kit_connections[0][1]


@pytest.mark.parametrize("role", ["native", "portable"])
def test_fixed_kit_connection_does_not_timeout_a_non_pong_peer(role):
    options = kit_options(role)
    assert options["ping_interval"] is None
    assert options["proxy"] is None and options["open_timeout"] == 10
    assert not {"ping_timeout", "close_timeout"} & options.keys()

    async def run():
        ping_count = 0

        class NonPongConnection(ServerConnection):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                original = self.protocol.recv_frame

                def receive(frame):
                    nonlocal ping_count
                    if frame.opcode == OP_PING:
                        ping_count += 1
                        return  # Deliberate CPU peer: never emit Pong.
                    original(frame)

                self.protocol.recv_frame = receive

        async def echo(peer):
            with contextlib.suppress(ConnectionClosed):
                async for message in peer:
                    await peer.send(message)

        async with serve(echo, "127.0.0.1", 0, create_connection=NonPongConnection,
                         subprotocols=options["subprotocols"], ping_interval=None) as server:
            uri = "ws://127.0.0.1:" + str(server.sockets[0].getsockname()[1]) + "/sign_in"
            # Short test-only heartbeat deadlines make the negative control
            # finite; neither timeout is a product configuration change.
            control = {**options, "ping_interval": 0.01, "ping_timeout": 0.02, "close_timeout": 0.1}
            async with connect(uri, **control) as peer:
                with pytest.raises(ConnectionClosed) as failure:
                    await asyncio.wait_for(peer.recv(), 1)
                assert failure.value.sent.code == 1011
                assert failure.value.sent.reason == "keepalive ping timeout"
            assert ping_count >= 1
            prior = ping_count
            async with connect(uri, **options, ping_timeout=0.02, close_timeout=0.1) as peer:
                assert peer.keepalive_task is None
                # Explicitly prove this peer also withholds a manually sent
                # Pong, while application messages continue after that bound.
                pending = await peer.ping()
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(asyncio.shield(pending), 0.04)
                await peer.send("same-session-after-no-pong")
                assert await asyncio.wait_for(peer.recv(), 1) == "same-session-after-no-pong"
                assert ping_count == prior + 1
            with contextlib.suppress(ConnectionClosed):
                await pending

    asyncio.run(run())


def test_native_deadline_still_stops_and_releases_the_same_process(monkeypatch):
    app, _, payload, state = chain()
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/isaac/stream",
            headers={"x-serverless2-session": SID, "x-serverless2-connection": "existing-native-connection"},
            subprotocols=["x-nv-sessionid." + SID],
        ) as socket:
            socket.send_json(payload["start"])
            assert socket.receive_json()["type"] == "isaac.session.signaling_ready"
            socket.send_json({"type": "viewer.attach", "peer_id": "private-peer", "signaling": signaling()})
            assert socket.receive_json()["type"] == "viewer.attached"
            assert state.kit_connections[0][1]["ping_interval"] is None
            monkeypatch.setattr(native, "time", SimpleNamespace(time=lambda: payload["deadline_at"] + 1))
            receipt = socket.receive_json()
            assert receipt["type"] == "isaac.session.execution" and receipt["code"] == "session_cancelled"
            end = time.monotonic() + 2
            while not state.releases and time.monotonic() < end:
                time.sleep(0.005)
            assert state.releases == ["cancelled"]
            assert len(state.processes) == len(state.attaches) == len(state.kit_connections) == 1
            assert state.processes[0].state == "stopped"
