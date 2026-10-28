"""CPU-only adversarial witness inside the unchanged SessionProcess boundary."""
import argparse
import ctypes
import errno
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

FLAGS = os.O_WRONLY | os.O_CREAT | os.O_TRUNC


def opening(path, flags=FLAGS):
    try:
        fd = os.open(path, flags, 0o666)
        os.close(fd)
        return {"allowed": True, "writes": 0}
    except OSError as error:
        return {"errno": error.errno, "writes": 0}


def rename_thread(name):
    path = Path(f"/proc/self/task/{threading.get_native_id()}/comm")
    fd = os.open(path, FLAGS, 0o666)
    try:
        count = os.write(fd, name.encode())
    finally:
        os.close(fd)
    return {"flags": FLAGS, "written": count, "readback": path.read_text().strip()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, required=True)
    parser.add_argument("--controller", type=int, required=True)
    parser.add_argument("--foreign", type=int, required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    assert os.getuid() != 0 and os.getgid() == os.getuid()
    assert all(int(status[key].strip(), 16) == 0 for key in ("CapEff", "CapPrm", "CapAmb"))
    assert status["NoNewPrivs"].strip() == "1"
    result = {"pid": os.getpid(), "uid": os.getuid(), "depth": args.depth,
              "capabilities": {key: status[key].strip() for key in ("CapEff", "CapPrm", "CapAmb", "CapBnd")},
              "no_new_privileges": status["NoNewPrivs"].strip(),
              "own_thread": rename_thread(f"cpu-depth-{args.depth}")}
    errors = []

    def thread():
        try:
            result["future_thread"] = rename_thread(f"cpu-future-{args.depth}")
        except BaseException as error:
            errors.append(repr(error))

    future = threading.Thread(target=thread)
    future.start()
    future.join()
    assert not errors, errors
    assert result["own_thread"]["readback"] == f"cpu-depth-{args.depth}"
    assert result["future_thread"]["readback"] == f"cpu-future-{args.depth}"

    paths = {
        "controller_comm": f"/proc/{args.controller}/comm",
        "controller_mem": f"/proc/{args.controller}/mem",
        "foreign_session_comm": f"/proc/{args.foreign}/comm",
        "foreign_session_mem": f"/proc/{args.foreign}/mem",
        "proc_sys": "/proc/sys/kernel/hostname",
        "sysrq": "/proc/sysrq-trigger",
        "runtime_file": "/srv/runtime/world-writable-canary",
        "authority_file": "/authority/world-writable-canary",
        "proc_root_runtime": "/proc/self/root/srv/runtime/world-writable-canary",
        "proc_root_authority": "/proc/self/root/authority/world-writable-canary",
        "unassigned_device": "/dev/tty",
    }
    result["denials"] = {name: opening(path) for name, path in paths.items()}
    fd = os.open("/srv/runtime/world-writable-canary", os.O_RDONLY)
    try:
        result["denials"]["proc_fd_runtime"] = opening(f"/proc/self/fd/{fd}")
    finally:
        os.close(fd)
    for name, value in result["denials"].items():
        expected = (errno.EACCES, errno.EROFS) if name in {"proc_sys", "sysrq"} else (errno.EACCES,)
        assert value.get("errno") in expected, (name, value)

    # No additional proc namespace creation/delete/rename rights were granted.
    result["new_proc_file"] = opening(f"/proc/self/task/{threading.get_native_id()}/cpu-must-not-exist")
    assert result["new_proc_file"].get("errno") in (errno.EACCES, errno.ENOENT, errno.EPERM)
    for name, action in {
        "setuid_root": lambda: os.setuid(0),
        "signal_foreign_check": lambda: os.kill(args.foreign, 0),
        "signal_controller_check": lambda: os.kill(args.controller, 0),
    }.items():
        try:
            action()
            result[name] = {"allowed": True}
        except OSError as error:
            result[name] = {"errno": error.errno}
        assert result[name].get("errno") == errno.EPERM, (name, result[name])
    libc = ctypes.CDLL(None, use_errno=True)
    result["unshare_user_namespace"] = {"returncode": libc.unshare(0x10000000), "errno": ctypes.get_errno()}
    assert result["unshare_user_namespace"] == {"returncode": -1, "errno": errno.EPERM}

    # Assigned utility device access remains unchanged; no GPU is present.
    fd = os.open("/dev/null", os.O_RDWR)
    try:
        try:
            fcntl.ioctl(fd, 0x1234, 0)
            result["assigned_null_ioctl"] = {"allowed": True}
        except OSError as error:
            result["assigned_null_ioctl"] = {"errno": error.errno}
    finally:
        os.close(fd)
    assert result["assigned_null_ioctl"].get("errno") == errno.ENOTTY

    # Kernel comm_write rejects other thread groups, including the same UID.
    sibling = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import time; time.sleep(15)"])
    try:
        path = Path(f"/proc/{sibling.pid}/comm")
        before = path.read_text()
        fd = os.open(path, FLAGS, 0o666)
        try:
            try:
                os.write(fd, b"cross-group")
                result["same_uid_other_thread_group"] = {"allowed": True}
            except OSError as error:
                result["same_uid_other_thread_group"] = {"errno": error.errno}
        finally:
            os.close(fd)
        result["same_uid_other_thread_group_unchanged"] = path.read_text() == before
        assert result["same_uid_other_thread_group"].get("errno") == errno.EINVAL
        assert result["same_uid_other_thread_group_unchanged"]
    finally:
        sibling.terminate()
        sibling.wait(timeout=3)

    # These own-process controls are deliberately recorded, never modified.
    result["additional_own_process_opens"] = {
        path: opening(path, os.O_WRONLY)
        for path in ("/proc/self/oom_score_adj", "/proc/self/attr/current", "/proc/self/mem")
    }
    if args.depth < 2:
        command = [sys.executable, "-I", "-B", __file__, "--depth", str(args.depth + 1),
                   "--controller", str(args.controller), "--foreign", str(args.foreign)]
        child = subprocess.run(command, capture_output=True, text=True, timeout=20)
        assert child.returncode == 0, child.stderr
        result["exec_descendant"] = json.loads(child.stdout)
    if args.output:
        Path(args.output).write_text(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
