"""Linux process/filesystem isolation for authored project Python.

No namespace/cgroup owner is added. Native retains the container/GPU lifecycle.
Landlock is mandatory, inherited by all descendants, and never best-effort.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import secrets
import stat
import shutil
import fcntl
import sys
from pathlib import Path

LIBC = ctypes.CDLL(None, use_errno=True)
# The supported x86_64/aarch64 Linux syscall ABI uses these Landlock numbers.
CREATE, ADD_RULE, RESTRICT = 444, 445, 446
READ = (1 << 0) | (1 << 2) | (1 << 3)
WRITE = (1 << 1) | sum(1 << n for n in range(4, 15))
# Never allow creating device nodes, even within the session directory.
WRITE &= ~((1 << 6) | (1 << 11))
FILE = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 14)


class Ruleset(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class Beneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int)]


class CapHeader(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]


class CapData(ctypes.Structure):
    _fields_ = [
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    ]


def checked(value, operation):
    if value < 0:
        raise OSError(ctypes.get_errno(), operation)
    return value


def abi():
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "aarch64"):
        raise RuntimeError(
            "interactive authored code requires supported Linux Landlock"
        )
    version = checked(LIBC.syscall(CREATE, 0, 0, 1), "landlock ABI probe")
    if version < 3:
        raise RuntimeError("Landlock ABI >=3 is required; isolation cannot be disabled")
    return version


def drop_controller_capabilities():
    # CHOWN, KILL, SETGID, SETUID only. Drop the bounding set before giving up
    # SETPCAP, so a later exec cannot recover Docker's other default rights.
    keep = sum(1 << n for n in (0, 5, 6, 7))
    header, data = CapHeader(0x20080522, 0), (CapData * 2)()
    checked(LIBC.capget(ctypes.byref(header), ctypes.byref(data)), "capget")
    current = data[0].permitted | data[1].permitted << 32
    if current & keep != keep:
        raise RuntimeError(
            "controller lacks its four required process/file capabilities"
        )
    last = int(Path("/proc/sys/kernel/cap_last_cap").read_text())
    for cap in [n for n in range(last + 1) if n != 8] + [8]:
        if not keep & (1 << cap) and checked(
            LIBC.prctl(23, cap, 0, 0, 0), "cap bounding read"
        ):
            checked(LIBC.prctl(24, cap, 0, 0, 0), "cap bounding drop")
    checked(LIBC.prctl(47, 4, 0, 0, 0), "clear ambient capabilities")
    data[0] = CapData(keep, keep, 0)
    data[1] = CapData(0, 0, 0)
    checked(LIBC.capset(ctypes.byref(header), ctypes.byref(data)), "capset")
    return keep


def controller_boundary(*, runtime_roots, work_roots, authority_roots):
    if os.geteuid() != 0:
        raise RuntimeError("the trusted controller requires its reviewed root identity")
    # Deny ptrace/proc-memory exposure; children additionally have distinct UIDs.
    checked(LIBC.prctl(4, 0, 0, 0, 0), "PR_SET_DUMPABLE")
    checked(LIBC.prctl(38, 1, 0, 0, 0), "PR_SET_NO_NEW_PRIVS")
    version = abi()
    drop_controller_capabilities()
    # Native201's API does not project a container securityContext. Enforce the
    # same write boundary inside the trusted entrypoint, before any listener or
    # authored code; read-only rootfs remains an additional operator defense.
    rules = [
        *runtime_rules(runtime_roots),
        *device_rules(),
        *[{"path": str(p), "write": True} for p in work_roots],
        *[{"path": str(p), "write": False} for p in authority_roots],
        {"path": "/dev/shm", "write": True},
    ]
    restrict(rules)
    return version


def sealed_policy(policy):
    """Return an immutable, anonymous policy FD, including standalone CPython.

    Arena's standalone Python does not export os.memfd_create. The same Linux
    libc operation supplies CLOEXEC and sealing without a writable temp file.
    The caller owns and closes the returned descriptor after child creation.
    """
    create = LIBC.memfd_create
    create.argtypes, create.restype = [ctypes.c_char_p, ctypes.c_uint], ctypes.c_int
    fd = checked(create(b"isaac-isolation-policy", 0x1 | 0x2), "memfd_create")
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(json.dumps(policy).encode())
        os.lseek(fd, 0, os.SEEK_SET)
        # Linux F_ADD_SEALS / F_GET_SEALS; these names may also be absent from
        # standalone CPython. Seal growth, shrink, writes and further seals.
        fcntl.fcntl(fd, 1033, 0xF)
        if fcntl.fcntl(fd, 1034) & 0xF != 0xF:
            raise RuntimeError("isolation policy was not fully sealed")
        return fd
    except BaseException:
        os.close(fd)
        raise


def new_identity(root):
    """Reserve a unique identity for this container lifetime, without reuse."""
    ledger = Path(root) / ".identities"
    ledger.mkdir(mode=0o700, exist_ok=True)
    if ledger.is_symlink() or ledger.stat().st_uid != os.geteuid():
        raise RuntimeError("identity ledger ownership differs")
    while True:
        uid = 100000 + secrets.randbelow(2**31 - 100001)
        try:
            with (ledger / str(uid)).open("x") as f:
                f.write("reserved\n")
            return uid
        except FileExistsError:
            continue


def own(path, uid, mode=0o700):
    path = Path(path)
    path.chmod(mode)
    os.chown(path, uid, uid, follow_symlinks=False)
    return path


def reclaim(path):
    """After complete process exit only, seal retained state to the controller.

    Directory descriptors and no-follow opens prevent project-created symlinks
    from redirecting privileged traversal outside this exact session tree.
    """
    path = Path(path)
    os.chown(path, 0, 0, follow_symlinks=False)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _reclaim_fd(fd)
    finally:
        os.close(fd)


def _reclaim_fd(fd):
    for name in os.listdir(fd):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        os.chown(name, 0, 0, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            child = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            try:
                _reclaim_fd(child)
                os.fchmod(child, 0o700)
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                raise RuntimeError("retained project file has an external hard link")
            os.chmod(name, 0o600, dir_fd=fd, follow_symlinks=False)
    os.fchown(fd, 0, 0)
    os.fchmod(fd, 0o700)


def clean_environment(root, supplied=None):
    """No inherited credential, proxy, native API, preload or Python variables."""
    root = Path(root)
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LIVESTREAM": "2",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    # These names describe installed runtime/device selection, not credentials.
    accepted = {
        "LD_LIBRARY_PATH",
        "CUDA_VISIBLE_DEVICES",
        "NVIDIA_VISIBLE_DEVICES",
        "NVIDIA_DRIVER_CAPABILITIES",
        "VK_ICD_FILENAMES",
        "VK_DRIVER_FILES",
        "ACCEPT_EULA",
        "ISAACSIM_ACCEPT_EULA",
        "PRIVACY_CONSENT",
        "OMNI_KIT_ACCEPT_EULA",
        "I4H_ARENA_PYTHON",
        "I4H_DATASET_PYTHON",
        "I4H_BUS_ROOT",
    }
    for name, value in (supplied or {}).items():
        if name not in accepted or not isinstance(value, str) or "\0" in value:
            raise ValueError("unapproved project environment name/value")
        env[name] = value
    for name, leaf in {
        "HOME": "home",
        "TMPDIR": "tmp",
        "XDG_RUNTIME_DIR": "run",
        "XDG_CACHE_HOME": "cache",
        "XDG_CONFIG_HOME": "config",
        "CUDA_CACHE_PATH": "cuda",
        "ISAAC_HEALTHCARE_KIT_ROOT": "kit",
    }.items():
        env[name] = str(root / leaf)
    return env


def proc_runtime_write_rule():
    """Permit inherited own-process controls under the kernel's procfs checks.

    CUDA opens each current/future thread's comm with O_CREAT|O_TRUNC. A rule
    rooted at this process's PID cannot cover the ordinary exec descendants.
    Both controller and child therefore grant only WRITE_FILE and TRUNCATE on
    procfs. Child UID/capability separation and kernel procfs access checks still
    apply; the standard container's global proc control mounts must stay read-only.
    """
    for name in ("bus", "fs", "irq", "sys", "sysrq-trigger"):
        path = Path("/proc") / name
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RuntimeError("global proc control mount is not read-only: " + str(path))
    return {"path": "/proc", "proc_runtime_write": True}


def runtime_rules(runtime_roots):
    paths = [
        "/usr",
        "/lib",
        "/lib64",
        "/bin",
        "/sbin",
        "/proc",
        "/sys",
        "/etc/ld.so.cache",
        "/etc/ld.so.conf",
        "/etc/ld.so.conf.d",
        "/etc/ssl/certs",
        "/etc/pki",
        "/etc/hosts",
        "/etc/resolv.conf",
        "/etc/nsswitch.conf",
        "/etc/gai.conf",
        "/etc/passwd",
        "/etc/group",
        "/etc/os-release",
        "/etc/localtime",
        "/etc/vulkan",
        "/etc/glvnd",
        "/run/nvidia/driver",
    ]
    for path in runtime_roots:
        p = Path(path)
        if (
            not p.is_absolute()
            or p == Path("/")
            or any(
                p.is_relative_to(prefix)
                for prefix in ("/proc", "/run", "/work", "/tmp", "/dev")
            )
        ):
            raise ValueError("runtime roots must be immutable image directories")
        paths.append(str(p))
    return [
        {"path": str(Path(p).resolve()), "write": False}
        for p in paths
        if Path(p).exists()
    ] + [proc_runtime_write_rule()]


def restrict(rules):
    version = abi()
    handled = (1 << 15) - 1  # All filesystem rights through mandatory ABI 3.
    # ABI 5 additionally mediates GPU ioctls: permit only actual device paths.
    if version >= 5:
        handled |= 1 << 15
    attr = Ruleset(handled)
    fd = checked(
        LIBC.syscall(CREATE, ctypes.byref(attr), ctypes.sizeof(attr), 0),
        "landlock ruleset",
    )
    try:
        for item in rules:
            path = Path(item["path"])
            access = READ | (WRITE if item.get("write") else 0)
            if item.get("directory_only"):
                if not path.is_dir():
                    raise ValueError("enumeration-only rule requires a directory")
                access = 1 << 3  # READ_DIR only; no file read, execute or IOCTL.
            if item.get("proc_runtime_write"):
                if (
                    path != Path("/proc")
                    or not path.is_dir()
                    or any(item.get(key) for key in ("write", "directory_only", "device"))
                ):
                    raise ValueError("proc runtime rule requires only the exact procfs root")
                proc_runtime_write_rule()  # Fail closed at each inherited boundary.
                access = (1 << 1) | (1 << 14)  # WRITE_FILE and TRUNCATE only.
            if item.get("device"):
                access = (1 << 1) | (1 << 2) | ((1 << 15) if version >= 5 else 0)
            if not path.is_dir():
                access &= FILE | (1 << 15)
            parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = Beneath(access, parent)
                checked(
                    LIBC.syscall(ADD_RULE, fd, 1, ctypes.byref(rule), 0),
                    "landlock path rule",
                )
            finally:
                os.close(parent)
        checked(LIBC.prctl(38, 1, 0, 0, 0), "PR_SET_NO_NEW_PRIVS")
        checked(LIBC.syscall(RESTRICT, fd, 0), "landlock restrict self")
    finally:
        os.close(fd)


def device_rules():
    # These are container-assigned devices; no host path or device is mounted here.
    paths = ["/dev/null", "/dev/zero", "/dev/random", "/dev/urandom"]
    for pattern in ("nvidia*", "dri/*"):
        paths.extend(str(x) for x in Path("/dev").glob(pattern) if x.is_char_device())
    paths.extend(
        str(x) for x in Path("/dev/nvidia-caps").glob("*") if x.is_char_device()
    )
    # Discovery must still work after the controller applies Landlock. Reading
    # directory entries grants no access to unlisted device/file contents.
    return [{"path": "/dev", "directory_only": True}] + [
        {"path": p, "device": True} for p in paths if Path(p).exists()
    ]


def device_groups():
    return sorted(
        {
            Path(item["path"]).stat().st_gid
            for item in device_rules()
            if item.get("device")
            if Path(item["path"]).stat().st_mode & 0o006 != 0o006
        }
    )


def ipc_objects():
    result = []
    for kind in ("shm", "sem", "msg"):
        lines = Path("/proc/sysvipc", kind).read_text().splitlines()
        names = lines[0].split()
        for line in lines[1:]:
            value = dict(zip(names, line.split(), strict=True))
            result.append((kind, int(value[kind + "id"]), int(value["uid"])))
    return result


def empty_ipc():
    if list(Path("/dev/shm").iterdir()) or ipc_objects():
        raise RuntimeError("dedicated worker IPC namespace is not empty; quarantine")


def remove_ipc(uid):
    if os.getuid() != uid or os.geteuid() == 0:
        raise RuntimeError("IPC cleanup must use the exited project identity")
    for kind, identifier, owner in ipc_objects():
        if owner != uid:
            raise RuntimeError("foreign IPC ownership; quarantine")
        fn = {"shm": LIBC.shmctl, "sem": LIBC.semctl, "msg": LIBC.msgctl}[kind]
        # IPC_RMID = 0; semctl additionally takes a semnum before cmd.
        args = (identifier, 0, 0) if kind != "sem" else (identifier, 0, 0, 0)
        checked(fn(*args), "remove owned SysV IPC object")


def clear_shm(uid):
    for path in Path("/dev/shm").iterdir():
        if path.lstat().st_uid != uid:
            raise RuntimeError("foreign shared-memory file; quarantine")
        os.chown(path, 0, 0, follow_symlinks=False)
        if path.is_dir() and not path.is_symlink():
            reclaim(path)
            shutil.rmtree(path)
        else:
            path.unlink()


def run(policy):
    if (
        os.getuid() != policy["uid"]
        or os.getgid() != policy["uid"]
        or os.geteuid() == 0
    ):
        raise RuntimeError(
            "project identity was not dropped before interpreter startup"
        )
    status = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
    )
    if any(int(status[name].strip(), 16) for name in ("CapEff", "CapPrm", "CapAmb")):
        raise RuntimeError("authored process retained capabilities")
    checked(LIBC.prctl(38, 1, 0, 0, 0), "PR_SET_NO_NEW_PRIVS")
    restrict(policy["rules"])
    os.chdir(policy["cwd"])
    os.execve(policy["command"][0], policy["command"], policy["environment"])


def read_workflow_readiness(path):
    """Bounded, nonblocking read under the owning project's existing identity."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > 4096:
            raise RuntimeError("workflow readiness record is not a bounded regular file")
        raw = stream.read(4097)
        if len(raw) > 4096:
            raise RuntimeError("workflow readiness record exceeded its byte bound")
        return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-fd", type=int)
    parser.add_argument("--cleanup-ipc", type=int)
    parser.add_argument("--read-workflow-ready", type=Path)
    parser.add_argument("--read-workflow-uid", type=int)
    args = parser.parse_args()
    if args.read_workflow_ready is not None:
        if (args.read_workflow_uid is None or args.read_workflow_uid <= 0
                or os.geteuid() != args.read_workflow_uid or os.getegid() != args.read_workflow_uid):
            raise RuntimeError("readiness must be read under its owning project identity")
        raw = read_workflow_readiness(args.read_workflow_ready)
        if raw is None:
            raise SystemExit(3)
        sys.stdout.buffer.write(raw)
        return
    if args.cleanup_ipc is not None:
        return remove_ipc(args.cleanup_ipc)
    if args.policy_fd is None:
        parser.error("--policy-fd is required for project launch")
    with os.fdopen(args.policy_fd, "r") as stream:
        policy = json.load(stream)
    run(policy)


if __name__ == "__main__":
    main()
