"""Native201 session attach/watch/release around an actual Isaac process.

No admission, scheduler, scaling or reconnect logic lives here. The native
authorizer injects a connection ID; the API verifies this Pod's bound service
account before attach. A forged public header cannot attach a different Pod.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .contract import SESSION
from .process import SessionProcess
from .signaling import (
    HANDOFF_CLOSE_CODE,
    SignalingPeer,
    kit_signaling_path,
    validate_signaling,
)


class NoRedirectConnect(connect):
    def process_redirect(self, exc):
        return exc


def _kit_close_diagnostic(peer, error, phase):
    """Bounded private metadata; never log peer-controlled exception text."""
    def code(value):
        return int(value) if isinstance(value, int) and not isinstance(value, bool) and 1000 <= value <= 4999 else None

    def frame(value):
        if value is None:
            return None
        reason = getattr(value, "reason", None)
        known = reason in ("", "keepalive ping timeout")
        return {
            "code": code(getattr(value, "code", None)),
            "reason": reason if known else None,
            "reason_sha256": hashlib.sha256(reason.encode("utf-8", errors="replace")).hexdigest()
            if isinstance(reason, str) and not known else None,
        }

    name = type(error).__name__ if error is not None else None
    return {
        "event": "kit_viewer_transport_ended",
        "phase": phase,
        "exception_type": "".join(c for c in name[:80] if c.isascii() and (c.isalnum() or c == "_")) if name else None,
        "received": frame(getattr(error, "rcvd", None)),
        "sent": frame(getattr(error, "sent", None)),
        "final_close_code": code(getattr(peer, "close_code", None)),
    }


def _log_kit_close(peer, error, phase):
    # Diagnostics must not alter the transport's control flow.
    with contextlib.suppress(Exception):
        logging.getLogger(__name__).warning(
            "Kit viewer transport ended: %s",
            json.dumps(_kit_close_diagnostic(peer, error, phase), sort_keys=True),
        )


def epoch(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


class NativeSessionAPI:
    def __init__(self, origin, token_file, *, http=None):
        u = urlsplit(origin)
        if (
            u.scheme != "https"
            or not u.netloc
            or u.path not in ("", "/")
            or u.query
            or u.fragment
            or u.username
        ):
            raise ValueError("operator-bound native HTTPS origin required")
        self.origin, self.token_file = origin.rstrip("/"), Path(token_file)
        self.http = http or httpx.AsyncClient(timeout=15, follow_redirects=False)

    async def request(self, method, sid, suffix="", body=None):
        if not SESSION.fullmatch(sid):
            raise ValueError("invalid native session identity")
        token = self.token_file.read_text().strip()
        response = await self.http.request(
            method,
            f"{self.origin}/internal/sessions/{sid}{suffix}",
            headers={"Authorization": "Bearer " + token},
            **({"json": body} if body is not None else {}),
        )
        if response.status_code != 200:
            # Do not include URL, headers or a response body in operator errors.
            raise RuntimeError(
                f"native_session_{method.lower()}_{response.status_code}"
            )
        value = response.json()
        if value.get("id") != sid:
            raise ValueError("native response identity differs")
        return value

    async def attach(self, sid, connection, model_id):
        value = await self.request(
            "POST", sid, ":attach", {"connection": connection, "worker_session_id": sid}
        )
        owner = value.get("owner", {})
        if (
            value.get("status") != "attached"
            or value.get("connection") != connection
            or owner.get("model") != model_id
            or not owner.get("tenant")
            or not owner.get("owner")
        ):
            raise ValueError("native attach did not verify this session and owner")
        return value

    async def watch(self, sid, owner):
        value = await self.request("GET", sid)
        if value.get("status") != "attached" or value.get("owner") != owner:
            raise ValueError("native session ownership changed")
        return value

    async def release(self, sid, connection, outcome):
        return await self.request(
            "POST",
            sid,
            ":release",
            {"connection": connection, "outcome": outcome, "gpu_seconds": None},
        )


async def joined(task):
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            pass
    return task.result()


def application(
    api,
    *,
    model_id,
    expected_image,
    runtime_revision,
    start_key,
    prepare_start,
    poll_seconds=2,
    process_factory=SessionProcess,
    connect_factory=NoRedirectConnect,
):
    """prepare_start(start, native_owner, sid, deadline, display) returns config.

    The supplied adapter performs authenticated artifact download and the general
    project preparation. Only after a successful native attach may it run.
    """
    if not 0 < poll_seconds <= 30:
        raise ValueError("explicit native watch interval in (0, 30] required")
    if not isinstance(start_key, bytes) or len(start_key) != 32:
        raise ValueError("model-scoped App start verification key required")
    gate = asyncio.Lock()
    health = {
        "available": True,
        "active": False,
        "media_ready": None,
        "cleanup_unknown": False,
    }

    async def ready(_):
        return JSONResponse(health, status_code=200 if health["available"] else 503)

    async def live(_):
        # Quarantine is a readiness condition, never a liveness restart request
        # that would discard the failed session's retained output.
        return JSONResponse({"alive": True})

    async def stream(socket):
        sid = socket.headers.get("x-serverless2-session", "")
        connection = socket.headers.get("x-serverless2-connection", "")
        if (
            not SESSION.fullmatch(sid)
            or not SESSION.fullmatch(connection)
            or gate.locked()
            or not health["available"]
        ):
            await socket.close(code=1013)
            return
        await gate.acquire()
        health["active"] = True
        process, attached, watcher, finalize = None, False, None, None
        signaling_ready = False
        start_digest, config = None, None
        phase, failure_message = "preparation", ""
        tasks = []
        outcome = "error"
        cancel_preparation = threading.Event()
        try:
            attach_task = asyncio.create_task(api.attach(sid, connection, model_id))
            try:
                native = await asyncio.shield(attach_task)
            except asyncio.CancelledError:
                native = await joined(attach_task)
                attached = True
                raise
            attached = True
            deadline = epoch(native["deadline_at"])
            owner = native["owner"]
            await socket.accept(subprotocol=f"x-nv-sessionid.{sid}")

            async def watch():
                nonlocal outcome
                while True:
                    state = await api.watch(sid, owner)
                    if state.get("cancel_requested") or time.time() >= epoch(
                        state["deadline_at"]
                    ):
                        outcome = "cancelled"
                        raise RuntimeError("native_session_cancelled_or_expired")
                    if (
                        process is not None
                        and process.child is not None
                        and process.child.returncode is not None
                    ):
                        outcome = "done" if process.child.returncode == 0 and signaling_ready else "error"
                        return
                    await asyncio.sleep(poll_seconds)

            watcher = asyncio.create_task(watch())

            async def run():
                nonlocal process, outcome, finalize, signaling_ready, start_digest, phase, config
                raw = await asyncio.wait_for(
                    socket.receive_text(), max(0.01, deadline - time.time())
                )
                if len(raw.encode()) > 1024 * 1024:
                    raise ValueError("session start is too large")
                start = json.loads(raw)
                if (
                    start.get("type"),
                    start.get("session_id"),
                    start.get("image"),
                    start.get("runtime_revision"),
                ) != ("isaac.session.start", sid, expected_image, runtime_revision):
                    raise ValueError(
                        "session start does not match the installed runtime binding"
                    )
                signature = start.pop("start_signature", "")
                authenticated = json.dumps(
                    start, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
                if (
                    start.get("deadline_at") != deadline
                    or not isinstance(signature, str)
                    or not hmac.compare_digest(
                        signature,
                        hmac.new(start_key, authenticated, hashlib.sha256).hexdigest(),
                    )
                ):
                    raise PermissionError("App session start signature differs")
                start_digest = hashlib.sha256(authenticated).hexdigest()
                # Joining preparation avoids abandoning a download/extraction
                # thread while cancellation releases its native session.
                prep = asyncio.create_task(
                    asyncio.to_thread(
                        prepare_start,
                        start["start"],
                        owner,
                        sid,
                        deadline,
                        start["display"],
                        cancel_preparation,
                    )
                )
                try:
                    config = await asyncio.shield(prep)
                except asyncio.CancelledError:
                    cancel_preparation.set()
                    await joined(prep)
                    raise
                if (
                    config.get("session_id") != sid
                    or config.get("deadline_at") != deadline
                ):
                    raise ValueError(
                        "prepared process escaped its native session bounds"
                    )
                finalize = config.pop("_finalize", None)
                process = process_factory(config)
                current = await api.watch(sid, owner)
                if current.get("cancel_requested") or time.time() >= epoch(
                    current["deadline_at"]
                ):
                    raise RuntimeError("native_session_cancelled_or_expired")
                phase = "initialization"
                launch = asyncio.create_task(process.start())
                try:
                    await asyncio.shield(launch)
                except asyncio.CancelledError:
                    await joined(launch)
                    raise
                await process.wait_signaling()
                signaling_ready = True
                phase = "running"
                await socket.send_json(
                    {
                        "type": "isaac.session.signaling_ready",
                        "session_id": sid,
                        "media_ready": None,
                        "startup_ready": True,
                        "startup_readiness_source": "workflow_started" if config.get("startup_readiness_file") else "signaling_socket",
                        "deadline_at": deadline,
                    }
                )
                kit, forward, peer_id = None, None, None
                peer_state = SignalingPeer(sid, deadline, config.get("startup_timeout_seconds", deadline - time.time()))

                async def detach(close_code=1000):
                    nonlocal kit, forward
                    failure = None
                    if forward is not None:
                        forward.cancel()
                        await asyncio.gather(forward, return_exceptions=True)
                        forward = None
                    if kit is not None:
                        previous, kit = kit, None
                        try:
                            if close_code == HANDOFF_CLOSE_CODE:
                                await previous.close(code=HANDOFF_CLOSE_CODE)
                            else:
                                await previous.close()
                        except (ConnectionClosed, OSError, TimeoutError) as error:
                            _log_kit_close(previous, error, "kit_close")
                            failure, close_code = error, 1000
                    peer_state.closed(close_code)
                    return failure

                async def viewer_failed(error, phase):
                    _log_kit_close(kit, error, phase)
                    await detach()
                    await socket.send_json(
                        {"type": "viewer.error", "peer_id": peer_id,
                         "code": "kit_viewer_closed"}
                    )

                async def outbound(peer, identity):
                    cancelled = False
                    failure, failure_phase = None, "kit_receive"
                    try:
                        async for data in peer:
                            binary = isinstance(data, bytes)
                            failure_phase = "native_forward"
                            await socket.send_json(
                                {
                                    "type": "viewer.data",
                                    "peer_id": identity,
                                    "binary": binary,
                                    "data": base64.b64encode(data).decode()
                                    if binary
                                    else data,
                                }
                            )
                            failure_phase = "kit_receive"
                    except asyncio.CancelledError:
                        cancelled = True
                        raise
                    except Exception as error:
                        failure = error
                        raise
                    finally:
                        # Our own transport handoff/drain cancels this reader.
                        # It is not an independent Kit failure for the next peer.
                        if not cancelled:
                            # Operator logs only; the viewer envelope, lease and
                            # Kit connection/heartbeat policy remain unchanged.
                            _log_kit_close(peer, failure, failure_phase)
                            await socket.send_json(
                                {"type": "viewer.error", "peer_id": identity,
                                 "code": "kit_viewer_closed"}
                            )

                try:
                    while True:
                        raw = await socket.receive_text()
                        if len(raw.encode()) > 1024 * 1024:
                            raise ValueError("oversized native transport frame")
                        frame = json.loads(raw)
                        kind = frame.get("type")
                        if kind == "viewer.attach":
                            if (set(frame) != {"type", "peer_id", "signaling"}
                                    or not SESSION.fullmatch(frame.get("peer_id", ""))):
                                raise ValueError("viewer identity missing")
                            signaling = validate_signaling(frame["signaling"], sid)
                            if kit is not None:
                                await socket.send_json(
                                    {
                                        "type": "viewer.error",
                                        "peer_id": frame["peer_id"],
                                        "code": "viewer_busy",
                                    }
                                )
                                continue
                            reconnect = signaling.get("reconnect") == "1"
                            if reconnect and frame["peer_id"] != peer_id:
                                raise PermissionError("SDK handoff changed its private peer")
                            peer_state.begin(signaling)
                            if not reconnect:
                                peer_id = frame["peer_id"]
                            try:
                                kit = await connect_factory(
                                    f"ws://127.0.0.1:{config['signal_port']}"
                                    + kit_signaling_path(signaling, sid),
                                    subprotocols=[f"x-nv-sessionid.{sid}"],
                                    proxy=None,
                                    # Match the browser SDK's Kit connection: do
                                    # not add a shorter Ping/Pong startup deadline.
                                    # Native watch still enforces cancel/expiry.
                                    ping_interval=None,
                                    max_size=1024 * 1024,
                                    max_queue=2,
                                    open_timeout=10,
                                )
                            except (ConnectionClosed, OSError, TimeoutError) as error:
                                await viewer_failed(error, "kit_connect")
                                continue
                            peer_state.connected()
                            await socket.send_json(
                                {"type": "viewer.attached", "peer_id": peer_id}
                            )
                            forward = asyncio.create_task(outbound(kit, peer_id))
                        elif (
                            kind == "viewer.detach" and frame.get("peer_id") == peer_id
                        ):
                            if set(frame) not in ({"type", "peer_id"}, {"type", "peer_id", "close_code"}):
                                raise ValueError("invalid viewer detach fields")
                            close_code = frame.get("close_code", 1000)
                            if type(close_code) is not int or close_code not in (1000, HANDOFF_CLOSE_CODE):
                                raise ValueError("invalid viewer close code")
                            failed = await detach(close_code)
                            if failed is not None:
                                await socket.send_json(
                                    {"type": "viewer.error", "peer_id": peer_id,
                                     "code": "kit_viewer_closed"}
                                )
                            # Keep the same Kit process and native lease alive.
                        elif (
                            kind == "viewer.data"
                            and peer_id is not None
                            and frame.get("peer_id") == peer_id
                        ):
                            if (set(frame) != {"type", "peer_id", "binary", "data"}
                                    or type(frame["binary"]) is not bool
                                    or not isinstance(frame["data"], str)):
                                raise ValueError("invalid native viewer data")
                            data = (
                                base64.b64decode(frame["data"], validate=True)
                                if frame.get("binary")
                                else frame["data"]
                            )
                            if kit is None:
                                # Valid frames already buffered for this exact
                                # detached peer carry no new viewer authority.
                                continue
                            try:
                                await kit.send(data)
                            except (ConnectionClosed, OSError, TimeoutError) as error:
                                await viewer_failed(error, "kit_send")
                        elif kind == "session.keepalive":
                            await socket.send_json(
                                {"type": "session.keepalive", "deadline_at": deadline}
                            )
                        else:
                            raise ValueError("invalid native transport frame")
                finally:
                    await detach()

            tasks = [asyncio.create_task(run()), watcher]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except WebSocketDisconnect:
            outcome = "disconnected"
        except Exception as error:
            # Private, owner-bound diagnostics are sanitized by the App before
            # persistence/public projection. Never send an exception to a viewer.
            failure_message = str(error)[:4000]
        finally:
            cancel_preparation.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            exit_code = (
                process.child.returncode
                if process is not None and process.child is not None else None
            )
            if process is not None:
                await joined(asyncio.create_task(process.stop("native_session_close")))
            settled = process is None or process.state == "stopped"
            if settled and finalize is not None:
                try:
                    await joined(asyncio.create_task(asyncio.to_thread(finalize)))
                except Exception:
                    # Delivery failure is a failed result, never a successful
                    # scientific output. Physical GPU cleanup remains known.
                    if outcome != "error":
                        outcome, phase = "error", "delivery"
                        failure_message = "Output publication failed; retained session files require operator retrieval."
                    health["available"] = False
                    health["output_delivery"] = "failed"
                    health["output_retention"] = (
                        "pod_local_until_operator_export_or_pod_loss"
                    )
                    logging.getLogger(__name__).error(
                        "Interactive output publication failed for %s; preserve its work_root directory for operator export; no replay",
                        sid,
                    )
            if start_digest is not None:
                code = {
                    "done": "session_completed",
                    "cancelled": "session_cancelled",
                    "disconnected": "session_transport_disconnected",
                }.get(outcome, {
                    "preparation": "project_preparation_failed",
                    "initialization": "initialization_failed",
                    "running": "execution_failed",
                    "delivery": "output_delivery_failed",
                }[phase])
                evidence = {
                    "type": "isaac.session.execution",
                    "session_id": sid,
                    "start_sha256": start_digest,
                    "image": expected_image,
                    "runtime_revision": runtime_revision,
                    "phase": phase,
                    "outcome": outcome,
                    "code": code,
                    "signaling_ready": signaling_ready,
                    "exit_code": exit_code,
                    "cleanup": "settled" if settled else "unknown",
                    "message": failure_message,
                    "log_tail": "",
                }
                if config is not None and outcome == "error" and config.get("log_file"):
                    with contextlib.suppress(OSError):
                        with Path(config["log_file"]).open("rb") as log:
                            log.seek(0, os.SEEK_END)
                            log.seek(max(0, log.tell() - 16384))
                            evidence["log_tail"] = log.read(16384).decode("utf-8", errors="replace")
                # This trusted file preserves the observation for operator export;
                # it is not a lease or a physical-release declaration.
                if config is not None and config.get("closeout_file"):
                    try:
                        path = Path(config["closeout_file"]).with_name("execution-outcome.json")
                        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                        with os.fdopen(fd, "w") as stream:
                            json.dump(evidence, stream, sort_keys=True)
                            stream.write("\n")
                            stream.flush()
                            os.fsync(stream.fileno())
                    except OSError:
                        logging.getLogger(__name__).error("Session execution receipt could not be retained for %s", sid)
                # A failed transport cannot turn observed execution into success
                # or release a worker whose process cleanup is unknown.
                with contextlib.suppress(Exception):
                    await joined(asyncio.create_task(
                        asyncio.wait_for(socket.send_json(evidence), timeout=5)
                    ))
            if attached and settled:
                try:
                    result = await joined(
                        asyncio.create_task(api.release(sid, connection, outcome))
                    )
                    if result.get("status") != "ended":
                        raise ValueError("native release was not settled")
                except Exception:
                    health["available"], health["cleanup_unknown"] = False, True
            elif attached:
                health["available"], health["cleanup_unknown"] = False, True
            with contextlib.suppress(Exception):
                await joined(asyncio.create_task(
                    asyncio.wait_for(socket.close(code=1011 if outcome == "error" else 1000), timeout=5)
                ))
            health["active"] = False
            gate.release()

    return Starlette(
        routes=[
            Route("/healthz", ready),
            Route("/livez", live),
            WebSocketRoute("/v1/isaac/stream", stream),
        ]
    )
