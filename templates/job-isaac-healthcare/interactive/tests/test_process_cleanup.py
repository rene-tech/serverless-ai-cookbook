"""Owned-process joins and fail-closed cleanup, with synthetic proc metadata."""
import asyncio
import json
import os
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

from i4h_interactive import process


def stat(pid=42):
    return f"{pid} (name with ) parentheses) " + " ".join(
        ["Z", str(os.getpid())] + ["0"] * 17 + ["812"]
    )


class Proc:
    def __init__(self, parts, data):
        self.parts, self.data = tuple(parts), data
        self.name = self.parts[-1]

    def __truediv__(self, name):
        return Proc((*self.parts, str(name)), self.data)

    def read_text(self):
        return self.data[self.name]

    def iterdir(self):
        return iter([self / "42"])


def synthetic_proc(data):
    def path(value, *rest):
        if str(value) == "/proc":
            return Proc(("/proc", *map(str, rest)), data)
        return Path(value, *rest)
    return patch.object(process, "Path", path)


def config(root):
    return {"session_id": "process-cleanup-test", "command": [sys.executable],
            "work_dir": str(root), "browser_origin": "https://example.test",
            "media_host": "127.0.0.1", "signal_port": 51001, "media_port": 51002,
            "proxy_port": 51003, "deadline_at": 1, "stop_grace_seconds": 1,
            "startup_timeout_seconds": 1, "network_mode": "authenticated-private-network",
            "isolation": {"uid": os.geteuid() + 100000, "root": str(root)}}


def test_identity_preserves_parent_start_and_all_uids():
    with synthetic_proc({"stat": stat(), "status": "Pid:\t42\nUid:\t43 43 43 43\n"}):
        assert process._process_identity(42) == {"pid": 42, "parent": os.getpid(),
            "state": "Z", "start_ticks": 812, "uids": (43,) * 4}


@pytest.mark.parametrize("metadata", [
    {"stat": "42 malformed", "status": "Pid:42\nUid:43 43 43 43"},
    {"stat": "42 (test) Z", "status": "Pid:42\nUid:43 43 43 43"},
    {"stat": stat(), "status": "Pid:42"},
    {"stat": stat(), "status": "Pid:42\nUid:invalid"},
    {"stat": stat(), "status": "Pid:42\nUid:43 43 43 43\ninvalid"},
])
def test_malformed_proc_identity_is_a_cleanup_error(metadata):
    with synthetic_proc(metadata), pytest.raises(RuntimeError, match="metadata is malformed"):
        process._process_identity(42)


def test_parser_failure_quarantines_without_reap_or_reclaim(tmp_path):
    session = process.SessionProcess(config(tmp_path))
    session._baseline = {}
    with synthetic_proc({"stat": stat(), "status": "Pid:42"}), \
            patch.object(process.os, "waitpid") as wait, \
            patch.object(process.isolation, "reclaim") as reclaim:
        asyncio.run(session.stop("test"))
    assert session.state == "cleanup_unknown"
    assert session._reaped_adopted_zombies == []
    assert json.loads((tmp_path / "process-closeout.json").read_bytes())["state"] == "cleanup_unknown"
    wait.assert_not_called()
    reclaim.assert_not_called()


def identity(pid, uid, **changes):
    return {"pid": pid, "parent": os.getpid(), "state": "Z", "start_ticks": pid * 11,
            "uids": (uid,) * 4, **changes}


def test_only_stable_owned_adopted_zombie_is_joined():
    uid = os.geteuid() + 100000
    entries = {
        51: identity(51, uid), 52: identity(52, uid + 1),
        53: identity(53, uid, parent=os.getpid() + 1),
        54: identity(54, uid, state="S"),
        55: identity(55, uid), 56: identity(56, uid),
    }
    root = Mock()
    root.iterdir.return_value = [Path(str(pid)) for pid in entries]
    with patch.object(process, "Path", return_value=root), \
            patch.object(process, "_process_identity", side_effect=entries.__getitem__) as read, \
            patch.object(process.os, "waitpid", return_value=(51, 0)) as wait:
        result = process.reap_owned_adopted_zombies(uid, {55, 56})
    assert result == [{**entries[51], "wait_status": 0}]
    assert [call.args[0] for call in read.call_args_list] == [51, 51, 52, 53, 54]
    wait.assert_called_once_with(51, os.WNOHANG)


def test_changed_identity_is_never_joined():
    uid = os.geteuid() + 100000
    root = Mock()
    root.iterdir.return_value = [Path("51")]
    with patch.object(process, "Path", return_value=root), \
            patch.object(process, "_process_identity", side_effect=[identity(51, uid), identity(51, uid, start_ticks=1)]), \
            patch.object(process.os, "waitpid") as wait, \
            pytest.raises(RuntimeError, match="identity changed"):
        process.reap_owned_adopted_zombies(uid, set())
    wait.assert_not_called()


def test_unwaitable_owned_zombie_remains_an_error():
    uid = os.geteuid() + 100000
    root = Mock()
    root.iterdir.return_value = [Path("51")]
    with patch.object(process, "Path", return_value=root), \
            patch.object(process, "_process_identity", return_value=identity(51, uid)), \
            patch.object(process.os, "waitpid", return_value=(0, 0)), \
            pytest.raises(RuntimeError, match="could not be joined"):
        process.reap_owned_adopted_zombies(uid, set())
