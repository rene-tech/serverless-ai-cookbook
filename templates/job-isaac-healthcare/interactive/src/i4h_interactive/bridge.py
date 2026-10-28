"""Persistent native WSS transport with replaceable browser peers.

This CPU component accepts only an already-admitted native ID/claim. It never
admits, retries, allocates GPUs, extends deadlines or releases native resources.
One replica owns each connection; restart ends that connection explicitly.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import re
import secrets
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect

from .contract import SESSION
from .signaling import (
    HANDOFF_CLOSE_CODE,
    SIGNALING_HEADER,
    SignalingPeer,
    parse_signaling_header,
    validate_signaling,
)


class NoRedirectConnect(connect):
    def process_redirect(self, exc):
        return exc


class Tunnel:
    def __init__(self, value, endpoint, *, connect_factory=NoRedirectConnect):
        self.value, self.endpoint, self.connect_factory = (
            value,
            endpoint,
            connect_factory,
        )
        self.state, self.upstream, self.viewer = "connecting", None, None
        self.ready = asyncio.Event()
        self.peer_lock = asyncio.Lock()
        self.peer = SignalingPeer(value["session_id"], value["deadline_at"], value["startup_timeout_s"])
        self.error = None
        self.execution = None
        self.peer_id = None
        self.media = None
        self.updated_at = time.time()
        self.consumed = set()
        self.task = None

    def record_execution(self, frame):
        start = {k: v for k, v in self.value["start"].items() if k != "start_signature"}
        digest = hashlib.sha256(json.dumps(start, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        if (
            not isinstance(frame, dict)
            or set(frame) != {"type", "session_id", "start_sha256", "image", "runtime_revision",
                              "phase", "outcome", "code", "signaling_ready", "exit_code", "cleanup", "message", "log_tail"}
            or frame.get("type") != "isaac.session.execution"
            or frame.get("session_id") != self.value["session_id"]
            or frame.get("start_sha256") != digest
            or frame.get("image") != start["image"]
            or frame.get("runtime_revision") != start["runtime_revision"]
            or self.execution is not None
        ):
            raise ValueError("native execution evidence identity differs")
        # App validates the bounded outcome grammar and sanitizes diagnostics.
        # This private observation never ends or releases the Native session.
        self.execution = frame
        self.updated_at = time.time()

    async def run(self):
        try:
            async with self.connect_factory(
                self.endpoint,
                additional_headers={"x-serverless2-session-claim": self.value["claim"]},
                subprotocols=["x-nv-sessionid." + self.value["session_id"]],
                ssl=ssl.create_default_context(),
                proxy=None,
                open_timeout=self.value["startup_timeout_s"],
                max_size=1024 * 1024,
                max_queue=2,
                close_timeout=5,
            ) as upstream:
                self.upstream = upstream
                await upstream.send(json.dumps(self.value["start"]))
                raw = await asyncio.wait_for(
                    upstream.recv(), self.value["startup_timeout_s"]
                )
                ready = json.loads(raw)
                if ready.get("type") == "isaac.session.execution":
                    self.record_execution(ready)
                    return
                if (
                    ready.get("type") != "isaac.session.signaling_ready"
                    or ready.get("session_id") != self.value["session_id"]
                ):
                    raise ValueError("native signaling readiness identity differs")
                self.state = "ready"
                self.updated_at = time.time()
                self.ready.set()
                async with asyncio.timeout(
                    max(0.01, self.value["deadline_at"] - time.time())
                ):
                    async for raw in upstream:
                        frame = json.loads(raw)
                        if frame.get("type") == "isaac.session.execution":
                            self.record_execution(frame)
                            return
                        if frame.get("type") not in {
                            "viewer.attached",
                            "viewer.data",
                            "viewer.error",
                            "session.keepalive",
                        }:
                            raise ValueError("invalid native transport envelope")
                        if (
                            self.viewer is not None
                            and frame.get("peer_id") == self.peer_id
                        ):
                            await self.viewer.put(frame)
        except asyncio.CancelledError:
            self.error = "bridge_shutdown"
            raise
        except Exception:
            self.error = "native_transport_ended"
        finally:
            self.state = "ended"
            self.ready.set()
            if self.viewer is not None:
                # A full queue cannot block cleanup of the native socket.
                with contextlib.suppress(asyncio.QueueFull):
                    self.viewer.put_nowait(
                        {"type": "viewer.error", "code": "native_transport_ended"}
                    )
            self.upstream = None
            self.peer.clear()
            self.media = None
            # Drop the single-use claim after the connection lifetime.
            self.value.pop("claim", None)

    def viewer_attached(self):
        attached = self.peer.attached
        if not attached:
            self.media = None
        return attached

    async def attach(self, socket, signaling):
        signaling = validate_signaling(signaling, self.value["session_id"])
        reconnect = signaling.get("reconnect") == "1"
        # The SDK worker may connect before the first socket's 4001 has reached
        # us. Only that exact logical peer can wait for its transport to drain.
        if self.peer_lock.locked() and not (reconnect and self.peer.matches(signaling)):
            await socket.close(code=1013)
            return
        remaining = min(self.value["startup_timeout_s"], self.value["deadline_at"] - time.time())
        try:
            async with asyncio.timeout(max(0, remaining)):
                await self.peer_lock.acquire()
        except TimeoutError:
            await socket.close(code=1013)
            return
        try:
            await self.ready.wait()
            if self.state != "ready":
                await socket.close(code=1011)
                return
            try:
                self.peer.begin(signaling)
            except PermissionError:
                await socket.close(code=1008)
                return
            queue = asyncio.Queue(maxsize=2)
            self.viewer = queue
            if not reconnect:
                self.peer_id = secrets.token_hex(16)
                self.media = None
            pumps = []
            close_code = 1000
            try:
                await self.upstream.send(
                    json.dumps({"type": "viewer.attach", "peer_id": self.peer_id,
                                "signaling": signaling})
                )
                ack = await asyncio.wait_for(queue.get(), remaining)
                if ack.get("type") != "viewer.attached":
                    raise ValueError("viewer attachment failed")
                self.peer.connected()
                await socket.accept(subprotocol="x-nv-sessionid." + self.value["session_id"])

                async def inbound():
                    nonlocal close_code
                    while True:
                        event = await socket.receive()
                        if event["type"] == "websocket.disconnect":
                            if event.get("code") == HANDOFF_CLOSE_CODE:
                                close_code = HANDOFF_CLOSE_CODE
                            return
                        binary = event.get("bytes") is not None
                        data = base64.b64encode(event["bytes"]).decode() if binary else event["text"]
                        await self.upstream.send(json.dumps({
                            "type": "viewer.data", "peer_id": self.peer_id,
                            "binary": binary, "data": data,
                        }))

                async def outbound():
                    downstream_disconnected = False
                    while True:
                        frame = await queue.get()
                        if frame.get("type") == "viewer.error":
                            await socket.close(code=1011)
                            return
                        if frame.get("type") != "viewer.data":
                            continue
                        if downstream_disconnected:
                            continue
                        try:
                            await (socket.send_bytes(base64.b64decode(frame["data"], validate=True))
                                   if frame["binary"] else socket.send_text(frame["data"]))
                        except WebSocketDisconnect:
                            # The browser's close can race an already queued
                            # Native frame. Keep watching Native while inbound
                            # reads the actual close code; never infer4001.
                            downstream_disconnected = True

                pumps = [asyncio.create_task(inbound()), asyncio.create_task(outbound())]
                done, _ = await asyncio.wait(
                    pumps, return_when=asyncio.FIRST_COMPLETED,
                    timeout=max(0, self.value["deadline_at"] - time.time()),
                )
                if not done:
                    raise TimeoutError("session deadline reached during viewer close")
                # A Kit failure concurrent with a browser close is a failed
                # transport, never authority to retain a handoff.
                if pumps[1] in done:
                    close_code = 1000
                for task in done:
                    task.result()
            except BaseException:
                close_code = 1000
                raise
            finally:
                for task in pumps:
                    task.cancel()
                await asyncio.gather(*pumps, return_exceptions=True)
                self.viewer = None
                self.peer.closed(close_code)
                if not self.peer.attached:
                    self.media = None
                if self.upstream is not None:
                    await self.upstream.send(json.dumps({
                        "type": "viewer.detach", "peer_id": self.peer_id,
                        "close_code": close_code,
                    }))
                # The logical peer survives only the SDK's observed 4001
                # handoff. Neither transport ever restarts Kit or its lease.
        finally:
            self.peer_lock.release()


def application(
    *,
    service_token,
    targets,
    connect_factory=NoRedirectConnect,
):
    if not isinstance(targets, list) or not targets:
        raise ValueError("approved Native target mappings are required")
    mappings = []
    identities = set()
    for row in targets:
        if not isinstance(row, dict) or set(row) != {
            "region",
            "target",
            "native_endpoint",
            "runtime_revision",
        }:
            raise ValueError("invalid operator target mapping")
        target = row["target"]
        if not isinstance(target, dict) or set(target) != {
            "cluster",
            "variant",
            "id",
            "image",
            "gpu_class",
        }:
            raise ValueError("exact Native target identity is required")
        if any(
            not isinstance(row[name], str) or not row[name]
            for name in ("region", "runtime_revision")
        ):
            raise ValueError("target region/runtime are required")
        if any(
            not isinstance(target[name], str) or not target[name]
            for name in ("cluster", "id", "image")
        ):
            raise ValueError("invalid Native target identity")
        if any(
            target[name] is not None
            and (not isinstance(target[name], str) or not target[name])
            for name in ("variant", "gpu_class")
        ):
            raise ValueError("invalid Native target variant/class")
        if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", target["image"]):
            raise ValueError("immutable target image required")
        u = urlsplit(row["native_endpoint"])
        if (
            u.scheme != "wss"
            or not u.hostname
            or not u.path
            or u.query
            or u.fragment
            or u.username
        ):
            raise ValueError("exact operator-bound native WSS endpoint required")
        identity = (row["region"], target["cluster"], target["variant"], target["id"])
        if identity in identities:
            raise ValueError("duplicate Native target mapping")
        identities.add(identity)
        mappings.append(json.loads(json.dumps(row)))
    if len(service_token) < 32:
        raise ValueError("operator service credential required")
    tunnels = {}

    def auth(request):
        if request.query_params or not hmac.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + service_token
        ):
            raise PermissionError("private transport caller required")

    async def create(request):
        try:
            auth(request)
        except PermissionError:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        raw = await request.body()
        if len(raw) > 1024 * 1024:
            return JSONResponse({"error": "invalid_start"}, status_code=400)
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"error": "invalid_start"}, status_code=400)
        if not isinstance(value, dict) or not isinstance(value.get("start"), dict):
            return JSONResponse({"error": "invalid_start"}, status_code=400)
        sid = value.get("session_id", "")
        start = value.get("start", {})
        selected = [
            row
            for row in mappings
            if row["region"] == start.get("region")
            and row["target"] == start.get("target")
        ]
        if (
            set(value)
            != {"session_id", "claim", "deadline_at", "startup_timeout_s", "start"}
            or set(start)
            != {
                "type",
                "session_id",
                "image",
                "runtime_revision",
                "region",
                "target",
                "deadline_at",
                "start",
                "display",
                "start_signature",
            }
            or not isinstance(sid, str)
            or not SESSION.fullmatch(sid)
            or len(selected) != 1
            or start.get("type") != "isaac.session.start"
            or start.get("session_id") != sid
            or start.get("image") != selected[0]["target"]["image"]
            or start.get("runtime_revision") != selected[0]["runtime_revision"]
            or start.get("deadline_at") != value.get("deadline_at")
        ):
            return JSONResponse({"error": "identity_mismatch"}, status_code=409)
        if (
            value.get("deadline_at", 0) <= time.time()
            or value.get("startup_timeout_s", 0) <= 0
        ):
            return JSONResponse(
                {"error": "expired_or_unbounded_session"}, status_code=409
            )
        # A duplicate never sends another claim or creates another native socket.
        digest = hashlib.sha256(raw).hexdigest()
        if sid in tunnels:
            prior = tunnels[sid]
            return JSONResponse(
                {
                    "session_id": sid,
                    "state": prior.state,
                    "same_request": prior.digest == digest,
                },
                status_code=200 if prior.digest == digest else 409,
            )
        tunnel = Tunnel(
            value, selected[0]["native_endpoint"], connect_factory=connect_factory
        )
        tunnel.digest = digest
        tunnels[sid] = tunnel
        tunnel.task = asyncio.create_task(tunnel.run())
        return JSONResponse({"session_id": sid, "state": "connecting"}, status_code=202)

    async def status(request):
        try:
            auth(request)
        except PermissionError:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        item = tunnels.get(request.path_params["sid"])
        if item is None:
            return JSONResponse({"error": "transport_not_found"}, status_code=404)
        return JSONResponse(
            {
                "session_id": request.path_params["sid"],
                "state": item.state,
                "viewer_attached": item.viewer_attached(),
                "media_ready": True if item.media is not None else None,
                "media_evidence": item.media,
                "observed_at": time.time(),
                "execution": item.execution,
                "error": item.error,
            }
        )

    async def media(request):
        try:
            auth(request)
        except PermissionError:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        item = tunnels.get(request.path_params["sid"])
        if item is None or not item.viewer_attached():
            return JSONResponse({"error": "viewer_not_attached"}, status_code=409)
        body = await request.json()
        if (
            not isinstance(body, dict)
            or set(body) != {"width", "height"}
            or any(type(body[x]) is not int or not 0 < body[x] <= 4096 for x in body)
        ):
            return JSONResponse({"error": "invalid_frame_measurement"}, status_code=400)
        item.media = {
            **body,
            "reported_at": time.time(),
            "source": "owner-browser-decoded-frame",
        }
        return JSONResponse({"recorded": True})

    async def attach(socket):
        try:
            auth(socket)
        except PermissionError:
            await socket.close(code=1008)
            return
        item = tunnels.get(socket.path_params["sid"])
        if item is None:
            await socket.close(code=1008)
            return
        nonce = socket.headers.get("x-isaac-attach-nonce", "")
        if not SESSION.fullmatch(nonce) or nonce in item.consumed:
            await socket.close(code=1008)
            return
        try:
            headers = socket.headers.getlist(SIGNALING_HEADER)
            if len(headers) != 1:
                raise PermissionError("exactly one private signaling header required")
            signaling = parse_signaling_header(headers[0], item.value["session_id"])
        except PermissionError:
            await socket.close(code=1008)
            return
        # A customer cannot reset this guard by deleting a bucket receipt. Its
        # lifetime is exactly this native connection; restart creates no tunnel.
        item.consumed.add(nonce)
        await item.attach(socket, signaling)

    @contextlib.asynccontextmanager
    async def lifespan(_):
        yield
        for tunnel in tunnels.values():
            tunnel.task.cancel()
        await asyncio.gather(
            *(t.task for t in tunnels.values()), return_exceptions=True
        )

    return Starlette(
        routes=[
            Route("/sessions", create, methods=["POST"]),
            Route("/sessions/{sid}", status),
            Route("/sessions/{sid}/media", media, methods=["POST"]),
            WebSocketRoute("/sessions/{sid}/attach", attach),
        ],
        lifespan=lifespan,
    )


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--tls-cert", required=True)
    parser.add_argument("--tls-key", required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    app = application(
        service_token=args.token_file.read_text().strip(),
        targets=config["targets"],
    )
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config["port"],
        ssl_certfile=args.tls_cert,
        ssl_keyfile=args.tls_key,
        access_log=False,
        log_level="warning",
        ws_max_size=1024 * 1024,
        ws_max_queue=2,
    )


if __name__ == "__main__":
    main()
