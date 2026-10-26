"""Cambridge's observed HTML login and read-only CamSol form inspection.

This is an external web-service connector, not a native CamSol API. No
calculation route is called or inferred. Credentials and cookies stay private.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass, field
import hashlib
import hmac
from html.parser import HTMLParser
import secrets
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

ORIGIN = "https://www-cohsoftware.ch.cam.ac.uk"
LOGIN = "/index.php/login"
AUTHENTICATE = "/index.php/login/authenticate/concrete"
MODES = {
    "intrinsic": "/index.php/camsolintrinsic",
    "ph-dependent": "/index.php/camsolph",
    "ptm": "/index.php/camsolptm",
    "structurally-corrected": "/index.php/camsolstrucorr",
    "combination-design": "/index.php/camsolcombination",
}


class ProviderBoundary(Exception):
    """Only a fixed, non-sensitive code crosses the tool boundary."""


def same_origin(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == urlsplit(ORIGIN).hostname
                and parsed.port in (None, 443) and parsed.username is None
                and parsed.password is None)
    except ValueError:
        return False


def public_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms: list[dict] = []
        self.current = None
        self.challenge = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        marker = " ".join(str(attrs.get(k, "")) for k in ("id", "name", "class", "src"))
        self.challenge |= any(word in marker.lower() for word in ("captcha", "turnstile", "challenge-platform"))
        if tag == "form":
            self.current = {"action": attrs.get("action", ""),
                            "method": attrs.get("method", "get").upper(), "fields": []}
            self.forms.append(self.current)
        if self.current is not None and tag in ("input", "select", "textarea", "button") and attrs.get("name"):
            self.current["fields"].append({"name": attrs["name"], "type": attrs.get("type", tag),
                                           "value": attrs.get("value", "")})

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


def parsed_forms(response: httpx.Response) -> Forms:
    if response.status_code != 200:
        raise ProviderBoundary("access_denied" if response.status_code in (401, 403) else "provider_unavailable")
    if "text/html" not in response.headers.get("content-type", "").lower():
        raise ProviderBoundary("unexpected_provider_content")
    forms = Forms()
    forms.feed(response.text)
    if forms.challenge:
        raise ProviderBoundary("manual_challenge_required")
    return forms


@dataclass(repr=False, frozen=True)
class Credentials:
    principal: str
    email: str = field(repr=False)
    password: str = field(repr=False)

    @classmethod
    def from_headers(cls, headers):
        values = [headers.get(key, "") for key in
                  ("x-scientific-user", "x-camsol-email", "x-camsol-password")]
        try:
            values[1:] = [base64.b64decode(value, validate=True).decode("utf-8") for value in values[1:]]
        except (binascii.Error, UnicodeError, ValueError):
            raise ProviderBoundary("private_header_encoding_required") from None
        if any(not value.strip() or any(c in value for c in ("\r", "\n", "\x00")) for value in values):
            raise ProviderBoundary("connection_settings_required")
        return cls(*values)


class Session:
    def __init__(self, *, transport=None):
        self.client = httpx.AsyncClient(transport=transport, timeout=30, follow_redirects=False,
                                       trust_env=False, headers={"User-Agent": "ScientificAI-CamSol-Connection/1"})
        self.lock = asyncio.Lock()
        self.connected = False

    async def close(self):
        self.connected = False
        await self.client.aclose()

    async def fetch(self, path: str, *, data=None) -> httpx.Response:
        url = urljoin(ORIGIN, path)
        method = "POST" if data is not None else "GET"
        for _ in range(6):
            if not same_origin(url):
                raise ProviderBoundary("external_redirect_requires_review")
            # The sole permitted POST is the login form actually observed upstream.
            if method == "POST" and url != ORIGIN + AUTHENTICATE:
                raise ProviderBoundary("login_contract_changed")
            try:
                async with self.client.stream(method, url, data=data, follow_redirects=False) as stream:
                    raw = bytearray()
                    async for chunk in stream.aiter_bytes():
                        raw.extend(chunk)
                        # Bounds connection-page inspection, never scientific inputs/outputs.
                        if len(raw) > 2 * 1024 * 1024:
                            raise ProviderBoundary("provider_page_too_large")
                    response = httpx.Response(stream.status_code, headers=stream.headers,
                                              content=bytes(raw), request=stream.request)
            except httpx.HTTPError:
                raise ProviderBoundary("provider_unavailable") from None
            if not response.is_redirect:
                return response
            location = response.headers.get("location")
            if not location:
                raise ProviderBoundary("invalid_provider_redirect")
            url = urljoin(str(response.url), location)
            # Never resend a password body, even to the same origin.
            if method == "POST" and response.status_code not in (301, 302, 303):
                raise ProviderBoundary("login_redirect_requires_review")
            method, data = "GET", None
        raise ProviderBoundary("provider_redirect_limit")

    async def inspect(self, mode: str) -> dict:
        response = await self.fetch(MODES[mode])
        forms = parsed_forms(response)
        path = urlsplit(str(response.url)).path.rstrip("/")
        fields = [field for form in forms.forms for field in form["fields"]]
        if path.endswith(("/login", "/user_not_registered")) or any(f["type"] == "password" for f in fields):
            was_connected = self.connected
            self.connected = False
            self.client.cookies.clear()
            raise ProviderBoundary("session_expired_reconnect" if was_connected else "authentication_required")
        # A public landing page alone is not proof of a working account.
        if path != MODES[mode] or not forms.forms:
            raise ProviderBoundary("authenticated_form_not_observed")
        self.connected = True
        return {"status": "authenticated_form_observed", "connected": True, "mode": mode,
                "page": public_url(str(response.url)),
                "page_sha256": hashlib.sha256(response.content).hexdigest(),
                "forms": [{"action": public_url(urljoin(str(response.url), form["action"])),
                           "same_origin": same_origin(urljoin(str(response.url), form["action"])),
                           "method": form["method"],
                           "fields": [{"name": f["name"], "type": f["type"]} for f in form["fields"]]}
                          for form in forms.forms]}

    async def connect(self, credentials: Credentials) -> dict:
        self.connected = False
        self.client.cookies.clear()
        response = await self.fetch(LOGIN)
        forms = parsed_forms(response)
        matches = [form for form in forms.forms
                   if urljoin(str(response.url), form["action"]) == ORIGIN + AUTHENTICATE
                   and form["method"] == "POST"]
        if len(matches) != 1:
            raise ProviderBoundary("login_contract_changed")
        fields = matches[0]["fields"]
        tokens = [f["value"] for f in fields if f["name"] == "ccm_token" and f["type"] == "hidden"]
        if (len(tokens) != 1 or not tokens[0] or
                {f["name"] for f in fields} != {"uName", "uPassword", "uMaintainLogin", "ccm_token"}):
            raise ProviderBoundary("login_contract_changed")
        result = await self.fetch(AUTHENTICATE, data={"uName": credentials.email,
                                                     "uPassword": credentials.password,
                                                     "ccm_token": tokens[0]})
        after = parsed_forms(result)
        if any(f["type"] == "password" for form in after.forms for f in form["fields"]):
            raise ProviderBoundary("login_not_accepted")
        # Authentication is claimed only after observing a protected algorithm form.
        return await self.inspect("intrinsic")


class Connections:
    """Cookie jars cannot cross LibreChat principals or credential rotations."""
    def __init__(self, *, transport=None):
        self._salt = secrets.token_bytes(32)
        self._sessions: dict[bytes, Session] = {}
        self._transport = transport
        self._connect_lock = asyncio.Lock()

    def key(self, credentials: Credentials) -> bytes:
        import json
        value = json.dumps([credentials.principal, credentials.email, credentials.password]).encode()
        return hmac.digest(self._salt, value, "sha256")

    async def call(self, action: str, credentials: Credentials, mode="intrinsic") -> dict:
        receipt = {"provider": "cambridge-camsol-web", "external_service": ORIGIN,
                   "scientific_data_sent": False, "submission_available": False}
        key = self.key(credentials)
        try:
            if action == "connect":
                # No blind authentication retry; concurrent explicit connects serialize.
                async with self._connect_lock:
                    session = self._sessions.get(key)
                    if session is None:
                        session = Session(transport=self._transport)
                    async with session.lock:
                        try:
                            result = await session.connect(credentials)
                        except BaseException:
                            await session.close()
                            self._sessions.pop(key, None)
                            raise
                        self._sessions[key] = session
                return {**receipt, **result}
            if action not in ("status", "inspect") or mode not in MODES:
                raise ProviderBoundary("unsupported_inspection")
            session = self._sessions.get(key)
            if session is None:
                raise ProviderBoundary("not_connected")
            async with session.lock:
                try:
                    result = await session.inspect(mode)
                except ProviderBoundary as error:
                    if str(error) in ("authentication_required", "session_expired_reconnect"):
                        await session.close()
                        self._sessions.pop(key, None)
                        raise ProviderBoundary("session_expired_reconnect") from None
                    raise
            return {**receipt, **result}
        except ProviderBoundary as error:
            known_disconnected = str(error) in {"not_connected", "authentication_required", "session_expired_reconnect",
                                               "login_not_accepted", "manual_challenge_required", "login_contract_changed"}
            return {**receipt, "status": str(error), "connected": False if known_disconnected else None,
                    "next_step": "Check CamSol in MCP Settings; reconnect explicitly after resolving the reported condition."}

    async def close(self):
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()
