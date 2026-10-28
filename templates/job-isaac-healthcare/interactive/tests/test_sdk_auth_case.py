"""Portable SDK credential casing, with real Fetch Headers wire production."""

import json
import subprocess
import time
from types import SimpleNamespace

import pytest
from i4h_interactive.contract import authenticate
from i4h_interactive.server import application
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_sdk_signaling import QUERY, SID, Factory

TOKEN = "AbCdEf0123456789_-" * 3
ORIGIN = "https://app.test"


def connect(protocols, *, origin=ORIGIN, bearer=None):
    config = {
        "session_id": SID,
        "browser_origin": ORIGIN,
        "deadline_at": time.time() + 60,
        "signal_port": 49100,
    }
    process = SimpleNamespace(active_connection=False, state="signaling")
    factory = Factory()
    client = TestClient(application(config, TOKEN, process=process, connect_factory=factory))
    headers = {"origin": origin}
    if bearer is not None:
        headers["authorization"] = bearer
    return client, headers, process, factory


def assert_accepted(protocols):
    client, headers, process, factory = connect(protocols)
    with client.websocket_connect(
        "/signaling/sign_in?" + QUERY, headers=headers, subprotocols=protocols
    ) as socket:
        socket.send_text("sdk-signaling")
        assert socket.receive_text() == "sdk-signaling"
    assert len(factory.calls) == 1
    assert factory.calls[0][0] == "ws://127.0.0.1:49100/sign_in?" + QUERY
    assert factory.calls[0][1]["subprotocols"] == ["x-nv-sessionid." + SID]
    assert TOKEN not in repr(factory.calls)
    assert not process.active_connection


def test_actual_fetch_headers_wire():
    result = subprocess.run(
        ["node", "--input-type=module", "-e", """
const headers = new Headers({'Authorization.Bearer': process.argv[1],
                            'x-nv-sessionid': process.argv[2]});
console.log(JSON.stringify(Array.from(headers.entries(), ([k, v]) => k + '.' + v)));
""", TOKEN, SID],
        capture_output=True, text=True, check=True, timeout=10,
    )
    protocols = json.loads(result.stdout)
    assert "authorization.bearer." + TOKEN in protocols
    assert_accepted(protocols)


@pytest.mark.parametrize("prefix", ["authorization.bearer.", "Authorization.Bearer.", "aUtHoRiZaTiOn.BeArEr."])
def test_auth_prefix_casing_preserves_token_and_strips_upstream(prefix):
    assert_accepted(["x-nv-sessionid." + SID, prefix + TOKEN])


@pytest.mark.parametrize("negative", ["mixed-duplicate", "lower-duplicate", "wrong-origin", "foreign-session", "token-case", "mixed-bearer"])
def test_rejected_auth_never_connects_to_kit(negative):
    protocols = ["x-nv-sessionid." + SID, "authorization.bearer." + TOKEN]
    origin, bearer = ORIGIN, None
    if negative == "mixed-duplicate":
        protocols.append("Authorization.Bearer." + TOKEN)
    elif negative == "lower-duplicate":
        protocols.append("authorization.bearer." + TOKEN)
    elif negative == "wrong-origin":
        origin = "https://other.test"
    elif negative == "foreign-session":
        protocols[0] = "x-nv-sessionid.another-session"
    elif negative == "token-case":
        protocols[1] = "authorization.bearer." + TOKEN.lower()
    else:
        bearer = "Bearer " + TOKEN
    client, headers, process, factory = connect(protocols, origin=origin, bearer=bearer)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/signaling/sign_in?" + QUERY, headers=headers, subprotocols=protocols
        ):
            pass
    assert factory.calls == [] and not process.active_connection


def test_nonbrowser_bearer_remains_case_sensitive():
    config = {"session_id": SID, "browser_origin": ORIGIN}
    assert authenticate({"authorization": "Bearer " + TOKEN}, config, TOKEN) == []
    with pytest.raises(PermissionError):
        authenticate({"authorization": "Bearer " + TOKEN.lower()}, config, TOKEN)
