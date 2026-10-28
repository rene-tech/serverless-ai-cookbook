"""Actual proxy pumps: an authenticated close races a downstream send failure."""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers, QueryParams
from starlette.websockets import WebSocketDisconnect

from i4h_interactive.bridge import Tunnel
from i4h_interactive.server import application
from i4h_interactive.signaling import encode_signaling
from test_sdk_signaling import Echo, FIELDS, SID


class ClosingBrowser:
    def __init__(self, code, failure=WebSocketDisconnect, order="simultaneous"):
        self.code = code
        self.failure = failure
        self.order = order
        self.send_failed = asyncio.Event()
        self.headers = Headers({
            "origin": "https://app.test",
            "sec-websocket-protocol": "x-nv-sessionid." + SID + ", Authorization.Bearer." + "x" * 43,
        })
        self.query_params = QueryParams(encode_signaling(FIELDS, SID))
        self.accepted = False

    async def accept(self, **kwargs):
        self.accepted = True

    async def receive(self):
        if self.order == "missing-close":
            await asyncio.Event().wait()
        if self.order == "send-first":
            await self.send_failed.wait()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        return {"type": "websocket.disconnect", "code": self.code}

    async def send_text(self, value):
        self.send_failed.set()
        raise self.failure(1006)

    send_bytes = send_text

    async def close(self, **kwargs):
        pass


@pytest.mark.parametrize("code", [4001, 1000])
@pytest.mark.parametrize("order", ["simultaneous", "send-first"])
def test_bridge_simultaneous_browser_close_and_send_disconnect(code, order):
    async def run():
        tunnel = Tunnel({"session_id": SID, "deadline_at": time.time() + 60,
                         "startup_timeout_s": 30}, "unused")
        tunnel.state = "ready"
        tunnel.ready.set()
        frames = []

        async def send(raw):
            value = json.loads(raw)
            frames.append(value)
            if value["type"] == "viewer.attach":
                await tunnel.viewer.put({"type": "viewer.attached"})
                await tunnel.viewer.put({"type": "viewer.data", "binary": False, "data": "late-data"})

        tunnel.upstream = SimpleNamespace(send=send)
        browser = ClosingBrowser(code, order=order)
        await tunnel.attach(browser, FIELDS)
        assert browser.accepted
        assert frames[-1]["type"] == "viewer.detach"
        assert frames[-1]["close_code"] == code
        assert tunnel.viewer_attached() is (code == 4001)
        assert not tunnel.peer_lock.locked()

    asyncio.run(run())


def test_bridge_real_native_failure_overrides_simultaneous_4001():
    async def run():
        tunnel = Tunnel({"session_id": SID, "deadline_at": time.time() + 60,
                         "startup_timeout_s": 30}, "unused")
        tunnel.state = "ready"
        tunnel.ready.set()
        frames = []

        async def send(raw):
            value = json.loads(raw)
            frames.append(value)
            if value["type"] == "viewer.attach":
                await tunnel.viewer.put({"type": "viewer.attached"})
                await tunnel.viewer.put({"type": "viewer.error", "code": "kit_viewer_closed"})

        tunnel.upstream = SimpleNamespace(send=send)
        await tunnel.attach(ClosingBrowser(4001), FIELDS)
        assert not tunnel.viewer_attached()
        assert frames[-1]["close_code"] == 1000

    asyncio.run(run())


@pytest.mark.parametrize("code", [4001, 1000])
@pytest.mark.parametrize("order", ["simultaneous", "send-first"])
def test_portable_simultaneous_browser_close_and_send_disconnect(code, order):
    async def run():
        config = {"session_id": SID, "browser_origin": "https://app.test",
                  "deadline_at": time.time() + 60, "signal_port": 49100}
        process = SimpleNamespace(active_connection=False, state="signaling")
        peers = []

        def connect(url, **kwargs):
            peer = Echo(kwargs["subprotocols"][0])
            peer.queue.put_nowait("late-data")
            peers.append(peer)
            return peer

        app = application(config, "x" * 43, process=process, connect_factory=connect)
        route = next(row for row in app.routes if row.path == "/signaling/sign_in")
        browser = ClosingBrowser(code, order=order)
        await route.endpoint(browser)
        assert browser.accepted and len(peers) == 1
        assert process.active_connection is (code == 4001)
        assert peers[0].close_codes == ([4001] if code == 4001 else [])

    asyncio.run(run())


def test_bridge_unrelated_send_failure_does_not_authorize_handoff():
    async def run():
        tunnel = Tunnel({"session_id": SID, "deadline_at": time.time() + 60,
                         "startup_timeout_s": 30}, "unused")
        tunnel.state = "ready"
        tunnel.ready.set()

        async def send(raw):
            if json.loads(raw)["type"] == "viewer.attach":
                await tunnel.viewer.put({"type": "viewer.attached"})
                await tunnel.viewer.put({"type": "viewer.data", "binary": False, "data": "late-data"})

        tunnel.upstream = SimpleNamespace(send=send)
        with pytest.raises(RuntimeError):
            await tunnel.attach(ClosingBrowser(4001, RuntimeError), FIELDS)
        assert not tunnel.viewer_attached()

    asyncio.run(run())


@pytest.mark.parametrize("role", ["bridge", "portable"])
def test_downstream_disconnect_without_observed_close_expires_at_deadline(role):
    async def run():
        deadline = time.time() + 0.05
        browser = ClosingBrowser(4001, order="missing-close")
        if role == "bridge":
            tunnel = Tunnel({"session_id": SID, "deadline_at": deadline,
                             "startup_timeout_s": 30}, "unused")
            tunnel.state = "ready"
            tunnel.ready.set()

            async def send(raw):
                if json.loads(raw)["type"] == "viewer.attach":
                    await tunnel.viewer.put({"type": "viewer.attached"})
                    await tunnel.viewer.put({"type": "viewer.data", "binary": False, "data": "late-data"})

            tunnel.upstream = SimpleNamespace(send=send)
            with pytest.raises(TimeoutError):
                await tunnel.attach(browser, FIELDS)
            assert not tunnel.viewer_attached() and not tunnel.peer_lock.locked()
        else:
            process = SimpleNamespace(active_connection=False, state="signaling")

            def connect(url, **kwargs):
                peer = Echo(kwargs["subprotocols"][0])
                peer.queue.put_nowait("late-data")
                return peer

            app = application({"session_id": SID, "browser_origin": "https://app.test",
                               "deadline_at": deadline, "signal_port": 49100},
                              "x" * 43, process=process, connect_factory=connect)
            route = next(row for row in app.routes if row.path == "/signaling/sign_in")
            with pytest.raises(TimeoutError):
                await route.endpoint(browser)
            assert not process.active_connection

    asyncio.run(run())
