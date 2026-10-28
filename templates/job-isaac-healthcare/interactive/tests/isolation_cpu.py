"""Run in an isolated CPU-only container, using the production process boundary."""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/interactive-src")
from i4h_interactive import isolation
from i4h_interactive.process import SessionProcess

RUNTIME_ROOTS = ["/opt/interactive-src", "/opt/runtime", "/runtime-demo"] + [
    p for p in ("/opt/i4h", "/opt/python") if Path(p).exists()
]

CHILD = r"""
import ctypes, json, os, pathlib, time, sys
root=pathlib.Path(sys.argv[1]); out={}
paths={
 'world_readable_native_token':'/run/secrets/native/token',
 'derived_key':'/config/derived-key',
 'prior_session':'/work/previous/data.json',
 'controller_proc_environment':'/proc/1/environ',
 'controller_proc_token':'/proc/1/root/run/secrets/native/token',
 'outside_symlink':str(root/'escape'),
}
for name,path in paths.items():
 try: pathlib.Path(path).read_bytes(); out[name]='EXPOSED'
 except PermissionError: out[name]='DENIED'
try: pathlib.Path('/opt/runtime/immutable').write_text('bad');out['runtime_write']='EXPOSED'
except (PermissionError,OSError): out['runtime_write']='DENIED'
try: pathlib.Path('/runtime-demo/world-writable').write_text('bad');out['writable_runtime_write']='EXPOSED'
except PermissionError: out['writable_runtime_write']='DENIED'
try: os.setuid(0);out['regain_uid']='EXPOSED'
except PermissionError: out['regain_uid']='DENIED'
out['credential_environment_absent']=not any(k in os.environ for k in ('NATIVE_POD_TOKEN','APP_SIGNING_KEY','AWS_SECRET_ACCESS_KEY','HTTP_PROXY','PYTHONPATH','LD_PRELOAD'))
out['uid']=os.getuid();out['home_is_owned']=pathlib.Path(os.environ['HOME']).stat().st_uid==os.getuid()
out['no_new_privileges']='NoNewPrivs:\t1' in pathlib.Path('/proc/self/status').read_text()
pathlib.Path('/dev/shm/owned-posix').write_text('session-local')
libc=ctypes.CDLL(None,use_errno=True); shmid=libc.shmget(0,4096,0o1000|0o600)
assert shmid>=0
out['sysv_shm_created']=True
(root/'proof.json').write_text(json.dumps(out))
if sys.argv[2]=='detached':
 pid=os.fork()
 if pid==0:
  os.setsid();(root/'detached.pid').write_text(str(os.getpid()))
  while True: time.sleep(1)
 time.sleep(.3)
"""


def case(name, mode):
    parent = Path("/work") / name
    parent.mkdir(mode=0o711)
    uid = isolation.new_identity("/work")
    root = parent / "project"
    root.mkdir(mode=0o770)
    root.chmod(0o770)
    os.chown(root, 0, uid)
    (root / "escape").symlink_to("/run/secrets/native/token")
    script = root / "hostile.py"
    script.write_text(CHILD)
    script.chmod(0o444)
    return root, {
        "session_id": name,
        "command": [sys.executable, "-I", "-B", str(script), str(root), mode],
        "work_dir": str(root / "process"),
        "log_file": str(parent / "execution.log"),
        "closeout_file": str(parent / "process-closeout.json"),
        "browser_origin": "https://test.invalid",
        "media_host": "10.0.0.5",
        "signal_port": 49100,
        "media_port": 47998,
        "proxy_port": 49200,
        "deadline_at": time.time() + 60,
        "stop_grace_seconds": 2,
        "startup_timeout_seconds": 1,
        "network_mode": "turn-relay",
        "turn_url": "turns:turn.invalid:443?transport=tcp",
        "pid_namespace_guard": True,
        "isolation": {
            "root": str(root),
            "uid": uid,
            "runtime_roots": RUNTIME_ROOTS,
        },
    }


async def main():
    # Deliberately writable-root/default-capability container: the actual
    # controller must drop its own rights and enforce immutable runtime access.
    rootfs_readonly = bool(os.statvfs("/").f_flag & os.ST_RDONLY)
    assert rootfs_readonly is False
    Path("/runtime-demo").mkdir()
    target = Path("/runtime-demo/world-writable")
    target.write_text("readable immutable runtime asset")
    target.chmod(0o666)
    version = isolation.controller_boundary(
        runtime_roots=RUNTIME_ROOTS,
        work_roots=["/work"],
        authority_roots=["/run/secrets/native", "/config"],
    )
    try:
        target.write_text("controller must not alter runtime")
    except PermissionError:
        pass
    else:
        raise AssertionError("controller runtime boundary missing")
    caps = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
    )
    assert all(
        int(caps[key].strip(), 16) == 0xE1 for key in ("CapEff", "CapPrm", "CapBnd")
    )
    assert int(caps["CapAmb"].strip(), 16) == 0 and int(caps["CapInh"].strip(), 16) == 0
    isolation.empty_ipc()
    Path("/work/previous").mkdir()
    Path("/work/previous/data.json").write_text("synthetic prior owner state")
    os.environ.update(
        NATIVE_POD_TOKEN="synthetic",
        APP_SIGNING_KEY="synthetic",
        AWS_SECRET_ACCESS_KEY="synthetic",
        HTTP_PROXY="http://synthetic.invalid",
    )
    root, cfg = case("first", "normal")
    p = SessionProcess(cfg)
    await p.start()
    await asyncio.wait_for(p.child.wait(), 10)
    if p.child.returncode:
        raise AssertionError(Path(cfg["log_file"]).read_text())
    await p.stop("test")
    assert p.state == "stopped", p.status()
    proof = json.loads((root / "proof.json").read_text())
    assert all(
        value == "DENIED"
        for key, value in proof.items()
        if key
        in (
            "world_readable_native_token",
            "derived_key",
            "prior_session",
            "controller_proc_environment",
            "controller_proc_token",
            "outside_symlink",
            "runtime_write",
            "writable_runtime_write",
            "regain_uid",
        )
    ), proof
    assert (
        proof["credential_environment_absent"]
        and proof["home_is_owned"]
        and proof["no_new_privileges"]
    )
    assert root.stat().st_uid == 0 and root.stat().st_mode & 0o777 == 0o700
    isolation.empty_ipc()
    root2, cfg2 = case("second", "detached")
    q = SessionProcess(cfg2)
    assert cfg["isolation"]["uid"] != cfg2["isolation"]["uid"]
    await q.start()
    await asyncio.wait_for(q.child.wait(), 10)
    if q.child.returncode:
        raise AssertionError(Path(cfg2["log_file"]).read_text())
    # Read-only proof comes from the exited project; root reclaims only the PID
    # file for this local CPU test, then terminates its exact owned descendant.
    pidfile = root2 / "detached.pid"
    os.chown(pidfile, 0, 0)
    pid = int(pidfile.read_text())
    try:
        await q.stop("test")
        assert q.state == "cleanup_unknown", q.status()
    finally:
        os.kill(pid, signal.SIGKILL)
    print(
        json.dumps(
            {
                "status": "PASS",
                "landlock_abi": version,
                "container_rootfs_readonly": rootfs_readonly,
                "controller_runtime_write_denied": True,
                "controller_capabilities": "CHOWN,KILL,SETGID,SETUID only; bounding/permitted/effective=0xe1",
                "actual_project_denials": proof,
                "normal_process_joined_and_ipc_cleared": True,
                "distinct_session_uids": True,
                "retained_state_sealed": True,
                "detached_descendant_quarantined": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
