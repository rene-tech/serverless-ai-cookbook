"""One process group owned by one already-admitted session. No queue or retry."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
import sys
from pathlib import Path

from .contract import validate
from . import isolation


def processes():
    """PID/start-time only, in this container's PID namespace; no argv/secrets."""
    result = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            if fields[0] != "Z":
                result[int(path.name)] = int(fields[19])
        except (FileNotFoundError, ProcessLookupError):
            continue
    return result


class SessionProcess:
    def __init__(self, config):
        self.config = validate(config)
        self.child = None
        self.state = "created"
        self.stop_reason = None
        self.active_connection = False
        self._lock = asyncio.Lock()
        self._log = None
        self._baseline = None
        self.cleanup_witness = "not_requested"

    async def start(self):
        async with self._lock:
            if self.state != "created":
                raise RuntimeError("this session cannot start twice")
            if time.time() >= self.config["deadline_at"]:
                raise RuntimeError("native session deadline has elapsed")
            work = Path(self.config["work_dir"])
            work.mkdir(parents=True, exist_ok=False, mode=0o700)
            self._log = Path(self.config.get("log_file", work / "execution.log")).open(
                "xb"
            )
            if self.config.get("pid_namespace_guard"):
                self._baseline = processes()
            env = isolation.clean_environment(work, self.config.get("environment"))
            sandbox = self.config.get("isolation")
            for name in (
                "HOME",
                "TMPDIR",
                "XDG_RUNTIME_DIR",
                "XDG_CACHE_HOME",
                "XDG_CONFIG_HOME",
                "CUDA_CACHE_PATH",
                "ISAAC_HEALTHCARE_KIT_ROOT",
            ):
                path = Path(env[name])
                path.mkdir(mode=0o700)
                if sandbox:
                    isolation.own(path, sandbox["uid"])
            command = self.config["command"]
            options = {}
            policy_fd = None
            if sandbox:
                isolation.empty_ipc()
                isolation.own(work, sandbox["uid"])
                env["USER"] = env["LOGNAME"] = "isaac-project-" + str(sandbox["uid"])
                policy = {
                    "uid": sandbox["uid"],
                    "command": command,
                    "environment": env,
                    "cwd": self.config.get("cwd", str(work)),
                    "rules": [
                        *isolation.runtime_rules(sandbox["runtime_roots"]),
                        *isolation.device_rules(),
                        {"path": sandbox["root"], "write": True},
                        *[
                            {"path": p, "write": True}
                            for p in sandbox.get("extra_write_roots", [])
                        ],
                        {"path": "/dev/shm", "write": True},
                    ],
                }
                policy_fd = isolation.sealed_policy(policy)
                command = [
                    sys.executable,
                    "-I",
                    "-B",
                    str(Path(isolation.__file__)),
                    "--policy-fd",
                    str(policy_fd),
                ]
                options = {
                    "user": sandbox["uid"],
                    "group": sandbox["uid"],
                    "extra_groups": isolation.device_groups(),
                    "pass_fds": (policy_fd,),
                }
            try:
                self.child = await asyncio.create_subprocess_exec(
                    *command,
                    cwd="/" if sandbox else self.config.get("cwd", work),
                    env=env,
                    stdout=self._log,
                    stderr=asyncio.subprocess.STDOUT,
                    start_new_session=True,
                    umask=0o077,
                    **options,
                )
            except BaseException:
                self._log.close()
                self.state = "failed"
                raise
            finally:
                if policy_fd is not None:
                    os.close(policy_fd)
            self.state = "starting"

    async def wait_signaling(self):
        until = min(
            time.time() + self.config["startup_timeout_seconds"],
            self.config["deadline_at"],
        )
        while time.time() < until:
            if self.child is None or self.child.returncode is not None:
                raise RuntimeError("Isaac exited before signaling became available")
            try:
                _, writer = await asyncio.open_connection(
                    "127.0.0.1", self.config["signal_port"]
                )
                writer.close()
                await writer.wait_closed()
                self.state = "signaling"
                return
            except OSError:
                await asyncio.sleep(0.2)
        raise TimeoutError("Isaac signaling startup deadline exceeded")

    def status(self):
        return {
            "session_id": self.config["session_id"],
            "state": self.state,
            "process_exit_code": None if self.child is None else self.child.returncode,
            "signaling_connected": self.active_connection,
            "media_ready": None,
            "media_readiness_source": "requires actual browser decoded-frame evidence",
            "stop_reason": self.stop_reason,
            "workflow_cleanup_witness": self.cleanup_witness,
        }

    async def stop(self, reason):
        async with self._lock:
            if self.state in {"stopped", "failed"}:
                return
            self.stop_reason, self.state = reason, "stopping"
            if self.child is not None:
                # Always address the original process group, including children
                # left behind if the group leader exited first.
                try:
                    os.killpg(self.child.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(
                        self.child.wait(), self.config["stop_grace_seconds"]
                    )
                except TimeoutError:
                    pass
                try:
                    os.killpg(self.child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await self.child.wait()
                try:
                    os.killpg(self.child.pid, 0)
                except ProcessLookupError:
                    self.state = "stopped"
                else:
                    self.state = "cleanup_unknown"
            else:
                self.state = "stopped"
            if self._baseline is not None:
                # Authored projects can create detached descendants. A group
                # close alone cannot prove those left; quarantine, never reuse
                # this worker, if its isolated PID namespace has extra processes.
                if any(
                    self._baseline.get(pid) != stamp
                    for pid, stamp in processes().items()
                ):
                    self.state = "cleanup_unknown"
            sandbox = self.config.get("isolation")
            if sandbox and self.state == "stopped":
                try:
                    cleanup = await asyncio.create_subprocess_exec(
                        sys.executable,
                        "-I",
                        "-B",
                        str(Path(isolation.__file__)),
                        "--cleanup-ipc",
                        str(sandbox["uid"]),
                        user=sandbox["uid"],
                        group=sandbox["uid"],
                        extra_groups=[],
                        env=isolation.clean_environment(
                            Path(sandbox["root"]) / "process"
                        ),
                        stdout=self._log,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    try:
                        code = await asyncio.wait_for(
                            cleanup.wait(), self.config["stop_grace_seconds"]
                        )
                    except TimeoutError:
                        cleanup.kill()
                        await cleanup.wait()
                        raise RuntimeError("IPC cleanup did not join")
                    if code:
                        raise RuntimeError("IPC cleanup failed")
                    isolation.clear_shm(sandbox["uid"])
                    isolation.empty_ipc()
                    isolation.reclaim(sandbox["root"])
                    for path in sandbox.get("extra_write_roots", []):
                        isolation.reclaim(path)
                except (OSError, RuntimeError):
                    self.state = "cleanup_unknown"
            witness = self.config.get("cleanup_witness")
            if witness is not None and self.state == "stopped":
                try:
                    value = json.loads(Path(witness).read_text())
                    if (
                        value.get("session_id") != self.config["session_id"]
                        or value.get("children_joined") is not True
                    ):
                        raise ValueError("process cleanup witness differs")
                    self.cleanup_witness = "reported_joined"
                except (OSError, ValueError):
                    self.cleanup_witness = "missing_or_invalid"
                    # An authored witness is diagnostic. An empty owned PID/IPC
                    # namespace is the actual proof, including early failures
                    # before a workflow could write its witness.
                    if self._baseline is None:
                        self.state = "cleanup_unknown"
            if self._log:
                self._log.close()
            work = Path(self.config["work_dir"])
            closeout = Path(
                self.config.get("closeout_file", work / "process-closeout.json")
            )
            if closeout.parent.exists():
                closeout.write_text(json.dumps(self.status(), sort_keys=True) + "\n")

    async def monitor(self):
        while self.state not in {"stopped", "failed", "cleanup_unknown"}:
            if time.time() >= self.config["deadline_at"]:
                await self.stop("native_deadline")
                return
            if self.child is not None and self.child.returncode is not None:
                await self.stop("process_exit")
                return
            await asyncio.sleep(0.2)
