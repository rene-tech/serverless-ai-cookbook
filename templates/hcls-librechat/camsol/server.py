#!/usr/bin/env python3
"""Loopback-only CamSol connection MCP, owned by the existing workbench runtime."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uvicorn

from web import Connections, Credentials, ProviderBoundary

Mode = Literal["intrinsic", "ph-dependent", "ptm", "structurally-corrected", "combination-design"]


def create_server(connections=None, *, port=8786):
    connections = connections or Connections()

    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield {}
        finally:
            await connections.close()

    server = MCPServer(
        "CamSol connection", version="0.1.0", lifespan=lifespan, log_level="WARNING",
        instructions="Cambridge external web service. Connection and GET-only form inspection only; "
                     "no calculations or scientific inputs. Credentials are supplied privately by MCP Settings; "
                     "never ask for passwords or cookies in chat. A visible form is not a qualified calculation API.",
    )

    async def call(ctx, action, mode="intrinsic"):
        try:
            credentials = Credentials.from_headers(ctx.request_context.request.headers)
            async with asyncio.timeout(60):
                return await connections.call(action, credentials, mode)
        except TimeoutError:
            return {"status": "provider_timeout", "connected": None,
                    "scientific_data_sent": False, "submission_available": False}
        except ProviderBoundary as error:
            return {"status": str(error), "scientific_data_sent": False, "submission_available": False}
        except Exception:
            # Provider bodies/URLs/headers may contain credentials. Never relay a raw exception.
            return {"status": "connector_error", "scientific_data_sent": False, "submission_available": False}

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                             idempotentHint=False, openWorldHint=True))
    async def connect_camsol(ctx: Context) -> dict:
        """Explicitly sign in to Cambridge using this user's protected MCP Settings. No science is submitted."""
        return await call(ctx, "connect")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def camsol_connection_status(ctx: Context) -> dict:
        """GET-only check of the current Cambridge session; never logs in or retries a failed login."""
        return await call(ctx, "status")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def inspect_camsol_mode(mode: Mode, ctx: Context) -> dict:
        """Inspect actual authenticated CamSol form names/types using GET only. Never submit or guess a calculation."""
        return await call(ctx, "inspect", mode)

    app = server.streamable_http_app(host="127.0.0.1", stateless_http=True, json_response=True)

    class PrivateLoopback(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # The Node MCP manager calls us; browsers and public proxying cannot.
            if (request.headers.get("host") != f"127.0.0.1:{port}"
                    or request.headers.get("origin") is not None
                    or request.client is None or request.client.host != "127.0.0.1"):
                return JSONResponse({"error": "private_connection_only"}, status_code=403)
            try:
                Credentials.from_headers(request.headers)
            except ProviderBoundary:
                return JSONResponse({"error": "connection_settings_required"}, status_code=403)
            return await call_next(request)

    app.add_middleware(PrivateLoopback)
    return server, app


def process_start(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] in ("Z", "X") else fields[19]
    except (OSError, IndexError):
        return None


async def serve(port, owner_pid, owner_start):
    # This process is an auxiliary service, never a second workbench supervisor.
    if process_start(owner_pid) != owner_start:
        raise SystemExit("Workbench owner changed; connector was not started.")
    _, app = create_server(port=port)
    runtime = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                            access_log=False, log_level="warning"))

    async def stop_with_owner():
        while not runtime.should_exit:
            await asyncio.sleep(2)
            if process_start(owner_pid) != owner_start:
                runtime.should_exit = True

    watcher = asyncio.create_task(stop_with_owner())
    try:
        await runtime.serve()
    finally:
        watcher.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8786)
    parser.add_argument("--owner-pid", type=int, required=True)
    parser.add_argument("--owner-start", required=True)
    args = parser.parse_args()
    # HTTP request logging is deliberately disabled: no cookies or credentials.
    logging.getLogger("httpx").disabled = True
    logging.getLogger("httpcore").disabled = True
    asyncio.run(serve(args.port, args.owner_pid, args.owner_start))
