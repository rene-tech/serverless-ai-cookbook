"""Authenticated signaling proxy and process control for one isolated session."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect

from .contract import authenticate, turn_credentials
from .process import SessionProcess
from .signaling import (
    HANDOFF_CLOSE_CODE,
    SignalingPeer,
    kit_signaling_path,
    parse_signaling_query,
)


class NoRedirectConnect(connect):
    def process_redirect(self, exc):
        return exc


def application(config, token, *, process=None, connect_factory=NoRedirectConnect):
    process = process or SessionProcess(config)
    peer_lock = asyncio.Lock()
    peer = SignalingPeer(config["session_id"], config["deadline_at"],
                         config.get("startup_timeout_seconds", config["deadline_at"] - time.time()))

    def authorized(request, *, signaling=False, terminal_read=False):
        if signaling:
            parse_signaling_query(request.query_params.multi_items(), config["session_id"])
        elif request.query_params:
            raise PermissionError(
                "credentials and controls do not belong in query strings"
            )
        authenticate(request.headers, config, token)
        if not terminal_read and time.time() >= config["deadline_at"]:
            raise PermissionError("native session deadline has elapsed")

    async def health(request: Request):
        try:
            authorized(request)
        except PermissionError:
            return JSONResponse(
                {"error": "session_authorization_required"}, status_code=403
            )
        process.active_connection = peer.attached
        return JSONResponse(process.status(), headers={"Cache-Control": "no-store"})

    async def stop(request: Request):
        try:
            authorized(request)
        except PermissionError:
            return JSONResponse(
                {"error": "session_authorization_required"}, status_code=403
            )
        await process.stop("owner_stop")
        peer.clear()
        process.active_connection = False
        # This is a process witness only. The native lease owner releases after
        # independently observing cleanup; this endpoint grants no release.
        return JSONResponse(process.status(), headers={"Cache-Control": "no-store"})

    async def descriptor(request: Request):
        try:
            authorized(request, terminal_read=True)
        except PermissionError:
            return JSONResponse(
                {"error": "session_authorization_required"}, status_code=403
            )
        ice = {"iceServers": [], "iceTransportPolicy": "all"}
        if config["network_mode"] == "turn-relay":
            secret = Path(config["turn_secret_file"]).read_bytes().strip()
            ice = turn_credentials(
                secret, config["session_id"], config["deadline_at"], config["turn_url"]
            )
        child = getattr(process, "child", None)
        terminal = (process.state in {"stopping", "stopped", "failed", "cleanup_unknown"}
                    or time.time() >= config["deadline_at"]
                    or (child is not None and child.returncode is not None))
        return JSONResponse(
            {
                "mode": "portable",
                "session_id": config["session_id"],
                "signaling_path": "/signaling",
                "ice_servers": ice["iceServers"],
                "ice_transport_policy": ice["iceTransportPolicy"],
                "media_host": config["media_host"],
                "media_port": config["media_port"],
                "startup_timeout_s": config["startup_timeout_seconds"],
                "startup_ready": process.state == "signaling" and not terminal,
                "startup_readiness_source": "pending" if process.state in {"created", "starting"} else "workflow_started" if config.get("startup_readiness_file") else "signaling_socket",
                "terminal": terminal,
                "deadline_at": config["deadline_at"],
            },
            headers={"Cache-Control": "no-store"},
        )

    async def viewer(_):
        return FileResponse(
            Path(config["viewer_dist"]) / "index.html",
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    async def asset(request):
        root = Path(config["viewer_dist"]).resolve() / "assets"
        path = (root / request.path_params["name"]).resolve()
        if path.parent != root or not path.is_file():
            return JSONResponse({"error": "not_found"}, status_code=404)
        return FileResponse(path)

    async def signaling(socket: WebSocket):
        try:
            authorized(socket, signaling=True)
            handshake = parse_signaling_query(socket.query_params.multi_items(), config["session_id"])
            protocols = authenticate(socket.headers, config, token)
        except PermissionError:
            await socket.close(code=1008)
            return
        reconnect = handshake.get("reconnect") == "1"
        if process.state != "signaling" or (peer_lock.locked() and not (reconnect and peer.matches(handshake))):
            await socket.close(code=1013)
            return
        try:
            async with asyncio.timeout(max(0, min(peer.startup_timeout_s, config["deadline_at"] - time.time()))):
                await peer_lock.acquire()
        except TimeoutError:
            await socket.close(code=1013)
            return
        close_code = 1000
        begun = False
        try:
            try:
                peer.begin(handshake)
            except PermissionError:
                await socket.close(code=1008)
                return
            begun = True
            process.active_connection = True
            # Fixed loopback target, no redirect, URL input, arbitrary path or
            # credential forwarding to Kit. Video remains real WebRTC media.
            async with connect_factory(
                f"ws://127.0.0.1:{config['signal_port']}" + kit_signaling_path(handshake, config["session_id"]),
                subprotocols=protocols,
                proxy=None,
                # Browser SDK semantics on the fixed Kit loopback only;
                # the existing session deadline still bounds both pumps.
                ping_interval=None,
                max_size=1024 * 1024,
                max_queue=2,
                open_timeout=10,
            ) as upstream:
                peer.connected()
                await socket.accept(subprotocol=upstream.subprotocol)

                async def browser_to_kit():
                    nonlocal close_code
                    while True:
                        event = await socket.receive()
                        if event["type"] == "websocket.disconnect":
                            if event.get("code") == HANDOFF_CLOSE_CODE:
                                close_code = HANDOFF_CLOSE_CODE
                            return
                        await upstream.send(
                            event.get("bytes")
                            if event.get("bytes") is not None
                            else event["text"]
                        )

                async def kit_to_browser():
                    downstream_disconnected = False
                    async for data in upstream:
                        if downstream_disconnected:
                            continue
                        try:
                            await (
                                socket.send_bytes(data)
                                if isinstance(data, bytes)
                                else socket.send_text(data)
                            )
                        except (WebSocketDisconnect, RuntimeError) as error:
                            if not isinstance(error, WebSocketDisconnect) and str(error) not in {
                                'Cannot call "send" once a close message has been sent.',
                                "Unexpected ASGI message 'websocket.send', after sending 'websocket.close' or response already completed.",
                            }:
                                raise
                            # A downstream send can notice the same browser
                            # close first through either ASGI closed-send state.
                            # Keep watching Kit until the actual
                            # inbound close or unchanged session deadline.
                            downstream_disconnected = True

                tasks = [
                    asyncio.create_task(browser_to_kit()),
                    asyncio.create_task(kit_to_browser()),
                ]
                try:
                    done, _ = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED,
                        timeout=max(0, config["deadline_at"] - time.time()),
                    )
                    if not done:
                        raise TimeoutError("session deadline reached during viewer close")
                    if tasks[1] in done:
                        # An independently completed Kit reader is a genuine
                        # transport end, not the browser's handoff authority.
                        close_code = 1000
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                if close_code == HANDOFF_CLOSE_CODE:
                    # Join the reader before private4001 makes it raise. Only
                    # the actual browser close selected this handoff path.
                    await upstream.close(code=HANDOFF_CLOSE_CODE)
        except BaseException:
            close_code = 1000
            raise
        finally:
            if begun:
                peer.closed(close_code)
            process.active_connection = peer.attached
            peer_lock.release()
            # A new authenticated viewer reuses this same process/session.
            # Explicit stop or the existing native deadline ends the process.

    @contextlib.asynccontextmanager
    async def lifespan(_):
        await process.start()
        monitor = asyncio.create_task(process.monitor())
        try:
            await process.wait_signaling()
            yield
        finally:
            await process.stop("service_shutdown")
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)

    routes = [
        Route("/health", health),
        Route("/stop", stop, methods=["POST"]),
        Route("/descriptor", descriptor),
        WebSocketRoute("/signaling/sign_in", signaling),
    ]
    if config.get("viewer_dist"):
        routes.extend([Route("/", viewer), Route("/assets/{name}", asset)])
    return Starlette(routes=routes, lifespan=lifespan)


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    token = args.token_file.read_text().strip()
    # TLS/auth ingress is separately reviewed; the raw listener never binds
    # every interface. Reverse proxy shares this host/network namespace.
    uvicorn.run(
        application(config, token),
        host="127.0.0.1",
        port=config["proxy_port"],
        access_log=False,
    )


if __name__ == "__main__":
    main()
