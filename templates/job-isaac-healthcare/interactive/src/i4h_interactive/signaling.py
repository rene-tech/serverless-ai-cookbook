"""Noncredential NVIDIA WebRTC v2 viewer handshake, bound to an owned session.

The SDK supplies four identity fields and optional reconnect=1 on /sign_in.
They are protocol metadata,
never authority: every caller must separately validate its existing owner,
origin, session, capability and deadline before using this module's result.
"""

from __future__ import annotations

import re
import time
from urllib.parse import parse_qsl, urlencode

SIGNALING_HEADER = "x-isaac-signaling"
SIGNALING_KEYS = ("peer_id", "version", "peer_role", "pairing_id")
HANDOFF_CLOSE_CODE = 4001
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
VIEWER_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; media-src 'self' blob:; frame-ancestors 'self'; "
    "object-src 'none'; base-uri 'none'; worker-src 'self' blob:"
)


def validate_signaling(value, session_id):
    """Return a canonical map; reject unsupported roles, ambiguity or another SID."""
    if not isinstance(session_id, str) or not IDENTITY.fullmatch(session_id):
        raise PermissionError("an authenticated session identity is required")
    if not isinstance(value, dict) or set(value) not in (
        set(SIGNALING_KEYS), set(SIGNALING_KEYS) | {"reconnect"}
    ):
        raise PermissionError("exact WebRTC viewer handshake fields are required")
    if any(not isinstance(item, str) for item in value.values()):
        raise PermissionError("WebRTC handshake fields must be text")
    if (
        not IDENTITY.fullmatch(value["peer_id"])
        or value["version"] != "2"
        or value["peer_role"] != "1"
        or value["pairing_id"] != session_id
        or ("reconnect" in value and value["reconnect"] != "1")
    ):
        raise PermissionError("WebRTC handshake differs from the owned session")
    return {name: value[name] for name in (*SIGNALING_KEYS, "reconnect") if name in value}


def parse_signaling_query(items, session_id):
    """Validate multi-items before collapsing them, preserving duplicate rejection."""
    pairs = list(items)
    if len(pairs) not in (len(SIGNALING_KEYS), len(SIGNALING_KEYS) + 1):
        raise PermissionError("exact WebRTC viewer handshake fields are required")
    if any(not isinstance(pair, tuple | list) or len(pair) != 2 for pair in pairs):
        raise PermissionError("invalid WebRTC handshake query")
    if len({pair[0] for pair in pairs}) != len(pairs):
        raise PermissionError("duplicate WebRTC handshake fields are forbidden")
    return validate_signaling(dict(pairs), session_id)


def encode_signaling(value, session_id):
    return urlencode(validate_signaling(value, session_id))


def parse_signaling_header(value, session_id):
    """Decode a bounded private canonical header, never a client-selected URL."""
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise PermissionError("a bounded WebRTC handshake header is required")
    try:
        items = parse_qsl(value, keep_blank_values=True, strict_parsing=True)
    except (ValueError, UnicodeError):
        raise PermissionError("invalid WebRTC handshake header") from None
    result = parse_signaling_query(items, session_id)
    if value != encode_signaling(result, session_id):
        raise PermissionError("canonical WebRTC handshake encoding is required")
    return result


def kit_signaling_path(value, session_id):
    return "/sign_in?" + encode_signaling(value, session_id)


class SignalingPeer:
    """One authenticated logical peer across the SDK's 4001 socket handoff.

    The caller supplies existing session bounds and separately authenticates
    every transport. Reconnect metadata never grants a new viewer or lease.
    Socket serialization belongs to the caller; this class has no side effects.
    """

    def __init__(self, session_id, deadline_at, startup_timeout_s, *, clock=time.time):
        self.session_id = session_id
        self.deadline_at = deadline_at
        self.startup_timeout_s = startup_timeout_s
        self.clock = clock
        self.clear()

    def clear(self):
        self.identity = None
        self.phase = "detached"
        self.handoff_until = None
        self.established = False

    def expire(self):
        now = self.clock()
        if now >= self.deadline_at or (
            self.phase == "handoff" and now >= self.handoff_until
        ):
            self.clear()
        return self.phase

    def matches(self, value):
        value = validate_signaling(value, self.session_id)
        return self.identity == {name: value[name] for name in SIGNALING_KEYS}

    @property
    def attached(self):
        self.expire()
        return self.established and self.phase != "detached"

    def begin(self, value):
        value = validate_signaling(value, self.session_id)
        self.expire()
        if self.clock() >= self.deadline_at:
            raise PermissionError("native session deadline has elapsed")
        if value.get("reconnect") == "1":
            if self.phase != "handoff" or not self.matches(value):
                raise PermissionError("matching observed SDK handoff required")
        elif self.phase != "detached":
            raise PermissionError("another signaling peer owns this session")
        else:
            self.identity = {name: value[name] for name in SIGNALING_KEYS}
            self.established = False
        self.phase = "connecting"
        self.handoff_until = None
        return value

    def connected(self):
        if self.phase != "connecting" or self.clock() >= self.deadline_at:
            self.clear()
            raise PermissionError("signaling connection is no longer admissible")
        self.phase = "attached"
        self.established = True

    def closed(self, code):
        if code == HANDOFF_CLOSE_CODE and self.attached:
            self.phase = "handoff"
            self.handoff_until = min(
                self.deadline_at, self.clock() + self.startup_timeout_s
            )
        else:
            self.clear()
