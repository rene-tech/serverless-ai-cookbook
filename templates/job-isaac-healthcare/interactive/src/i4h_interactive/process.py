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


def _process_identity(pid):
    """Only fixed proc metadata; never argv, environment, memory or open files."""
    root = Path("/proc") / str(pid)
    try:
        raw = (root / "stat").read_text()
        fields = raw.rsplit(")", 1)[1].split()
        status = dict(line.split(":", 1) for line in (root / "status").read_text().splitlines())
        uids = tuple(map(int, status["Uid"].split()))
        if len(uids) != 4 or int(status["Pid"].strip()) != pid:
            raise RuntimeError("process identity is incomplete")
        return {"pid": pid, "parent": int(fields[1]), "state": fields[0],
                "start_ticks": int(fields[19]), "uids": uids}
    except (ValueError, KeyError, IndexError) as exc:
        raise RuntimeError("process identity metadata is malformed") from exc


def reap_owned_adopted_zombies(uid, excluded):
    """Join only this session's stable adopted zombies, never a global waitpid."""
    if type(uid) is not int or uid <= 0 or uid == os.geteuid():
        raise RuntimeError("a distinct reserved project identity is required")
    reaped = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit() or int(path.name) in excluded:
            continue
        pid = int(path.name)
        try:
            first = _process_identity(pid)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if (first["uids"] != (uid,) * 4 or first["parent"] != os.getpid()
                or first["state"] != "Z"):
            continue
        try:
            second = _process_identity(pid)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if second != first:
            raise RuntimeError("adopted zombie identity changed before join")
        # A waitable zombie cannot reuse its PID until its parent reaps it.
        # The managed Popen leader and every baseline PID are excluded, so this
        # positive-PID wait cannot race their registered child watchers.
        waited, status = os.waitpid(pid, os.WNOHANG)
        if waited != pid:
            raise RuntimeError("owned adopted zombie could not be joined")
        reaped.append({**first, "wait_status": status})
    return reaped


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
        self._reaped_adopted_zombies = []

    @property
    def startup_readiness_source(self):
        if self.state in {"created", "starting"}:
            return "pending"
        return "workflow_started" if self.config.get("startup_readiness_file") else "signaling_socket"

    async def workflow_ready(self):
        """Read an optional typed lifecycle event from this invocation only."""
        path = self.config.get("startup_readiness_file")
        if path is None:
            return True  # Direct custom commands retain their socket contract.
        sandbox = self.config.get("isolation")
        if sandbox:
            # Root intentionally has no DAC override. Read only this bounded
            # record in a child with the already-reserved project identity.
            reader = await asyncio.create_subprocess_exec(
                sys.executable, "-I", "-B", str(Path(isolation.__file__)),
                "--read-workflow-ready", path, "--read-workflow-uid", str(sandbox["uid"]),
                user=sandbox["uid"], group=sandbox["uid"], extra_groups=[],
                env={"PYTHONDONTWRITEBYTECODE": "1"}, cwd="/",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                raw, _ = await asyncio.wait_for(reader.communicate(), max(0.01, min(5, self.config["deadline_at"] - time.time())))
                if reader.returncode == 3:
                    return False
                if reader.returncode != 0:
                    raise RuntimeError("owned workflow readiness reader failed")
            finally:
                if reader.returncode is None:
                    try:
                        reader.kill()
                    except ProcessLookupError:
                        pass
                await reader.wait()
        else:
            raw = isolation.read_workflow_readiness(path)
        if raw is None:
            return False
        value = json.loads(raw)
        if (not isinstance(value, dict)
                or set(value) != {"schema", "session_id", "event", "pid", "start_ticks"}
                or value["schema"] != "isaac-workflow-readiness/v1"
                or value["session_id"] != self.config["session_id"]
                or value["event"] != "workflow_started"
                or type(value["pid"]) is not int or value["pid"] <= 0
                or type(value["start_ticks"]) is not int):
            raise RuntimeError("workflow readiness identity differs")
        current = _process_identity(value["pid"])
        if current["start_ticks"] != value["start_ticks"] or current["state"] == "Z":
            raise RuntimeError("workflow readiness process changed")
        if self.config.get("isolation") and current["uids"] != (self.config["isolation"]["uid"],) * 4:
            raise RuntimeError("workflow readiness project identity differs")
        # The signal cannot be inherited from an unrelated live process.
        seen = set()
        while current["pid"] != self.child.pid:
            if current["pid"] in seen or current["parent"] <= 0:
                raise RuntimeError("workflow readiness is outside the owned process tree")
            seen.add(current["pid"])
            current = _process_identity(current["parent"])
        return True

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
            if ready_file := self.config.get("startup_readiness_file"):
                # These noncredential values are set by the process owner, not
                # accepted as arbitrary inherited project environment variables.
                env["I4H_WORKFLOW_READY_FILE"] = ready_file
                env["I4H_WORKFLOW_READY_SESSION"] = self.config["session_id"]
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
                if await asyncio.wait_for(self.workflow_ready(), max(0.01, until - time.time())):
                    self.state = "signaling"
                    return
                await asyncio.sleep(0.2)
            except OSError:
                await asyncio.sleep(0.2)
        raise TimeoutError("Isaac signaling startup deadline exceeded")

    def status(self):
        terminal = (self.state in {"stopping", "stopped", "failed", "cleanup_unknown"}
                    or time.time() >= self.config["deadline_at"]
                    or (self.child is not None and self.child.returncode is not None))
        return {
            "session_id": self.config["session_id"],
            "state": self.state,
            "process_exit_code": None if self.child is None else self.child.returncode,
            "signaling_connected": self.active_connection,
            "media_ready": None,
            "media_readiness_source": "requires actual browser decoded-frame evidence",
            "startup_ready": self.state == "signaling" and not terminal,
            "startup_readiness_source": self.startup_readiness_source,
            "terminal": terminal,
            "deadline_at": self.config["deadline_at"],
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
            self.state = "stopped"
            sandbox = self.config.get("isolation")
            if self._baseline is not None:
                # PID1 adopts double-forked children. Join only already-exited
                # session-owned orphans; leave live/foreign/uncertain processes
                # quarantined after the existing cleanup grace period.
                excluded = set(self._baseline)
                if self.child is not None:
                    excluded.add(self.child.pid)
                until = time.monotonic() + self.config["stop_grace_seconds"]
                while True:
                    if sandbox:
                        try:
                            self._reaped_adopted_zombies.extend(
                                reap_owned_adopted_zombies(sandbox["uid"], excluded)
                            )
                        except (OSError, RuntimeError):
                            self.state = "cleanup_unknown"
                            break
                    unexpected = any(
                        self._baseline.get(pid) != stamp
                        for pid, stamp in processes().items()
                    )
                    if not unexpected:
                        break
                    if not sandbox or time.monotonic() >= until:
                        self.state = "cleanup_unknown"
                        break
                    await asyncio.sleep(0.02)
            if self.child is not None:
                try:
                    os.killpg(self.child.pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    self.state = "cleanup_unknown"
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
                closeout.write_text(
                    json.dumps({**self.status(), "adopted_zombies_reaped": self._reaped_adopted_zombies}, sort_keys=True) + "\n"
                )

    async def monitor(self):
        while self.state not in {"stopped", "failed", "cleanup_unknown"}:
            if time.time() >= self.config["deadline_at"]:
                await self.stop("native_deadline")
                return
            if self.child is not None and self.child.returncode is not None:
                await self.stop("process_exit")
                return
            await asyncio.sleep(0.2)
