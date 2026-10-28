"""Execute the normal portable CLI with kernel-enforced offline descendants.

Only this child is restricted. A separate transfer parent can download inputs
beforehand and upload closed results afterward. No cluster policy is changed.
"""

import argparse
import ctypes
import errno
import hashlib
import json
import os
import platform
import socket
import sys
from pathlib import Path


class SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]


class SockFprog(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ushort), ("filter", ctypes.POINTER(SockFilter))]


def status():
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    return {name: int(fields[name].strip()) for name in ("NoNewPrivs", "Seccomp", "Seccomp_filters") if name in fields}


def restrict_network():
    if platform.machine() != "x86_64":
        raise RuntimeError("The pinned Isaac image and this qualification filter require Linux amd64")
    for fd in Path("/proc/self/fd").iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith("socket:"):
            raise RuntimeError("Refusing offline execution with an inherited socket descriptor")
    # Positive creation control, without sending packets or depending on an external service.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
        pass
    before = status()
    allow, deny = 0x7FFF0000, 0x00050000 | errno.EPERM
    # seccomp_data: nr at 0, arch at 4, first 64-bit argument at 16.
    # Internet/packet/vsock families are denied; Unix/Netlink local IPC remains.
    # Denying io_uring setup/entry prevents asynchronous socket-creation bypasses.
    instructions = [
        (0x20, 0, 0, 4),
        (0x15, 1, 0, 0xC000003E),
        (0x06, 0, 0, 0x80000000),
        (0x20, 0, 0, 0),
        (0x54, 0, 0, 0xBFFFFFFF),
        (0x15, 8, 0, 425),
        (0x15, 7, 0, 426),
        (0x15, 6, 0, 427),
        (0x15, 2, 0, 41),
        (0x15, 1, 0, 53),
        (0x06, 0, 0, allow),
        (0x20, 0, 0, 16),
        (0x15, 2, 0, socket.AF_UNIX),
        (0x15, 1, 0, socket.AF_NETLINK),
        (0x06, 0, 0, deny),
        (0x06, 0, 0, allow),
    ]
    array = (SockFilter * len(instructions))(*(SockFilter(*row) for row in instructions))
    program = SockFprog(len(instructions), array)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    for arguments in ((38, 1, 0, 0, 0), (22, 2, ctypes.addressof(program), 0, 0)):
        if libc.prctl(*arguments):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
    denied = []
    for name, family in (("ipv4", socket.AF_INET), ("ipv6", socket.AF_INET6),
                         ("packet", socket.AF_PACKET), ("vsock", getattr(socket, "AF_VSOCK", 40))):
        try:
            connection = socket.socket(family, socket.SOCK_STREAM)
        except OSError as error:
            if error.errno != errno.EPERM:
                raise RuntimeError(f"Offline probe {name} failed for a different reason") from error
            denied.append(name)
        else:
            connection.close()
            raise RuntimeError(f"Offline socket filter did not block {name}")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM):
        pass
    after = status()
    if after["NoNewPrivs"] != 1 or after["Seccomp"] != 2:
        raise RuntimeError("Kernel did not retain the requested offline filter")
    if "Seccomp_filters" in before and after["Seccomp_filters"] <= before["Seccomp_filters"]:
        raise RuntimeError("No additional kernel filter was installed")
    return {"schema": "isaac-offline-execution/v1", "socket_creation_before_filter": "passed",
            "denied_socket_families": denied, "local_unix_socket_creation": "passed",
            "kernel_before": before, "kernel_after": after,
            "filter_sha256": hashlib.sha256(bytes(array)).hexdigest(),
            "scope": "Normal portable CLI and all descendants; transfer parent remains unrestricted"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        parser.error("A normal portable command is required after --")
    proof = restrict_network()
    proof["command_sha256"] = hashlib.sha256(json.dumps(command).encode()).hexdigest()
    with args.receipt.open("x") as stream:
        json.dump(proof, stream, indent=2)
        stream.write("\n")
    print("ISAAC_OFFLINE_EXEC_READY=" + json.dumps(proof, sort_keys=True), flush=True)
    os.execv(command[0], command)


if __name__ == "__main__":
    main()
