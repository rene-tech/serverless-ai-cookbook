"""Operator-selected launch settings, with no fixture or workflow allowlist."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43,}\Z")


def integer(value, name, low=1, high=None):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or int(value) != value
    ):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if value < low or (high is not None and value > high):
        raise ValueError(f"{name} is outside its technical range")
    return value


def validate(config):
    if not isinstance(config, dict) or not SESSION.fullmatch(
        config.get("session_id", "")
    ):
        raise ValueError("an allocated session identity is required")
    command = config.get("command")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(x, str) or not x or "\0" in x for x in command)
    ):
        raise ValueError("command must be an argv list; no shell command is accepted")
    if not Path(command[0]).is_absolute():
        raise ValueError("the installed executable must be absolute")
    if not Path(config.get("work_dir", "")).is_absolute():
        raise ValueError("an isolated absolute work directory is required")
    if config.get("startup_readiness_file") is not None:
        ready = Path(config["startup_readiness_file"])
        if not ready.is_absolute() or ready.parent != Path(config["work_dir"]):
            raise ValueError("workflow readiness belongs to this process work directory")
    origin = urlsplit(config.get("browser_origin", ""))
    if (
        origin.scheme != "https"
        or not origin.netloc
        or origin.path not in ("", "/")
        or origin.query
        or origin.fragment
        or origin.username
    ):
        raise ValueError("the exact HTTPS browser origin is required")
    ipaddress.ip_address(config["media_host"])
    for key in ("signal_port", "media_port", "proxy_port"):
        integer(config[key], key, 1, 65535)
    if len({int(config[k]) for k in ("signal_port", "media_port", "proxy_port")}) != 3:
        raise ValueError("each listener must use its own port")
    deadline = config.get("deadline_at")
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError("the admitted native deadline is required")
    integer(config["stop_grace_seconds"], "stop_grace_seconds")
    integer(config["startup_timeout_seconds"], "startup_timeout_seconds")
    if config.get("network_mode") not in {
        "authenticated-private-network",
        "turn-relay",
    }:
        raise ValueError(
            "raw public WebRTC listeners are not a supported access boundary"
        )
    if config.get("network_mode") == "turn-relay":
        turn = urlsplit(config.get("turn_url", ""))
        if turn.scheme != "turns" or not turn.path or "transport=tcp" not in turn.query:
            raise ValueError(
                "TURN mode requires an authenticated turns: TLS/TCP endpoint"
            )
    return config


def authenticate(headers, config, token):
    """Pinned NVIDIA 6.7.0 wire format, or an ordinary non-browser bearer."""
    if headers.get("origin") not in (None, config["browser_origin"]):
        raise PermissionError("origin does not match this session")
    protocols = [
        x.strip()
        for x in headers.get("sec-websocket-protocol", "").split(",")
        if x.strip()
    ]
    wire_auth = [
        x.removeprefix("Authorization.Bearer.")
        for x in protocols
        if x.startswith("Authorization.Bearer.")
    ]
    wire_sid = [
        x.removeprefix("x-nv-sessionid.")
        for x in protocols
        if x.startswith("x-nv-sessionid.")
    ]
    bearer = headers.get("authorization", "")
    if bearer:
        supplied = (
            bearer.removeprefix("Bearer ") if bearer.startswith("Bearer ") else ""
        )
        if wire_auth:
            raise PermissionError("ambiguous credentials")
    else:
        if (
            wire_sid != [config["session_id"]]
            or len(wire_auth) != 1
            or headers.get("origin") != config["browser_origin"]
        ):
            raise PermissionError("authenticated session signaling required")
        supplied = wire_auth[0]
    if not TOKEN.fullmatch(token) or not hmac.compare_digest(supplied, token):
        raise PermissionError("session capability rejected")
    if wire_sid and wire_sid != [config["session_id"]]:
        raise PermissionError("another session was requested")
    return [x for x in protocols if not x.startswith("Authorization.Bearer.")]


def turn_credentials(secret: bytes, session_id: str, deadline_at: float, url: str):
    """Coturn REST credentials expire at the existing native lease deadline."""
    if len(secret) < 32 or not SESSION.fullmatch(session_id):
        raise ValueError("operator TURN secret and admitted session required")
    username = f"{int(deadline_at)}:{session_id}"
    credential = base64.b64encode(
        hmac.new(secret, username.encode(), hashlib.sha1).digest()
    ).decode()
    return {
        "iceTransportPolicy": "relay",
        "iceServers": [{"urls": [url], "username": username, "credential": credential}],
    }


def kit_arguments(config, *, width=1920, height=1080, fps=60):
    """Real official Kit settings; call before AppLauncher initializes Kit."""
    width, height = integer(width, "width"), integer(height, "height")
    fps = integer(fps, "fps")
    prefix = "--/exts/omni.kit.livestream.app/primaryStream/"
    return [
        prefix + "streamType=webrtc",
        prefix + "publicIp=" + config["media_host"],
        prefix
        + f"signalPort={integer(config['signal_port'], 'signal_port', 1, 65535)}",
        prefix + f"streamPort={integer(config['media_port'], 'media_port', 1, 65535)}",
        prefix + f"targetFps={fps}",
        prefix + "enableEventTracing=false",
        f"--/app/window/width={width}",
        f"--/app/window/height={height}",
    ]
