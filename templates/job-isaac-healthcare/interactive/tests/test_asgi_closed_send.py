"""Real installed ASGI closed-send branches, not arbitrary RuntimeError doubles."""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocket, WebSocketState
from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol

from i4h_interactive.bridge import Tunnel
from i4h_interactive.server import application
from test_sdk_close_race import ClosingBrowser
from test_sdk_signaling import Echo, FIELDS, SID


class ASGIClosingBrowser(ClosingBrowser):
    def __init__(self, code, implementation, order):
        super().__init__(code, order=order)
        self.implementation = implementation
        self.actual_send_error = None

    async def send_text(self, value):
        self.send_failed.set()
        try:
            if self.implementation == "starlette":
                socket = WebSocket({"type": "websocket"}, None, None)
                socket.application_state = WebSocketState.DISCONNECTED
                await socket.send_text(value)
            elif self.implementation == "uvicorn":
                protocol = object.__new__(WebSocketProtocol)
                protocol.handshake_started_event = asyncio.Event()
                protocol.handshake_started_event.set()
                protocol.closed_event = asyncio.Event()
                protocol.closed_event.set()
                protocol.initial_response = None
                await protocol.asgi_send({"type": "websocket.send", "text": value})
        except RuntimeError as error:
            self.actual_send_error = error
            raise
        raise AssertionError("actual closed ASGI state did not fail its send")

    send_bytes = send_text


@pytest.mark.parametrize("role", ["bridge", "portable"])
@pytest.mark.parametrize("implementation", ["starlette", "uvicorn"])
@pytest.mark.parametrize("code,order", [(4001, "simultaneous"), (4001, "send-first"), (1000, "send-first")])
def test_actual_asgi_closed_send_preserves_only_observed_browser_close(role, implementation, code, order):
    async def run():
        browser = ASGIClosingBrowser(code, implementation, order)
        if role == "bridge":
            tunnel = Tunnel({"session_id": SID, "deadline_at": time.time() + 60,
                             "startup_timeout_s": 30}, "unused")
            tunnel.state = "ready"
            tunnel.ready.set()
            frames = []

            async def send(raw):
                frame = json.loads(raw)
                frames.append(frame)
                if frame["type"] == "viewer.attach":
                    await tunnel.viewer.put({"type": "viewer.attached"})
                    await tunnel.viewer.put({"type": "viewer.data", "binary": False, "data": "late-frame"})

            tunnel.upstream = SimpleNamespace(send=send)
            await tunnel.attach(browser, FIELDS)
            assert frames[-1]["close_code"] == code
            assert tunnel.viewer_attached() is (code == 4001)
            assert not tunnel.peer_lock.locked()
        else:
            process = SimpleNamespace(active_connection=False, state="signaling")
            peers = []

            def connect(url, **kwargs):
                peer = Echo(kwargs["subprotocols"][0])
                peer.queue.put_nowait("late-frame")
                peers.append(peer)
                return peer

            app = application({"session_id": SID, "browser_origin": "https://app.test",
                               "deadline_at": time.time() + 60, "signal_port": 49100},
                              "x" * 43, process=process, connect_factory=connect)
            route = next(row for row in app.routes if row.path == "/signaling/sign_in")
            await route.endpoint(browser)
            assert process.active_connection is (code == 4001)
            assert peers[0].close_codes == ([4001] if code == 4001 else [])
        assert isinstance(browser.actual_send_error, RuntimeError)

    asyncio.run(run())


def test_portable_unrelated_runtime_error_cannot_authorize_handoff():
    async def run():
        process = SimpleNamespace(active_connection=False, state="signaling")
        peers = []

        def connect(url, **kwargs):
            peer = Echo(kwargs["subprotocols"][0])
            peer.queue.put_nowait("late-frame")
            peers.append(peer)
            return peer

        app = application({"session_id": SID, "browser_origin": "https://app.test",
                           "deadline_at": time.time() + 60, "signal_port": 49100},
                          "x" * 43, process=process, connect_factory=connect)
        route = next(row for row in app.routes if row.path == "/signaling/sign_in")
        with pytest.raises(RuntimeError):
            await route.endpoint(ClosingBrowser(4001, RuntimeError))
        assert not process.active_connection and peers[0].close_codes == []

    asyncio.run(run())
