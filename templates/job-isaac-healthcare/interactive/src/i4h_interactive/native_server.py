"""Deployable native worker using the same portable project/runtime implementation."""

import argparse
import hashlib
import json
import os
import time
import socket
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .contract import kit_arguments
from .native import NativeSessionAPI, application
from .delivery import deliver
from . import isolation


def own_pod_ip(hostname=None, hosts_file=Path("/etc/hosts")):
    """Use Kubernetes' own hostname mapping, never DNS or a guessed node IP."""
    hostname = hostname or socket.gethostname()
    addresses = set()
    for line in Path(hosts_file).read_text().splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) > 1 and hostname in fields[1:]:
            address = ipaddress.ip_address(fields[0])
            if (
                address.version == 4
                and not address.is_loopback
                and not address.is_unspecified
            ):
                addresses.add(str(address))
    if len(addresses) != 1:
        raise RuntimeError(
            "own Pod hostname must map to one unambiguous IPv4 in /etc/hosts"
        )
    return addresses.pop()


def load_settings(path, environ=None):
    """Read baked nonsecret settings and the operator's exact image binding.

    An image cannot contain its own manifest digest. Native's ordinary env
    projection supplies that nonsecret pin after publication, without needing
    an unsupported arbitrary config volume or exposing it to authored code.
    """
    environ = os.environ if environ is None else environ
    config = json.loads(Path(path).read_text())
    if bool(config.get("image")) == bool(config.get("image_env")):
        raise ValueError("configure one immutable image binding source")
    if config.get("image_env"):
        config["image"] = environ[config["image_env"]]
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", config["image"]):
        raise ValueError("worker requires the full immutable published image binding")
    if not isinstance(config.get("runtime_python"), str) or not Path(
        config["runtime_python"]
    ).is_absolute():
        raise ValueError("the installed Arena interpreter must be an absolute path")
    return config


def workflow_command(settings, spec_path):
    """Keep authored imports in Arena, outside the transport dependency environment."""
    return [
        settings["runtime_python"],
        "-I",
        "-B",
        str(Path(__file__).with_name("workflow.py")),
        "--spec",
        str(spec_path),
    ]


def consume_start_key(config, environ=None):
    environ = os.environ if environ is None else environ
    if bool(config.get("start_key_file")) == bool(config.get("start_key_env")):
        raise ValueError("configure one model-scoped signing-key source")
    key = (
        Path(config["start_key_file"]).read_text().strip()
        if config.get("start_key_file")
        else environ.pop(config["start_key_env"])
    )
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("model-scoped signing key must be 32 bytes encoded as hex")
    return bytes.fromhex(key)


def preparer(settings):
    def prepare(start, owner, sid, deadline, display, cancelled):
        def current():
            if cancelled.is_set() or time.time() >= deadline:
                raise RuntimeError("native session ended during project preparation")

        current()
        if settings.get("require_output_delivery", True):
            output = start.get("output", {})
            if any(
                urlsplit(output.get(key, "")).scheme != "https"
                for key in ("archive_put_url", "receipt_put_url")
            ):
                raise ValueError(
                    "owner-bound output archive and receipt targets are required"
                )
        project = start["project"]
        if (
            urlsplit(project["url"]).scheme != "https"
            or type(project["size_bytes"]) is not int
            or project["size_bytes"] <= 0
            or len(project["sha256"]) != 64
        ):
            raise ValueError(
                "an App-authorized immutable project descriptor is required"
            )
        work_root = Path(settings["work_root"])
        work_root.mkdir(parents=True, exist_ok=True, mode=0o711)
        uid = isolation.new_identity(work_root)
        root = work_root / sid
        root.mkdir(exist_ok=False, mode=0o711)
        project_root = root / "project"
        project_root.mkdir(mode=0o770)
        project_root.chmod(0o770)
        os.chown(project_root, 0, uid)
        ipc_parent = Path(settings["ipc_root"])
        ipc_parent.mkdir(parents=True, exist_ok=True, mode=0o711)
        ipc_root = ipc_parent / str(uid)
        ipc_root.mkdir(mode=0o700)
        isolation.own(ipc_root, uid)
        archive = project_root / "project.tar"
        digest, count = hashlib.sha256(), 0
        with httpx.stream(
            "GET",
            project["url"],
            timeout=min(60, max(0.001, deadline - time.time())),
            follow_redirects=False,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError("authorized project download failed")
            with archive.open("xb") as target:
                for chunk in response.iter_bytes():
                    current()
                    count += len(chunk)
                    if count > project["size_bytes"]:
                        raise ValueError("project exceeds its authorized byte count")
                    digest.update(chunk)
                    target.write(chunk)
        if count != project["size_bytes"] or digest.hexdigest() != project["sha256"]:
            raise ValueError("project checksum or byte count differs")
        archive.chmod(0o440)
        os.chown(archive, 0, uid)
        config = {
            **settings["session"],
            "session_id": sid,
            "deadline_at": deadline,
            "work_dir": str(project_root / "process"),
            "startup_readiness_file": str(project_root / "process" / "startup-ready.json"),
            "log_file": str(root / "execution.log"),
            "closeout_file": str(root / "process-closeout.json"),
            "cleanup_witness": str(project_root / "workflow-closeout.json"),
            "pid_namespace_guard": True,
            "isolation": {
                "root": str(project_root),
                "uid": uid,
                "runtime_roots": settings["runtime_roots"],
                "extra_write_roots": [str(ipc_root)],
            },
            "environment": {
                **settings.get("runtime_environment", {}),
                "I4H_BUS_ROOT": str(ipc_root),
            },
        }
        if config.get("media_host") == "POD_IP":
            config["media_host"] = own_pod_ip()
        spec = {
            "root": str(project_root),
            "archive": str(archive),
            "base_root": settings.get("base_root", "/opt/i4h"),
            "parameters": start["parameters"],
            "session_id": sid,
            "kit_arguments": kit_arguments(config, **display),
            "stop_grace_seconds": config["stop_grace_seconds"],
        }
        spec_path = project_root / "workflow.json"
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")
        spec_path.chmod(0o440)
        os.chown(spec_path, 0, uid)
        config["command"] = workflow_command(settings, spec_path)
        if start.get("output"):
            config["_finalize"] = lambda: deliver(
                root, sid, start["output"], data_root=project_root / "output"
            )
        return config

    return prepare


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_settings(args.config)
    key = consume_start_key(config)
    key_file = config.get("start_key_file")
    authority = [config["pod_token_file"], *([key_file] if key_file else [])]
    # Authority must never be mounted within a readable runtime rule.
    for rule in isolation.runtime_rules(config["runtime_roots"]):
        for path in authority:
            if Path(path).resolve().is_relative_to(Path(rule["path"])):
                raise ValueError(
                    "controller authority overlaps an authored runtime rule"
                )
    work = [Path(config[name]) for name in ("work_root", "ipc_root")]
    for path in work:
        path.mkdir(parents=True, exist_ok=True, mode=0o711)
    isolation.controller_boundary(
        runtime_roots=config["runtime_roots"],
        work_roots=work,
        authority_roots=sorted({str(Path(p).parent) for p in authority}),
    )
    isolation.empty_ipc()
    api = NativeSessionAPI(config["native_origin"], config["pod_token_file"])
    app = application(
        api,
        model_id=config["model_id"],
        expected_image=config["image"],
        runtime_revision=config["runtime_revision"],
        start_key=key,
        prepare_start=preparer(config),
        poll_seconds=config["poll_seconds"],
    )
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config["port"],
        access_log=False,
        log_level="warning",
        ws_max_size=1024 * 1024,
        ws_max_queue=2,
    )


if __name__ == "__main__":
    main()
