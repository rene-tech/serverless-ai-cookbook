"""Submit one reviewed Scientific AI stage and verify its owner artifacts."""

import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID


class Transient(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def https_url(value, *, origin=False):
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment
            or origin and (parts.path not in ("", "/") or parts.query)):
        raise ValueError("Use an authorized HTTPS URL")
    return value.rstrip("/") if origin else value


def token():
    file = os.environ.get("SCIENTIFIC_AI_TOKEN_FILE")
    value = Path(file).read_text().strip() if file else os.environ.get("SCIENTIFIC_AI_TOKEN", "")
    if not value or not re.fullmatch(r"[A-Za-z0-9_.~+/-]+={0,2}", value):
        raise ValueError("Load the approved Scientific AI bearer or rotating token file")
    return value


def open_request(request):
    try:
        return build_opener(NoRedirect).open(request, timeout=45)
    except HTTPError as error:
        code = error.code
        error.close()
        if code in {408, 425, 429, 500, 502, 503, 504}:
            raise Transient(f"Temporary HTTP {code}") from None
        raise ValueError(f"Request rejected with HTTP {code}") from None
    except URLError as error:
        if isinstance(error.reason, ssl.SSLError):
            raise ValueError("HTTPS certificate or protocol validation failed") from None
        raise Transient("Service connection failed") from None


def api(method, path, payload=None, key=None, *, asynchronous=False):
    base = https_url(os.environ["SCIENTIFIC_AI_URL"], origin=True)
    headers = {"Authorization": "Bearer " + token(), "Accept": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    if asynchronous:
        headers["Prefer"] = "respond-async"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(payload, allow_nan=False).encode()
    with open_request(Request(base + path, method=method, headers=headers, data=payload)) as response:
        raw = response.read((64 << 20) + 1)
    if len(raw) > 64 << 20:
        raise ValueError("The result manifest exceeds the expected size")
    return json.loads(raw)


def run_id(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("The service did not return a canonical Scientific AI run ID")
    return value


def wait(identifier, seconds):
    deadline = time.monotonic() + seconds
    poll = min(60, max(1, int(os.environ.get("SCIENTIFIC_AI_POLL_SECONDS", "15"))))
    while time.monotonic() < deadline:
        status = api("GET", "/v1/runs/" + identifier)
        if status["run_id"] != identifier:
            raise ValueError("Status belongs to another run")
        phase = status["phase"]
        if phase in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "PAUSED"}:
            return phase
        time.sleep(min(poll, max(0, deadline - time.monotonic())))
    raise ValueError("Wait limit reached. Reattach with the original submission key to check the remote run")


def stage_request(spec):
    if set(spec) != {"runtime", "request", "outputs"} or spec["runtime"] not in {"batch", "inference"}:
        raise ValueError("Declare the stage runtime, versioned request and exact outputs")
    body = spec["request"]
    if any(not isinstance(body[field], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", body[field])
           for field in ("model", "workflow")) or not isinstance(body["version"], str) or not body["version"]:
        raise ValueError("Declare a model, workflow and exact version")
    outputs = spec["outputs"]
    if (not isinstance(outputs, list) or not outputs or any(
            not isinstance(name, str) or not re.fullmatch(r"data/(?:[\w.-]+/)*[\w.-]+", name, re.ASCII)
            or {".", ".."}.intersection(name.split("/")) for name in outputs)
            or len(outputs) != len(set(outputs))):
        raise ValueError("Declare distinct, safe owner-artifact paths under data/")
    return spec["runtime"], body, set(outputs)


def download(item, destination):
    expected, size = item["sha256"], item["size_bytes"]
    if not re.fullmatch("[a-f0-9]{64}", expected) or type(size) is not int or size < 0:
        raise ValueError("Invalid artifact checksum or size")
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        digest, count = hashlib.sha256(), 0
        # This is a signed owner URL; never send the Scientific AI bearer.
        with open_request(Request(https_url(item["download_url"]))) as source, temporary.open("wb") as target:
            while block := source.read(1 << 20):
                count += len(block)
                if count > size:
                    raise ValueError("Artifact byte count mismatch")
                digest.update(block)
                target.write(block)
        if count != size or digest.hexdigest() != expected:
            raise ValueError("Artifact checksum or byte count mismatch")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": item["path"], "sha256": expected, "size_bytes": size}


def run(request_file):
    runtime, body, expected = stage_request(json.loads(request_file.read_text()))
    key = os.environ["SCIENTIFIC_AI_SUBMISSION_KEY"]
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", key):
        raise ValueError("Provide a stable submission key of 1–200 letters, digits, or ._:-")
    if runtime == "batch":
        submitted = api("POST", "/v1/runs", body, key)
    else:
        model, workflow = body.pop("model"), body.pop("workflow")
        submitted = api("POST", f"/v1/inference/{model}/{workflow}", body, key, asynchronous=True)["run"]
    identifier = run_id(submitted["run_id"])
    Path("sciai-run-id.txt").write_text(identifier + "\n")
    phase = wait(identifier, 14 * 24 * 60 * 60 + 600)
    if phase != "SUCCEEDED":
        raise ValueError(f"Scientific AI run {identifier} ended in {phase}")
    result = api("GET", f"/v1/runs/{identifier}/artifacts")
    if result["run_id"] != identifier:
        raise ValueError("Artifacts do not belong to the submitted run")
    destination = Path("outputs")
    destination.mkdir(exist_ok=True)
    selected = [item for item in result["files"] if item["path"] in expected]
    if len(selected) != len(expected) or {item["path"] for item in selected} != expected:
        raise ValueError("Missing or duplicate scientific output in the verified artifact manifest")
    verified = []
    for item in selected:
        path = destination / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        verified.append(download(item, path))
    Path("verified-manifest.json").write_text(json.dumps({"run_id": identifier, "files": verified}) + "\n")


def cancel(identifier_file):
    identifier = run_id(identifier_file.read_text().strip())
    result = api("POST", f"/v1/runs/{identifier}/cancel")
    if result["run_id"] != identifier:
        raise ValueError("Cancellation response belongs to another run")
    phase = wait(identifier, 600)
    if phase != "CANCELLED":
        raise ValueError(f"Scientific AI run {identifier} reached {phase} while cancellation was requested")


if __name__ == "__main__":
    os.umask(0o077)
    arguments = sys.argv[1:]
    if len(arguments) != 2 or arguments[0] not in {"run", "cancel"}:
        sys.exit("Usage: client.py run REQUEST_JSON | cancel RUN_ID_FILE")
    try:
        {"run": run, "cancel": cancel}[arguments[0]](Path(arguments[1]))
    except Transient as error:
        print(error, file=sys.stderr)
        sys.exit(75)
    except (TimeoutError, ConnectionError, http.client.HTTPException):
        print("Temporary service transport failure", file=sys.stderr)
        sys.exit(75)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error) if type(error) is ValueError else "Invalid run request, response, or local file", file=sys.stderr)
        sys.exit(65)
