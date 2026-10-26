"""Offline synthetic provider and actual MCP transport tests; no Cambridge login."""
import base64
import asyncio
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs

import httpx

from web import AUTHENTICATE, Credentials, Connections, LOGIN, MODES, ORIGIN


def html(body, **kwargs):
    return httpx.Response(200, text=body, headers={"content-type": "text/html", **kwargs})


def login(token="fresh-csrf", extra=""):
    return html(f'<form method="post" action="{ORIGIN}{AUTHENTICATE}">'
                '<input name="uName"><input type="password" name="uPassword">'
                '<input type="checkbox" name="uMaintainLogin">'
                f'<input type="hidden" name="ccm_token" value="{token}">{extra}</form>')


class Provider:
    def __init__(self):
        self.requests = []
        self.next_id = 0
        self.expired = False

    def __call__(self, request):
        self.requests.append(request)
        path = request.url.path
        if path == LOGIN:
            self.next_id += 1
            return login(str(self.next_id))
        if path == AUTHENTICATE:
            fields = parse_qs(request.content.decode())
            assert fields["ccm_token"] == [str(self.next_id)]
            assert "uMaintainLogin" not in fields
            return httpx.Response(303, headers={"location": MODES["intrinsic"],
                                                "set-cookie": f"CONCRETE=private-cookie-{self.next_id}; Path=/; Secure; HttpOnly"})
        if path in MODES.values():
            if self.expired or "CONCRETE=private-cookie-" not in request.headers.get("cookie", ""):
                return httpx.Response(302, headers={"location": "/index.php/user_not_registered"})
            return html('<form method="post" action="/observed-only-calculation">'
                        '<textarea name="sequence"></textarea><input type="hidden" name="token" value="private-form-token"></form>')
        if path == "/index.php/user_not_registered":
            return html("Account needed")
        raise AssertionError("Unobserved path requested")


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.provider = Provider()
        self.connections = Connections(transport=httpx.MockTransport(self.provider))
        self.a = Credentials("user-a", "research.login", "private%2F& +value")
        self.b = Credentials("user-b", "b@example.test", "private-other")

    async def asyncTearDown(self):
        await self.connections.close()

    async def test_dynamic_csrf_one_post_exact_password_and_no_secrets_in_receipt(self):
        for _ in range(2):
            result = await self.connections.call("connect", self.a)
            self.assertEqual(result["status"], "authenticated_form_observed")
            text = json.dumps(result)
            for secret in (self.a.email, self.a.password, "private-cookie", "private-form-token"):
                self.assertNotIn(secret, text)
        posts = [r for r in self.provider.requests if r.method == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertEqual([parse_qs(r.content.decode())["ccm_token"] for r in posts], [["1"], ["2"]])
        self.assertEqual(parse_qs(posts[0].content.decode())["uPassword"], [self.a.password])
        self.assertEqual({r.url.path for r in posts}, {AUTHENTICATE})

    async def test_principal_credential_isolation_and_rotation(self):
        await self.connections.call("connect", self.a)
        await self.connections.call("connect", self.b)
        await self.connections.call("inspect", self.a, "ph-dependent")
        a_cookie = self.provider.requests[-1].headers["cookie"]
        await self.connections.call("inspect", self.b, "ph-dependent")
        self.assertNotEqual(a_cookie, self.provider.requests[-1].headers["cookie"])
        count = len(self.provider.requests)
        for changed in (Credentials("user-b", self.a.email, self.a.password),
                        Credentials(self.a.principal, self.a.email, "rotated")):
            result = await self.connections.call("status", changed)
            self.assertEqual(result["status"], "not_connected")
        self.assertEqual(count, len(self.provider.requests))

    async def test_expiry_never_relogs_in(self):
        await self.connections.call("connect", self.a)
        self.provider.expired = True
        result = await self.connections.call("status", self.a)
        self.assertEqual(result["status"], "session_expired_reconnect")
        self.assertEqual(len([r for r in self.provider.requests if r.method == "POST"]), 1)
        self.assertEqual((await self.connections.call("status", self.a))["status"], "not_connected")

    async def run_provider(self, handler):
        pool = Connections(transport=httpx.MockTransport(handler))
        try:
            return await pool.call("connect", self.a)
        finally:
            await pool.close()

    async def test_external_redirect_and_post307_are_not_followed(self):
        for redirect, expected in (("https://other.test/steal", "external_redirect_requires_review"),
                                   (ORIGIN + AUTHENTICATE, "login_redirect_requires_review")):
            requests = []
            def provider(request):
                requests.append(request)
                if request.url.path == LOGIN:
                    return login()
                return httpx.Response(307 if redirect.startswith(ORIGIN) else 303,
                                      headers={"location": redirect})
            result = await self.run_provider(provider)
            self.assertEqual(result["status"], expected)
            self.assertEqual([r.method for r in requests], ["GET", "POST"])
            self.assertTrue(all(str(r.url).startswith(ORIGIN) for r in requests))

    async def test_challenge_and_changed_form_stop_before_post(self):
        for extra, expected in (('<input name="captcha">', "manual_challenge_required"),
                                ('<input name="new_contract_field">', "login_contract_changed")):
            methods = []
            def provider(request):
                methods.append(request.method)
                return login(extra=extra)
            self.assertEqual((await self.run_provider(provider))["status"], expected)
            self.assertEqual(methods, ["GET"])

    async def test_rejected_login_is_not_retried(self):
        methods = []
        def provider(request):
            methods.append(request.method)
            return login()
        result = await self.run_provider(provider)
        self.assertEqual(result["status"], "login_not_accepted")
        self.assertEqual(methods, ["GET", "POST"])

    async def test_unavailable_has_sanitized_cause(self):
        def provider(request):
            raise httpx.ConnectError("sensitive-body-or-cookie", request=request)
        result = await self.run_provider(provider)
        self.assertEqual(result["status"], "provider_unavailable")
        self.assertNotIn("sensitive", json.dumps(result))

    async def test_cancelled_login_leaves_no_cached_connection(self):
        entered = asyncio.Event()
        requests = []
        async def provider(request):
            requests.append(request)
            if request.url.path == LOGIN:
                return login()
            entered.set()
            await asyncio.Event().wait()
        pool = Connections(transport=httpx.MockTransport(provider))
        task = asyncio.create_task(pool.call("connect", self.a))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual((await pool.call("status", self.a))["status"], "not_connected")
        self.assertEqual([r.method for r in requests], ["GET", "POST"])
        await pool.close()


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_schema_and_loopback_guards(self):
        from server import create_server
        provider = Provider()
        pool = Connections(transport=httpx.MockTransport(provider))
        _, app = create_server(pool)
        headers = {"accept": "application/json, text/event-stream", "content-type": "application/json",
                   "x-scientific-user": "user-a", "x-camsol-email": base64.b64encode(b"a@example.test").decode(),
                   "x-camsol-password": base64.b64encode("private$&-$$-雪".encode()).decode()}
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)),
                                         base_url="http://127.0.0.1:8786") as client:
                body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
                response = await client.post("/mcp", headers=headers, json=body)
                self.assertEqual(response.status_code, 200, response.text)
                tools = response.json()["result"]["tools"]
                self.assertEqual({t["name"] for t in tools},
                                 {"connect_camsol", "camsol_connection_status", "inspect_camsol_mode"})
                for tool in tools:
                    self.assertNotIn("password", json.dumps(tool["inputSchema"]).lower())
                    self.assertNotIn("email", json.dumps(tool["inputSchema"]).lower())
                    self.assertNotIn("ctx", tool["inputSchema"].get("properties", {}))
                self.assertEqual(provider.requests, [])
                for changed in ({"origin": "http://localhost"}, {"host": "other.test"},
                                {"x-camsol-password": ""}):
                    denied = await client.post("/mcp", headers={**headers, **changed}, json=body)
                    self.assertEqual(denied.status_code, 403)
                body.update(method="tools/call", params={"name": "connect_camsol", "arguments": {}})
                response = await client.post("/mcp", headers=headers, json=body)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn("authenticated_form_observed", response.text)
                self.assertEqual(parse_qs(next(r for r in provider.requests if r.method == "POST").content.decode())["uPassword"],
                                 ["private$&-$$-雪"])
                for value in (headers["x-camsol-password"], headers["x-camsol-email"], "private-cookie", "private$&-$$-雪"):
                    self.assertNotIn(value, response.text)

    def test_connection_config_only_declares_masked_user_settings(self):
        config = json.loads(Path(__file__).with_name("connection.json").read_text())
        self.assertFalse(config["startup"])
        self.assertFalse(config["requiresOAuth"])
        self.assertEqual(config["url"], "http://127.0.0.1:8786/mcp")
        self.assertTrue(all(field["sensitive"] for field in config["customUserVars"].values()))


if __name__ == "__main__":
    unittest.main()
