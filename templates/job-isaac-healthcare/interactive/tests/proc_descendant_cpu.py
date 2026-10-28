"""Run in a dedicated CPU container using installed controller and SessionProcess; no GPU, Kit or network."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from i4h_interactive import isolation
from i4h_interactive.process import SessionProcess


def opening(path):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)
        os.close(fd)
        return {"allowed": True, "writes": 0}
    except OSError as error:
        return {"errno": error.errno, "writes": 0}


async def main():
    settings = json.loads(Path("/opt/interactive/worker.json").read_bytes())
    root = Path("/work/proc-runtime-cpu")
    root.mkdir(mode=0o711)
    root.chmod(0o711)
    uid, foreign_uid = isolation.new_identity(root), isolation.new_identity(root)
    project = root / "project"
    project.mkdir(mode=0o770)
    project.chmod(0o770)
    os.chown(project, 0, uid)
    runtime = Path("/srv/runtime")
    runtime.mkdir()
    canaries = [runtime / "world-writable-canary", Path("/authority/world-writable-canary")]
    for path in canaries:
        path.write_text("UNCHANGED_CPU_CANARY")
        path.chmod(0o666)
    roots = [*settings["runtime_roots"], str(runtime), str(Path(__file__).resolve().parent)]
    foreign = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import time;time.sleep(55)"],
                               user=foreign_uid, group=foreign_uid, extra_groups=[],
                               env={"PATH": "/usr/bin:/bin"}, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        version = isolation.controller_boundary(runtime_roots=roots, work_roots=[root], authority_roots=["/authority"])
        controller = {
            "proc_sys": opening("/proc/sys/kernel/hostname"),
            "sysrq": opening("/proc/sysrq-trigger"),
            "authority": opening("/authority/world-writable-canary"),
            "runtime": opening("/srv/runtime/world-writable-canary"),
            "foreign_comm": opening(f"/proc/{foreign.pid}/comm"),
            "foreign_mem": opening(f"/proc/{foreign.pid}/mem"),
        }
        for name, value in controller.items():
            assert value.get("errno") in ((13, 30) if name in ("proc_sys", "sysrq") else (13,)), (name, value)
        mounts = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            left, right = line.split(" - ", 1)
            fields, tail = left.split(), right.split()
            if fields[4] == "/proc" or fields[4].startswith("/proc/"):
                mounts.append({"mountpoint": fields[4], "mount_options": fields[5],
                               "filesystem": tail[0], "source": tail[1], "super_options": tail[2]})
        config = {
            "session_id": "proc-runtime-cpu", "command": ["/opt/i4h/arena/.venv/bin/python", "-I", "-B",
                str(Path(__file__).with_name("proc_descendant_child.py")), "--depth", "0", "--controller", str(os.getpid()),
                "--foreign", str(foreign.pid), "--output", str(project / "result.json")],
            "work_dir": str(project / "process"), "log_file": str(root / "execution.log"),
            "closeout_file": str(root / "closeout.json"), "browser_origin": "https://diagnostic.invalid",
            "media_host": "127.0.0.1", "signal_port": 49100, "media_port": 47998, "proxy_port": 49200,
            "deadline_at": time.time() + 45, "stop_grace_seconds": 3, "startup_timeout_seconds": 1,
            "network_mode": "turn-relay", "turn_url": "turns:diagnostic.invalid:5349?transport=tcp",
            "pid_namespace_guard": True, "isolation": {"root": str(project), "uid": uid, "runtime_roots": roots},
            "environment": settings["runtime_environment"],
        }
        process = SessionProcess(config)
        await process.start()
        await asyncio.wait_for(process.child.wait(), timeout=35)
        await process.stop("CPU_probe_complete")
        if process.child.returncode:
            print((root / "execution.log").read_text(), file=sys.stderr)
        assert process.child.returncode == 0 and process.state == "stopped", process.status()
        assert all(path.read_text() == "UNCHANGED_CPU_CANARY" for path in canaries)
        print(json.dumps({
            "status": "CPU_BOUNDARY_PASS", "landlock_abi": version, "kernel": os.uname().release,
            "controller": controller, "child": json.loads((project / "result.json").read_bytes()),
            "proc_mounts": mounts, "process_state": process.state, "unchanged_canaries": True,
            "CUDA_or_Kit_calls": 0, "network_calls": 0,
            "scope": "CPU-only installed SessionProcess/shared isolation; wrapper, exec descendants and future threads.",
            "limit": "Own-process proc controls retain kernel access semantics; actual GPU causal confirmation pending.",
        }, sort_keys=True))
    finally:
        foreign.terminate()
        foreign.wait(timeout=3)


asyncio.run(main())
