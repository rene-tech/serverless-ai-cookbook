"""The bridge follows only configured authoritative Native target mappings."""

import hashlib
import hmac
import json
import runpy
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from i4h_interactive.bridge import application
from i4h_interactive.native import application as worker_application
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def mapping(region="south"):
    return {
        "region": region,
        "target": {
            "cluster": "cluster-" + region,
            "variant": "renderer",
            "id": "interactive-renderer",
            "image": "registry.example/runtime@sha256:" + "a" * 64,
            "gpu_class": "renderer",
        },
        "native_endpoint": f"wss://operator-{region}.example/v1/isaac/stream",
        "runtime_revision": "qualified",
    }


def payload(row):
    deadline = time.time() + 60
    sid = "ses-0123456789abcdef"
    return {
        "session_id": sid,
        "claim": "single-native-claim",
        "deadline_at": deadline,
        "startup_timeout_s": 10,
        "start": {
            "type": "isaac.session.start",
            "session_id": sid,
            "region": row["region"],
            "target": row["target"],
            "image": row["target"]["image"],
            "runtime_revision": row["runtime_revision"],
            "deadline_at": deadline,
            "start": {},
            "display": {},
            "start_signature": "c" * 64,
        },
    }


def test_selected_configured_url_only_and_no_duplicate_native_connection():
    observed = []

    class NoNetwork:
        async def __aenter__(self):
            raise RuntimeError("offline transport probe")

        async def __aexit__(self, *_):
            pass

    def connect(url, **kwargs):
        observed.append((url, kwargs))
        return NoNetwork()

    north, south = mapping("north"), mapping("south")
    app = application(
        service_token="k" * 40, targets=[north, south], connect_factory=connect
    )
    body = payload(south)
    with TestClient(app, headers={"Authorization": "Bearer " + "k" * 40}) as client:
        assert client.post("/sessions", json=body).status_code == 202
        assert client.get("/sessions/" + body["session_id"]).status_code == 200
        assert client.post("/sessions", json=body).status_code == 200
        assert len(observed) == 1 and observed[0][0] == south["native_endpoint"]
        assert observed[0][1]["additional_headers"] == {
            "x-serverless2-session-claim": "single-native-claim"
        }
        invalid = []
        for field, value in [
            ("image", "registry.example/runtime@sha256:" + "f" * 64),
            ("id", "unapproved-object"),
        ]:
            request = deepcopy(body)
            request["start"]["target"][field] = value
            invalid.append(request)
        for field, value in [
            ("region", "unknown"),
            ("runtime_revision", "unapproved"),
            ("native_endpoint", "wss://caller.invalid/steal"),
        ]:
            request = deepcopy(body)
            request["start"][field] = value
            invalid.append(request)
        request = deepcopy(body)
        request["native_endpoint"] = "wss://caller.invalid/steal"
        invalid.append(request)
        for request in invalid:
            assert client.post("/sessions", json=request).status_code == 409
        assert len(observed) == 1


def test_duplicate_target_object_and_untrusted_url_config_fail_before_connection():
    row = mapping()
    changed = deepcopy(row)
    changed["target"]["image"] = "registry.example/runtime@sha256:" + "b" * 64
    with pytest.raises(ValueError, match="duplicate"):
        application(service_token="k" * 40, targets=[row, changed])
    for url in [
        "ws://unsafe.example/stream",
        "wss://credential@host.example/stream",
        "wss://host.example/stream?claim=secret",
    ]:
        altered = {**row, "native_endpoint": url}
        with pytest.raises(ValueError, match="operator-bound"):
            application(service_token="k" * 40, targets=[altered])


def test_private_ca_is_an_explicit_readonly_operator_bundle():
    render = runpy.run_path(str(Path(__file__).parents[1] / "render_bridge.py"))[
        "render"
    ]
    values = dict(
        namespace="bridge",
        image="registry.example/bridge@sha256:" + "c" * 64,
        config_name="targets",
        tls_secret="tls",
        token_secret="token",
    )
    ordinary = render(**values)["items"][0]["spec"]["template"]["spec"]
    assert "env" not in ordinary["containers"][0]
    mounted = render(
        **values, trust_bundle_config="qualified-cas", trust_bundle_key="bundle.pem"
    )["items"][0]["spec"]["template"]["spec"]
    assert mounted["containers"][0]["env"] == [
        {"name": "SSL_CERT_FILE", "value": "/native-trust/ca.crt"}
    ]
    assert mounted["containers"][0]["volumeMounts"][-1]["readOnly"] is True
    assert mounted["volumes"][-1]["configMap"] == {
        "name": "qualified-cas",
        "items": [{"key": "bundle.pem", "path": "ca.crt"}],
    }


@pytest.mark.parametrize("field", ["region", "target"])
def test_unchanged_worker_rejects_modified_signed_target_before_project_code(field):
    row = mapping()
    value = payload(row)
    sid = value["session_id"]
    deadline = float(int(time.time()) + 60)
    stamp = datetime.fromtimestamp(deadline, UTC).isoformat()
    envelope = value["start"]
    envelope["deadline_at"] = deadline
    envelope.pop("start_signature")
    key = b"k" * 32
    envelope["start_signature"] = hmac.new(
        key,
        json.dumps(
            envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    if field == "region":
        envelope["region"] = "other-region"
    else:
        envelope["target"]["id"] = "other-object"
    events = []

    class API:
        async def attach(self, *_):
            return {
                "id": sid,
                "deadline_at": stamp,
                "owner": {"tenant": "t", "owner": "o"},
            }

        async def watch(self, *_):
            return {"deadline_at": stamp, "cancel_requested": False}

        async def release(self, actual, connection, outcome):
            events.append((actual, outcome))
            return {"id": actual, "status": "ended"}

    def no_project(*_):
        events.append("project_called")
        raise AssertionError("tampered target reached project code")

    app = worker_application(
        API(),
        model_id="interactive",
        expected_image=row["target"]["image"],
        runtime_revision=row["runtime_revision"],
        start_key=key,
        prepare_start=no_project,
        poll_seconds=0.01,
    )
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/isaac/stream",
            headers={
                "x-serverless2-session": sid,
                "x-serverless2-connection": "connection",
            },
            subprotocols=["x-nv-sessionid." + sid],
        ) as socket:
            socket.send_json(envelope)
            with pytest.raises(WebSocketDisconnect) as error:
                socket.receive_json()
            assert error.value.code == 1011
    assert events == [(sid, "error")]
