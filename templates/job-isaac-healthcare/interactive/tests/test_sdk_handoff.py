"""Actual CPU bridge/Native and portable SDK socket-handoff regressions."""

import asyncio
import time
from types import MethodType
from urllib.parse import parse_qsl

import pytest
from i4h_interactive.signaling import (
    SignalingPeer,
    encode_signaling,
    parse_signaling_query,
)
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_sdk_signaling import FIELDS, QUERY, portable_fixture
from test_signaling_transport import (
    SERVICE,
    SID,
    chain,
    headers,
    signaling,
    wait_status,
)


def test_main_to_worker_handoff_preserves_one_native_process_peer_and_media():
    _, app, payload, state = chain()
    auth = {"Authorization": "Bearer " + SERVICE}
    with TestClient(app) as client:
        client.post("/sessions", json=payload, headers=auth)
        wait_status(client, lambda item: item["state"] == "ready")
        first = signaling("ordinary-sdk-main-and-worker")
        with client.websocket_connect(
            "/sessions/" + SID + "/attach",
            headers=headers(encode_signaling(first, SID), nonce="initial"),
        ) as socket:
            socket.send_text("original-offer")
            assert socket.receive_text() == "original-offer"
            assert (
                client.post(
                    "/sessions/" + SID + "/media",
                    json={"width": 880, "height": 640},
                    headers=auth,
                ).status_code
                == 200
            )
            socket.close(code=4001)
        # No wait/poll between sockets: exercise the SDK's immediate reconnect.
        reconnect = {**first, "reconnect": "1"}
        with client.websocket_connect(
            "/sessions/" + SID + "/attach",
            headers=headers(encode_signaling(reconnect, SID), nonce="worker"),
        ) as socket:
            socket.send_bytes(b"same-sdk-ack-stream")
            assert socket.receive_bytes() == b"same-sdk-ack-stream"
            value = wait_status(client, lambda item: item["viewer_attached"])
            assert (
                value["media_ready"] is True and value["media_evidence"]["width"] == 880
            )
            assert state.kit_close_codes == [4001]
            assert (
                len(state.processes)
                == len(state.attaches)
                == len(state.native_connections)
                == 1
            )
            assert (
                state.releases == []
                and state.processes[0].config["deadline_at"] == payload["deadline_at"]
            )
            attaches = [
                item for item in state.frames if item["type"] == "viewer.attach"
            ]
            assert (
                len(attaches) == 2 and attaches[0]["peer_id"] == attaches[1]["peer_id"]
            )
            assert state.kit_connections[-1][0].endswith("&reconnect=1")
            socket.close()
            wait_status(client, lambda item: not item["viewer_attached"])
        value = wait_status(client, lambda item: not item["viewer_attached"])
        assert value["media_ready"] is None
        assert state.kit_close_codes == [4001, 1000]
        assert len(state.processes) == 1 and not state.releases
    assert len(state.releases) == 1


def test_worker_reconnect_requires_observed_close_and_same_logical_peer():
    _, app, payload, state = chain()
    auth = {"Authorization": "Bearer " + SERVICE}
    with TestClient(app) as client:
        client.post("/sessions", json=payload, headers=auth)
        wait_status(client, lambda item: item["state"] == "ready")
        reconnect = {**signaling(), "reconnect": "1"}
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/sessions/" + SID + "/attach",
                headers=headers(encode_signaling(reconnect, SID), nonce="premature"),
            ):
                pass
        assert state.kit_connections == []
        with client.websocket_connect(
            "/sessions/" + SID + "/attach", headers=headers(nonce="main")
        ) as socket:
            socket.send_text("one")
            assert socket.receive_text() == "one"
            socket.close(code=4001)
        wait_status(client, lambda item: item["viewer_attached"])
        assert (
            client.post(
                "/sessions/" + SID + "/media",
                json={"width": 1920, "height": 1080},
                headers=auth,
            ).status_code
            == 200
        )
        wrong = {**signaling("another-peer"), "reconnect": "1"}
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/sessions/" + SID + "/attach",
                headers=headers(encode_signaling(wrong, SID), nonce="wrong-peer"),
            ):
                pass
        assert len(state.kit_connections) == 1
        with client.websocket_connect(
            "/sessions/" + SID + "/attach",
            headers=headers(encode_signaling(reconnect, SID), nonce="worker"),
        ) as socket:
            socket.send_text("two")
            assert socket.receive_text() == "two"
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(
                    "/sessions/" + SID + "/attach",
                    headers=headers(
                        encode_signaling(reconnect, SID), nonce="duplicate-worker"
                    ),
                ):
                    pass
            assert len(state.kit_connections) == 2
            socket.close()
            wait_status(client, lambda item: not item["viewer_attached"])
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/sessions/" + SID + "/attach",
                headers=headers(encode_signaling(reconnect, SID), nonce="after-close"),
            ):
                pass
        assert (
            len(state.processes) == 1
            and len(state.kit_connections) == 2
            and not state.releases
        )


def test_handoff_state_expiry_failure_and_deadline_are_not_new_authority():
    now = [10.0]
    peer = SignalingPeer(SID, 20.0, 3.0, clock=lambda: now[0])
    first = signaling()
    reconnect = {**first, "reconnect": "1"}
    peer.begin(first)
    peer.connected()
    peer.closed(4001)
    assert peer.attached and peer.handoff_until == 13.0
    now[0] = 13.0
    assert not peer.attached
    with pytest.raises(PermissionError):
        peer.begin(reconnect)
    peer.begin(first)
    peer.connected()
    peer.closed(1006)
    assert not peer.attached
    with pytest.raises(PermissionError):
        peer.begin(reconnect)
    now[0] = 19.0
    peer.begin(first)
    peer.connected()
    peer.closed(4001)
    assert peer.handoff_until == 20.0
    now[0] = 20.0
    with pytest.raises(PermissionError):
        peer.begin(reconnect)
    with pytest.raises(PermissionError):
        peer.begin(first)


@pytest.mark.parametrize(
    "suffix",
    [
        "&reconnect=0",
        "&reconnect=true",
        "&reconnect=1&reconnect=1",
        "&reconnect=1&credential=x",
    ],
)
def test_optional_reconnect_is_exact_noncredential_metadata(suffix):
    with pytest.raises(PermissionError):
        parse_signaling_query(
            parse_qsl(encode_signaling(signaling(), SID) + suffix), SID
        )


def test_portable_handoff_preserves_capability_origin_deadline_and_process():
    client, config, process, factory, token = portable_fixture()
    auth = {"origin": "https://app.test"}
    protocols = [
        "x-nv-sessionid." + FIELDS["pairing_id"],
        "Authorization.Bearer." + token,
    ]
    with client.websocket_connect(
        "/signaling/sign_in?" + QUERY, headers=auth, subprotocols=protocols
    ) as socket:
        socket.send_text("offer")
        assert socket.receive_text() == "offer"
        socket.close(code=4001)
    assert process.active_connection
    assert factory.peers[0].close_codes == [4001]
    with client.websocket_connect(
        "/signaling/sign_in?" + QUERY + "&reconnect=1",
        headers=auth,
        subprotocols=protocols,
    ) as socket:
        socket.send_bytes(b"worker")
        assert socket.receive_bytes() == b"worker"
        assert process.active_connection and factory.calls[-1][0].endswith(
            "&reconnect=1"
        )
        assert token not in repr(factory.calls)
    assert not process.active_connection and process.state == "signaling"
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/signaling/sign_in?" + QUERY + "&reconnect=1",
            headers=auth,
            subprotocols=protocols,
        ):
            pass
    assert len(factory.calls) == 2


def test_native_cancel_during_handoff_does_not_revive_or_allocate():
    _, app, payload, state = chain()
    auth = {"Authorization": "Bearer " + SERVICE}
    with TestClient(app) as client:
        client.post("/sessions", json=payload, headers=auth)
        wait_status(client, lambda item: item["state"] == "ready")
        with client.websocket_connect(
            "/sessions/" + SID + "/attach", headers=headers(nonce="initial-cancel")
        ) as socket:
            socket.send_text("initial")
            assert socket.receive_text() == "initial"
            socket.close(code=4001)
        state.cancel_requested = True
        wait_status(client, lambda item: item["state"] == "ended")
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/sessions/" + SID + "/attach",
                headers=headers(
                    encode_signaling({**signaling(), "reconnect": "1"}, SID),
                    nonce="late-worker",
                ),
            ):
                pass
        assert (
            len(state.kit_connections)
            == len(state.processes)
            == len(state.native_connections)
            == 1
        )
        assert len(state.releases) == 1 and state.processes[0].state == "stopped"


def test_genuine_kit_close_clears_media_and_requires_new_viewer():
    _, app, payload, state = chain()
    auth = {"Authorization": "Bearer " + SERVICE}
    with TestClient(app) as client:
        client.post("/sessions", json=payload, headers=auth)
        wait_status(client, lambda item: item["state"] == "ready")
        with client.websocket_connect(
            "/sessions/" + SID + "/attach", headers=headers(nonce="initial-failure")
        ) as socket:
            socket.send_text("initial")
            assert socket.receive_text() == "initial"
            assert (
                client.post(
                    "/sessions/" + SID + "/media",
                    json={"width": 900, "height": 600},
                    headers=auth,
                ).status_code
                == 200
            )
            client.portal.call(state.kit_peers[0].queue.put, None)
            ended = wait_status(client, lambda item: not item["viewer_attached"])
            assert ended["media_ready"] is None
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/sessions/" + SID + "/attach",
                headers=headers(
                    encode_signaling({**signaling(), "reconnect": "1"}, SID),
                    nonce="after-failure",
                ),
            ):
                pass
        assert (
            len(state.kit_connections)
            == len(state.processes)
            == len(state.native_connections)
            == 1
        )
        assert not state.releases


def test_portable_owned_private_close_cannot_be_misreported_as_kit_failure():
    client, _, process, factory, token = portable_fixture()
    auth = {"origin": "https://app.test"}
    protocols = [
        "x-nv-sessionid." + FIELDS["pairing_id"],
        "Authorization.Bearer." + token,
    ]
    with client.websocket_connect(
        "/signaling/sign_in?" + QUERY, headers=auth, subprotocols=protocols
    ) as socket:
        socket.send_text("offer")
        assert socket.receive_text() == "offer"

        async def close(peer, code=1000):
            peer.close_codes.append(code)
            # websockets raises for application-private4001 on its read side.
            await peer.queue.put(RuntimeError("private-close-reader-termination"))
            await asyncio.sleep(0)

        factory.peers[0].close = MethodType(close, factory.peers[0])
        socket.close(code=4001)
    assert process.active_connection
    with client.websocket_connect(
        "/signaling/sign_in?" + QUERY + "&reconnect=1",
        headers=auth,
        subprotocols=protocols,
    ) as socket:
        socket.send_text("worker")
        assert socket.receive_text() == "worker"
    assert not process.active_connection


def test_portable_health_expires_handoff_without_new_socket_or_timer(monkeypatch):
    from i4h_interactive import server

    now = [time.time()]
    original = server.SignalingPeer

    def state(sid, deadline, timeout):
        return original(sid, deadline, min(timeout, 2), clock=lambda: now[0])

    monkeypatch.setattr(server, "SignalingPeer", state)
    client, _, process, factory, token = portable_fixture()
    process.status = lambda: {"signaling_connected": process.active_connection}
    protocols = [
        "x-nv-sessionid." + FIELDS["pairing_id"],
        "Authorization.Bearer." + token,
    ]
    with client.websocket_connect(
        "/signaling/sign_in?" + QUERY,
        headers={"origin": "https://app.test"},
        subprotocols=protocols,
    ) as socket:
        socket.send_text("offer")
        assert socket.receive_text() == "offer"
        socket.close(code=4001)
    auth = {"Authorization": "Bearer " + token}
    assert client.get("/health", headers=auth).json()["signaling_connected"] is True
    now[0] += 3
    assert client.get("/health", headers=auth).json()["signaling_connected"] is False
    assert len(factory.calls) == 1
