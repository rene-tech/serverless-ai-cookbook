"""Noncredential NVIDIA WebRTC v2 viewer handshake, bound to an owned session.

The SDK supplies these four fields on /sign_in. They are protocol metadata,
never authority: every caller must separately validate its existing owner,
origin, session, capability and deadline before using this module's result.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode

SIGNALING_HEADER = "x-isaac-signaling"
SIGNALING_KEYS = ("peer_id", "version", "peer_role", "pairing_id")
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
    if not isinstance(value, dict) or set(value) != set(SIGNALING_KEYS):
        raise PermissionError("exact WebRTC viewer handshake fields are required")
    if any(not isinstance(value[name], str) for name in SIGNALING_KEYS):
        raise PermissionError("WebRTC handshake fields must be text")
    if (
        not IDENTITY.fullmatch(value["peer_id"])
        or value["version"] != "2"
        or value["peer_role"] != "1"
        or value["pairing_id"] != session_id
    ):
        raise PermissionError("WebRTC handshake differs from the owned session")
    return {name: value[name] for name in SIGNALING_KEYS}


def parse_signaling_query(items, session_id):
    """Validate multi-items before collapsing them, preserving duplicate rejection."""
    pairs = list(items)
    if len(pairs) != len(SIGNALING_KEYS):
        raise PermissionError("exact WebRTC viewer handshake fields are required")
    if any(not isinstance(pair, (tuple, list)) or len(pair) != 2 for pair in pairs):
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
