"""CPU probe under the deployed controller's four capabilities, no GPU/network."""

import asyncio
import json
import os
from pathlib import Path
import sys
import time

from i4h_interactive.process import SessionProcess, processes


async def run():
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    assert os.geteuid() == 0 and int(status["CapEff"], 16) == sum(1 << n for n in (0, 5, 6, 7))
    root = Path("/tmp/readiness-owned-probe")
    root.mkdir(mode=0o711)
    work = root / "work"
    work.mkdir(mode=0o700)
    os.chown(work, 10001, 10001)
    marker = work / "startup-ready.json"
    config = {"session_id": "ordinary-isolated-session", "command": [sys.executable],
              "work_dir": str(work), "startup_readiness_file": str(marker),
              "browser_origin": "https://ordinary.test", "media_host": "127.0.0.1",
              "signal_port": 49100, "media_port": 47998, "proxy_port": 49200,
              "deadline_at": time.time() + 30, "stop_grace_seconds": 1,
              "startup_timeout_seconds": 10, "network_mode": "authenticated-private-network",
              "isolation": {"uid": 10001}}
    code = '''import os,json,time
from pathlib import Path
p=Path(%r)
v={"schema":"isaac-workflow-readiness/v1","session_id":"ordinary-isolated-session","event":"workflow_started","pid":os.getpid(),"start_ticks":int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])}
p.write_text(json.dumps(v));p.chmod(0o600)
print('ready',flush=True)
time.sleep(30)
''' % str(marker)
    child = await asyncio.create_subprocess_exec(sys.executable, "-I", "-B", "-c", code,
        user=10001, group=10001, extra_groups=[], env={}, cwd="/",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        assert await asyncio.wait_for(child.stdout.readline(), 5) == b"ready\n"
        try:
            marker.read_bytes()
        except PermissionError:
            pass
        else:
            raise AssertionError("controller unexpectedly has project-directory read authority")
        session = SessionProcess(config)
        session.child, session.state = child, "starting"
        before = processes()
        assert await session.workflow_ready() is True
        assert processes() == before  # The UID-dropped reader is joined.
        assert child.returncode is None and session.state == "starting"
        print(json.dumps({"status": "PASS", "controller_uid": 0, "project_uid": 10001,
                          "directory_mode": "0700", "record_mode": "0600",
                          "direct_controller_read": "PermissionError", "owned_uid_read": True,
                          "reader_joined": True, "capabilities_unchanged": True}))
    finally:
        if child.returncode is None:
            child.terminate()
        await child.wait()


if __name__ == "__main__":
    asyncio.run(run())
