"""CPU startup-contract checks; no Kit, GPU, admission or live service."""

import asyncio
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from i4h_interactive.bridge import application as bridge_application
from i4h_interactive.process import SessionProcess, _process_identity
from i4h_interactive.server import application as portable_application
from test_boundary import config
from test_signaling_transport import chain, SERVICE, SID, wait_status


def session(root, *, marker=True):
    value = config(root)
    value["network_mode"] = "authenticated-private-network"
    if marker:
        value["startup_readiness_file"] = str(Path(value["work_dir"]) / "startup-ready.json")
    result = SessionProcess(value)
    Path(value["work_dir"]).mkdir()
    result.child = SimpleNamespace(pid=os.getpid(), returncode=None)
    result.state = "starting"
    return result


def write_ready(process, **changes):
    identity = _process_identity(os.getpid())
    value = {"schema": "isaac-workflow-readiness/v1", "session_id": process.config["session_id"],
             "event": "workflow_started", "pid": os.getpid(), "start_ticks": identity["start_ticks"], **changes}
    Path(process.config["startup_readiness_file"]).write_text(json.dumps(value))


def test_open_socket_waits_for_owned_workflow_event(tmp_path):
    async def run():
        process = session(tmp_path)
        async def accepted(reader, writer):
            writer.close()
            await writer.wait_closed()
        listener = await asyncio.start_server(accepted, "127.0.0.1", 0)
        process.config["signal_port"] = listener.sockets[0].getsockname()[1]
        async with listener:
            waiting = asyncio.create_task(process.wait_signaling())
            await asyncio.sleep(0.25)
            assert not waiting.done() and process.status()["startup_readiness_source"] == "pending"
            assert process.status()["startup_ready"] is False
            write_ready(process)
            await asyncio.wait_for(waiting, 1)
            assert process.status()["startup_ready"] is True
            assert process.status()["startup_readiness_source"] == "workflow_started"
    asyncio.run(run())


@pytest.mark.parametrize("change", [{"session_id": "another-session"}, {"start_ticks": -1}, {"event": "workflow_loading"}])
def test_readiness_rejects_wrong_invocation(tmp_path, change):
    process = session(tmp_path)
    write_ready(process, **change)
    with pytest.raises(RuntimeError):
        asyncio.run(process.workflow_ready())


def test_readiness_rejects_foreign_process_and_symlink(tmp_path):
    process = session(tmp_path)
    write_ready(process)
    process.child.pid = 987654321  # No ancestor can equal this absent test process.
    with pytest.raises(RuntimeError, match="owned process tree"):
        asyncio.run(process.workflow_ready())
    path = Path(process.config["startup_readiness_file"])
    path.unlink()
    path.symlink_to(tmp_path / "unrelated")
    with pytest.raises(OSError):
        asyncio.run(process.workflow_ready())


def test_readiness_fifo_and_oversize_are_bounded(tmp_path):
    process = session(tmp_path)
    path = Path(process.config["startup_readiness_file"])
    os.mkfifo(path)
    began = time.monotonic()
    with pytest.raises(RuntimeError, match="bounded regular file"):
        asyncio.run(process.workflow_ready())
    assert time.monotonic() - began < 1
    path.unlink()
    path.write_bytes(b" " * 4097)
    with pytest.raises(RuntimeError, match="bounded regular file"):
        asyncio.run(process.workflow_ready())


def test_custom_command_socket_fallback_and_original_deadline(tmp_path):
    async def run():
        process = session(tmp_path, marker=False)
        assert await process.workflow_ready() is True
        process.config["deadline_at"] = time.time() - 1
        with pytest.raises(TimeoutError):
            await process.wait_signaling()
        assert process.status()["terminal"] is True
        assert process.status()["startup_ready"] is False
    asyncio.run(run())


def test_pending_wait_can_be_cancelled_without_claiming_ready(tmp_path):
    async def run():
        process = session(tmp_path)
        waiting = asyncio.create_task(process.wait_signaling())
        await asyncio.sleep(0.02)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert process.state == "starting" and not process.status()["startup_ready"]
    asyncio.run(run())


def test_portable_descriptor_auth_pending_ready_and_terminal(tmp_path):
    process = session(tmp_path)
    token = "x" * 43
    client = TestClient(portable_application(process.config, token, process=process))
    path = "/descriptor"
    assert client.get(path).status_code == 403
    headers = {"Authorization": "Bearer " + token, "Origin": process.config["browser_origin"]}
    pending = client.get(path, headers=headers).json()
    assert (pending["startup_ready"], pending["terminal"], pending["startup_readiness_source"]) == (False, False, "pending")
    process.state = "signaling"
    ready = client.get(path, headers=headers).json()
    assert ready["startup_ready"] is True and ready["startup_readiness_source"] == "workflow_started"
    process.child.returncode = 7
    exited = client.get(path, headers=headers).json()
    assert exited["terminal"] is True and exited["startup_ready"] is False
    assert process.status()["terminal"] is True and not process.status()["startup_ready"]
    process.child.returncode = None
    deadline = process.config["deadline_at"] = time.time() - 1
    ended = client.get(path, headers=headers).json()
    assert ended["terminal"] is True and ended["startup_ready"] is False and ended["deadline_at"] == deadline
    assert client.get(path, headers={**headers, "Origin": "https://foreign.test"}).status_code == 403


def test_bridge_pending_projection_then_native_explicit_socket_contract():
    _, app, payload, state = chain()
    with TestClient(app) as client:
        assert client.post("/sessions", json=payload, headers={"Authorization": "Bearer " + SERVICE}).status_code == 202
        ready = wait_status(client, lambda value: value["state"] == "ready")
        assert ready["startup_ready"] is True and ready["terminal"] is False
        assert ready["deadline_at"] == payload["deadline_at"]
        assert ready["startup_readiness_source"] == "signaling_socket"
        assert len(state.processes) == len(state.attaches) == 1


@pytest.mark.parametrize("mutation", ["missing", "false", "wrong-deadline", "pending"])
def test_bridge_never_invents_missing_or_invalid_readiness(mutation):
    async def run():
        _, _, payload, _ = chain()
        frame = {"type": "isaac.session.signaling_ready", "session_id": SID,
                 "startup_ready": True, "startup_readiness_source": "workflow_started", "deadline_at": payload["deadline_at"]}
        if mutation == "missing":
            del frame["startup_ready"]
        elif mutation == "false":
            frame["startup_ready"] = False
        elif mutation == "wrong-deadline":
            frame["deadline_at"] += 1
        else:
            frame["startup_readiness_source"] = "pending"
        class Upstream:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def send(self, data): pass
            async def recv(self): return json.dumps(frame)
        from i4h_interactive.bridge import Tunnel
        item = Tunnel(payload, "wss://native.test", connect_factory=lambda *args, **kwargs: Upstream())
        assert item.state == "connecting" and item.startup_readiness_source == "pending"
        await item.run()
        assert item.state == "ended" and item.error == "native_transport_ended"
        assert item.startup_readiness_source == "pending"
    asyncio.run(run())
