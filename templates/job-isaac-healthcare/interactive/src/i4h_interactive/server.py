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
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket
from websockets.asyncio.client import connect

from .contract import authenticate, turn_credentials
from .process import SessionProcess
from .signaling import kit_signaling_path, parse_signaling_query


class NoRedirectConnect(connect):
    def process_redirect(self, exc):
        return exc


def application(config, token, *, process=None, connect_factory=NoRedirectConnect):
    process = process or SessionProcess(config)

    def authorized(request, *, signaling=False):
        if signaling:
            parse_signaling_query(request.query_params.multi_items(), config["session_id"])
        elif request.query_params:
            raise PermissionError(
                "credentials and controls do not belong in query strings"
            )
        authenticate(request.headers, config, token)
        if time.time() >= config["deadline_at"]:
            raise PermissionError("native session deadline has elapsed")

    async def health(request: Request):
        try:
            authorized(request)
        except PermissionError:
            return JSONResponse(
                {"error": "session_authorization_required"}, status_code=403
            )
        return JSONResponse(process.status(), headers={"Cache-Control": "no-store"})

    async def stop(request: Request):
        try:
            authorized(request)
        except PermissionError:
            return JSONResponse(
                {"error": "session_authorization_required"}, status_code=403
            )
        await process.stop("owner_stop")
        # This is a process witness only. The native lease owner releases after
        # independently observing cleanup; this endpoint grants no release.
        return JSONResponse(process.status(), headers={"Cache-Control": "no-store"})

    async def descriptor(request: Request):
        try:
            authorized(request)
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
        if process.active_connection or process.state != "signaling":
            await socket.close(code=1013)
            return
        process.active_connection = True
        try:
            # Fixed loopback target, no redirect, URL input, arbitrary path or
            # credential forwarding to Kit. Video remains real WebRTC media.
            async with connect_factory(
                f"ws://127.0.0.1:{config['signal_port']}" + kit_signaling_path(handshake, config["session_id"]),
                subprotocols=protocols,
                proxy=None,
                max_size=1024 * 1024,
                max_queue=2,
                open_timeout=10,
            ) as upstream:
                await socket.accept(subprotocol=upstream.subprotocol)

                async def browser_to_kit():
                    while True:
                        event = await socket.receive()
                        if event["type"] == "websocket.disconnect":
                            return
                        await upstream.send(
                            event.get("bytes")
                            if event.get("bytes") is not None
                            else event["text"]
                        )

                async def kit_to_browser():
                    async for data in upstream:
                        await (
                            socket.send_bytes(data)
                            if isinstance(data, bytes)
                            else socket.send_text(data)
                        )

                tasks = [
                    asyncio.create_task(browser_to_kit()),
                    asyncio.create_task(kit_to_browser()),
                ]
                try:
                    done, _ = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            process.active_connection = False
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
