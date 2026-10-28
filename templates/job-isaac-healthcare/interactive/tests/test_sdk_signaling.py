"""SDK v2 transport regression gates; no model, GPU or live service calls."""

import asyncio
import time
from types import SimpleNamespace
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from i4h_interactive.server import application as portable_application
from i4h_interactive.signaling import encode_signaling

SID = "ses-0123456789abcdef"
FIELDS = dict(peer_id="peer-1234567890", version="2", peer_role="1", pairing_id=SID)
QUERY = encode_signaling(FIELDS, SID)
BAD = [
    QUERY + "&peer_id=second",
    QUERY + "&access_token=secret",
    QUERY.replace("peer_role=1", "peer_role=2"),
    QUERY.replace("version=2", "version=3"),
    QUERY.replace("pairing_id=" + SID, "pairing_id=another"),
    QUERY.replace("peer-1234567890", ""),
    QUERY.replace("peer-1234567890", "%0d%0aInjected"),
    QUERY.replace("peer-1234567890", "a%2fb"),
    QUERY.replace("peer-1234567890", "x" * 129),
    QUERY.replace("peer_role=1&", ""),
    QUERY + "&version=",
]


class Echo:
    def __init__(self, protocol):
        self.subprotocol = protocol
        self.queue = asyncio.Queue()
        self.close_codes = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def close(self, code=1000):
        self.close_codes.append(code)

    async def send(self, data):
        await self.queue.put(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self.queue.get()
        if isinstance(value, BaseException):
            raise value
        return value


class Factory:
    def __init__(self):
        self.calls = []
        self.peers = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        peer = Echo(kwargs["subprotocols"][0])
        self.peers.append(peer)
        return peer


def portable_fixture():
    config = {
        "session_id": SID,
        "browser_origin": "https://app.test",
        "deadline_at": time.time() + 60,
        "signal_port": 49100,
    }
    process = SimpleNamespace(active_connection=False, state="signaling")
    factory = Factory()
    token = "x" * 43
    app = portable_application(config, token, process=process, connect_factory=factory)
    return (TestClient(app), config, process, factory, token)


def test_portable_sdk_path_strips_capability_and_preserves_fixed_kit_target():
    client, _, process, factory, token = portable_fixture()
    with client.websocket_connect(
        "/signaling/sign_in?" + QUERY,
        headers={"origin": "https://app.test"},
        subprotocols=["x-nv-sessionid." + SID, "Authorization.Bearer." + token],
    ) as socket:
        socket.send_bytes(b"sdk-binary")
        assert socket.receive_bytes() == b"sdk-binary"
    assert factory.calls[0][0] == "ws://127.0.0.1:49100/sign_in?" + QUERY
    assert factory.calls[0][1]["subprotocols"] == ["x-nv-sessionid." + SID]
    assert token not in repr(factory.calls) and (not process.active_connection)


@pytest.mark.parametrize("negative", BAD + ["wrong-origin", "wrong-token", "expired"])
def test_portable_rejects_malformed_or_unauthorized_before_kit(negative):
    client, config, process, factory, token = portable_fixture()
    query = (
        QUERY if negative in ["wrong-origin", "wrong-token", "expired"] else negative
    )
    origin = "https://evil.test" if negative == "wrong-origin" else "https://app.test"
    supplied = "z" * 43 if negative == "wrong-token" else token
    if negative == "expired":
        config["deadline_at"] = time.time() - 1
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/signaling/sign_in?" + query,
            headers={"origin": origin},
            subprotocols=["x-nv-sessionid." + SID, "Authorization.Bearer." + supplied],
        ):
            pass
    assert factory.calls == [] and (not process.active_connection)
