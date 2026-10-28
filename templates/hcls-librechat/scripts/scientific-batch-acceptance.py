#!/usr/bin/env python3
"""Submit scientific work or recover completed outputs with hash verification.

Submission/resume mode uses the model/input options listed below.
Read-only recovery mode needs only the original operation ID and a new folder:
  /opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \\
    --recover-operation-id OPERATION_ID --output /workspace/md/recovered

Recovery does not upload inputs, submit, resubmit or cancel work. It requires
the existing operation to have succeeded and uses the configured credentials.
No model, source, parameters or idempotency key is needed for recovery.
For recovery-only help, add --help to that recovery command.

To observe an already accepted job from its original receipt, without inputs:
  python scientific-batch-acceptance.py --observe-output /path/to/original/output
This is read-only, including after a temporary connection failure. Exit 75
means observation is incomplete, not that the scientific operation failed.

The output directory is the resume boundary. Re-running it observes the saved
operation or reconciles a lost admission with the exact saved request/key.
It never creates a replacement request or changes scientific parameters.
"""

import argparse
import asyncio
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx2
from anyio import BrokenResourceError, ClosedResourceError, EndOfStream
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp_types import CONNECTION_CLOSED, INTERNAL_ERROR, INVALID_REQUEST, REQUEST_TIMEOUT

# The same source is installed beside scientific_receipts.py in the image.
if Path(__file__).parent.name == 'scripts':
    sys.path.insert(0, str(Path(__file__).parent.parent))
from scientific_receipts import (
    admission_refused,
    admission_retryable,
    file_measurement as artifact_file_measurement,  # noqa: F401 - retained helper import API
    load as load_receipt,
    publish_file as publish_artifact,
    receipt_lock,
    save,
    verify_file as verify_artifact_file,
)
from native_md_artifacts import materialize_native_outputs


TERMINAL = {"failed", "cancelled", "timed_out", "export_failed", "preempted"}


class ToolAvailabilityError(RuntimeError):
    """An authorized catalog does not expose the requested submission tool."""


ARTIFACT_CHUNK_BYTES = 1024 * 1024
ARTIFACT_DOWNLOAD_ATTEMPTS = 4
ARTIFACT_DOWNLOAD_WORKERS = 4
OPERATION_READ_ATTEMPTS = 5
OPERATION_READ_TIMEOUT = 60
ADMISSION_REPLAY_ATTEMPTS = 3
TRANSIENT_READ_HTTP = {408, 429, 500, 502, 503, 504}
READ_TRANSPORT_ERRORS = (httpx2.TransportError, ConnectionError, TimeoutError,
                         BrokenResourceError, ClosedResourceError, EndOfStream)


class FileSource:
    """Measured input with bounded-memory hashing and an exact-byte upload stream."""

    def __init__(self, path: Path):
        self.path = path
        with path.open('rb') as source:
            self.signature = self._signature(os.fstat(source.fileno()))
            self.prefix = source.read(4)
            source.seek(0)
            self.sha256 = hashlib.file_digest(source, 'sha256').hexdigest()
            if self._signature(os.fstat(source.fileno())) != self.signature:
                raise ValueError('Input changed while measuring; no upload was submitted.')

    @staticmethod
    def _signature(stat):
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns

    def __len__(self):
        return self.signature[2]

    def startswith(self, prefix):
        return self.prefix.startswith(prefix)

    async def chunks(self):
        checksum, size = hashlib.sha256(), 0
        with self.path.open('rb') as source:
            if self._signature(os.fstat(source.fileno())) != self.signature:
                raise ValueError('Input changed after measurement; preserve it before retrying.')
            while chunk := source.read(ARTIFACT_CHUNK_BYTES):
                size += len(chunk)
                checksum.update(chunk)
                yield chunk
            if (size != len(self) or checksum.hexdigest() != self.sha256
                    or self._signature(os.fstat(source.fileno())) != self.signature):
                raise ValueError('Input changed during upload; it must not be finalized or submitted.')


class TransientArtifactDownloadError(RuntimeError):
    """A read-only artifact transfer can be retried without new GPU work."""


class ExplicitRejection(RuntimeError):
    def __init__(self, error: dict):
        allowed = ("type", "code", "message", "request_id", "idempotency_key",
                   "retryable", "retry_after_seconds", "admission")
        self.error = {key: error[key] for key in allowed if key in error}
        super().__init__(self.error.get("message", "Gateway explicitly rejected the request."))


class ToolReadError(RuntimeError):
    """Retain structured tool failures; only the observation loop may retry them."""

    def __init__(self, error: dict):
        self.error = {key: error[key] for key in ("code", "retryable", "retry_after_seconds", "request_id")
                      if key in error}
        super().__init__(str(error.get("message", "MCP tool failed."))[:500])


class OperationObservationError(RuntimeError):
    """An expected read failure, distinct from a failed scientific operation."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.error = outcome['error']
        super().__init__(outcome['message'])


class ScientificOperationFailed(RuntimeError):
    """An authoritative unsuccessful operation, never an observation outage."""

    def __init__(self, receipt, output, *, action_required=False):
        self.outcome = {'outcome': 'scientific_action_required' if action_required else 'scientific_failed',
                        'operation_id': receipt['operation_id'],
                        'state': receipt['state'], 'failure_code': receipt.get('failure_code'),
                        'diagnostics_directory': str(output),
                        'message': 'Scientific operation ' + ('requires attention' if action_required
                            else 'ended in ' + receipt['state'])
                            + '; inspect the retained status and diagnostics.'}
        if receipt.get('scientific_error'):
            self.outcome['error'] = receipt['scientific_error']
            self.outcome['message'] = receipt['scientific_error'].get('message', self.outcome['message'])
        super().__init__(self.outcome['message'])


class ParameterPreflightError(ValueError):
    """A local parameter-file rejection, before this invocation uploads/admission."""


class SourcePreflightError(ValueError):
    """A local source/metadata rejection, before this invocation uploads/admission."""


def submission_contract(tool_schema):
    """Select a current execution family's envelope from its exact tool schema.

    MD/scVI/MPI tools wrap their typed request; staged scientific tools publish
    its fields directly. This is discovery, never a failed-call downgrade.
    """
    properties = tool_schema.get('properties', {})
    wrapped = 'request' in properties
    if wrapped == ('parameters' in properties):
        raise ValueError('Submission tool must advertise exactly one scientific request shape.')
    request_schema = properties['request'] if wrapped else tool_schema
    visited = set()
    while isinstance(request_schema, dict) and '$ref' in request_schema:
        reference = request_schema['$ref']
        if not isinstance(reference, str) or not reference.startswith('#/') or reference in visited:
            raise RuntimeError('Scientific request schema has an unsupported reference; no upload was submitted.')
        visited.add(reference)
        request_schema = tool_schema
        for component in reference[2:].split('/'):
            request_schema = request_schema.get(component.replace('~1', '/').replace('~0', '~'), {})
    if not isinstance(request_schema, dict) or 'parameters' not in request_schema.get('properties', {}):
        raise ValueError('Submission tool has no typed scientific parameters schema.')
    return wrapped, request_schema


def submission_arguments(tool_schema, body, idempotency_key):
    wrapped, _ = submission_contract(tool_schema)
    arguments = {'request': body} if wrapped else dict(body)
    arguments['idempotency_key'] = idempotency_key
    Draft202012Validator(tool_schema).validate(arguments)
    return arguments


def preflight_parameters(tool_schema: dict, parameters: object, source: bytes | FileSource, args) -> None:
    """Validate exact discovered parameters before reserving an artifact.

    The uploaded-bundle placeholder uses measured validation-only fields here;
    submission later validates the real finalized upload reference.
    """
    _, request_schema = submission_contract(tool_schema)
    schema = request_schema.get('properties', {}).get('parameters') if isinstance(request_schema, dict) else None
    if not isinstance(schema, (dict, bool)):
        raise RuntimeError('Scientific submission tool has no parameters schema; no upload was submitted.')
    measured = {'artifact_id': '00000000-0000-4000-8000-000000000001',
                'sha256': digest(source), 'size_bytes': len(source),
                'media_type': args.media_type, 'compression': args.compression}
    candidate = bind_uploaded_source(parameters, measured)
    # Evolve the root validator rather than constructing one from the detached
    # property: local $defs/$ref targets remain relative to the advertised tool.
    validator = Draft202012Validator(tool_schema).evolve(schema=schema)
    errors = list(validator.iter_errors(candidate))
    if not errors:
        return
    envelope = isinstance(parameters, dict) and isinstance(parameters.get('parameters'), dict) and any(
        field in parameters for field in ('schema', 'operation', 'service_class', 'input_manifest'))
    prefix = ('The parameters file contains a full scientific-run request envelope. '
              'Put only its model-parameter object at the file root, not the envelope; '
              'the client does not unwrap or correct it. ' if envelope else
              'The parameters file does not match the advertised model-parameter schema. ')
    properties = schema.get('properties', {}) if isinstance(schema, dict) else {}
    if properties:
        shape = {name: '<' + str(value.get('type', 'contract value')) + '>'
                 for name, value in list(properties.items())[:12] if isinstance(value, dict)}
        prefix += 'Root-object shape (placeholders, not scientific defaults): ' + json.dumps(shape) + '. '
    details = '; '.join('/'.join(str(part) for part in error.absolute_path) + ': ' + error.message
                        for error in errors[:8])
    raise ParameterPreflightError(prefix + details + '. No upload or inference was submitted by this invocation.')


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data: bytes | FileSource) -> str:
    return data.sha256 if isinstance(data, FileSource) else hashlib.sha256(data).hexdigest()


def check(response):
    if not response.is_success:
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        if admission_refused(error):
            raise ExplicitRejection(error)
        raise RuntimeError(f"Platform returned HTTP {response.status_code}; inspect the saved evidence.")
    return response


def unpack(response, *, operation_id=None):
    data = response.model_dump(mode="json", by_alias=True)
    if data.get("structuredContent") is not None:
        value = data["structuredContent"]
    else:
        texts = [item["text"] for item in data.get("content", []) if item.get("type") == "text"]
        if len(texts) != 1:
            raise RuntimeError("Expected one JSON MCP result.")
        try:
            value = json.loads(texts[0])
        except ValueError:
            raise RuntimeError("MCP returned an unreadable result; admission may be unknown.") from None
    error = value.get('error') if isinstance(value, dict) else None
    # Current operation status/results can carry scientific diagnostics while
    # the read itself succeeded. Keep those distinct from a failed tool read.
    scientific_error = bool(isinstance(error, dict) and error and not data.get('isError')
        and operation_id and isinstance(value, dict)
        and value.get('operation_id') == operation_id
        and (value.get('operation', {}).get('status') in TERMINAL
             or value.get('status') in TERMINAL
             or value.get('graph', {}).get('action_required') is True
             or value.get('action_required') is True))
    if scientific_error and 'operation' in value:
        batch_operation(value, operation_id=operation_id)
    if admission_refused(error):
        raise ExplicitRejection(error)
    if isinstance(error, dict) and error and not scientific_error:
        raise ToolReadError(error)
    if data.get("isError") and not scientific_error:
        raise RuntimeError("MCP tool failed; inspect the saved response.")
    return value


async def call(client, name: str, arguments: dict):
    return unpack(await client.call_tool(name, arguments),
                  operation_id=arguments.get('operation_id')
                  if name in {'get_operation', 'get_operation_result'} else None)


class OperationReadHTTP:
    """Observe HTTP status before MCP 2.2 maps e.g. 401 and 503 to one error.

    Only this operation's reads and their session handshake are observed. Never
    retain headers, credentials, response bodies, or unrelated background GETs.
    """

    def __init__(self, operation_id):
        self.operation_id, self.failure = operation_id, None

    async def response(self, response):
        if response.request.method != 'POST' or response.status_code < 400:
            return
        try:
            request = json.loads(response.request.content)
        except (ValueError, UnicodeError):
            return
        if not isinstance(request, dict):
            return
        method, params = request.get('method'), request.get('params', {})
        if method not in {'initialize', 'server/discover', 'tools/list'} and not (
                method == 'tools/call' and isinstance(params, dict)
                and params.get('name') in {'get_operation', 'get_operation_result'}
                and params.get('arguments', {}).get('operation_id') == self.operation_id):
            return
        self.failure = {'http_status': response.status_code}
        delay = retry_after_seconds(response.headers.get('retry-after'))
        if delay:
            self.failure['retry_after_seconds'] = delay


def retry_after_seconds(value):
    """Honor both HTTP delta-seconds and dates; the existing deadline bounds waits."""
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            delay = parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError, AttributeError):
            return 0
    return delay if math.isfinite(delay) and delay > 0 else 0


def operation_read_failure(error, http_failure=None):
    """Fail closed unless every exception leaf is an identified transient read."""
    if isinstance(error, BaseExceptionGroup):
        failures = [operation_read_failure(item, http_failure) for item in error.exceptions]
        unknown = next((item for item in failures if not item.get('expected')), None)
        permanent = next((item for item in failures if not item['retryable']), None)
        return unknown or permanent or max(failures, key=lambda item: item.get('retry_after_seconds', 0))
    if isinstance(error, OperationObservationError):
        return error.error
    info = {'error_type': type(error).__name__, 'retryable': False, **(http_failure or {})}
    if not isinstance(error, (MCPError, ToolReadError, ExplicitRejection, *READ_TRANSPORT_ERRORS)):
        return info
    info['expected'] = True
    structured = getattr(error, 'error', {})
    if isinstance(error, MCPError):
        info['rpc_code'] = error.code
        structured = error.data if isinstance(error.data, dict) else {}
        structured = structured.get('error', structured)
        if error.code not in {INTERNAL_ERROR, CONNECTION_CLOSED, REQUEST_TIMEOUT} and not (
                error.code == INVALID_REQUEST and error.message == 'Session terminated'):
            return info
    if isinstance(structured, dict):
        for field in ('code', 'request_id'):
            if isinstance(structured.get(field), str):
                info[field] = structured[field][:160]
        delay = retry_after_seconds(structured.get('retry_after_seconds'))
        if delay:
            info['retry_after_seconds'] = max(delay, info.get('retry_after_seconds', 0))
        # Explicit server rejection always wins over a generic transport error.
        if structured.get('retryable') is False or structured.get('code') in {
                'not_found', 'unauthorized', 'unauthenticated', 'forbidden',
                'invalid_tool_arguments', 'invalid_request', 'validation_error'}:
            return info
    status = info.get('http_status')
    if status is not None:
        # A lost MCP session is not an absent scientific operation. Re-handshake
        # only for this exact SDK signal; a real tool not_found stopped above.
        info['retryable'] = status in TRANSIENT_READ_HTTP or (
            status == 404 and isinstance(error, MCPError) and error.code == INVALID_REQUEST
            and error.message == 'Session terminated')
        return info
    if isinstance(error, (ToolReadError, ExplicitRejection)):
        info['retryable'] = structured.get('retryable') is True
    elif isinstance(error, MCPError):
        info['retryable'] = error.code in {INTERNAL_ERROR, CONNECTION_CLOSED, REQUEST_TIMEOUT} or (
            error.code == INVALID_REQUEST and error.message == 'Session terminated')
    elif isinstance(error, READ_TRANSPORT_ERRORS):
        info['retryable'] = True
    return info


def observation_outcome(args, receipt, info):
    """Report observation uncertainty without changing the last scientific state."""
    category = ('authorization_failed' if info.get('http_status') in {401, 403}
                or info.get('code') in {'unauthorized', 'unauthenticated', 'forbidden'} else
                'operation_not_found' if info.get('http_status') == 404
                or info.get('code') == 'not_found' else
                'observation_unavailable' if info['retryable'] else 'observation_rejected')
    return {'outcome': category, 'operation_id': receipt['operation_id'], 'state': 'unknown',
            'last_observed_state': receipt['state'], 'error': info,
            'receipt_directory': str(args.output),
            'recovery_command': shlex.join([sys.executable, str(Path(__file__).resolve()),
                                           '--observe-output', str(args.output.resolve())]),
            'message': ('The current operation state could not be read. This is not a scientific '
                        'failure; the accepted operation was not resubmitted or changed. '
                        + ('Retry the recovery command after service recovery.' if info['retryable']
                           else 'Resolve the reported access or request error before retrying.'))}


async def observe_operation(args, http, endpoint, headers, receipt, receipt_path, *, recovery=False):
    """Reconnect bounded read-only sessions; never return to upload/admission.

    Five consecutive failed observations at most, sharing the original wait
    deadline. Success resets the transient budget. Last authoritative scientific
    state and operation identity are retained even when observation is exhausted.
    """
    deadline = time.monotonic() + (180 if recovery else max(0, args.wait_seconds))
    failures, operation_id = 0, receipt['operation_id']
    announced_state = None
    observation = OperationReadHTTP(operation_id)
    while True:
        phase, observation.failure = 'connect', None
        try:
            # wait_seconds bounds repeated observations, not the connection.
            # The durable study worker asks for wait_seconds=0 to check once.
            # Giving that request 100 ms prevented a real TLS/MCP handshake,
            # so completed remote work stayed queued indefinitely in the UI.
            # Always permit one bounded read; the deadline below still stops
            # further polls/retries and never re-admits the scientific job.
            timeout = OPERATION_READ_TIMEOUT
            async with httpx2.AsyncClient(headers=headers, timeout=timeout, trust_env=False,
                    follow_redirects=False, event_hooks={'response': [observation.response]}) as mcp_http:
                async with Client(streamable_http_client(endpoint, http_client=mcp_http),
                                  read_timeout_seconds=timeout) as connection:
                    while True:
                        phase, observation.failure = 'get_operation', None
                        status = await call(connection, phase, {'operation_id': operation_id})
                        phase, observation.failure = None, None
                        save(args.output / 'status.json', status)
                        operation = batch_operation(status, operation_id=operation_id,
                                                    model_id=receipt['identity'].get('model_id'))
                        receipt['state'] = operation['status']
                        receipt.pop('observation', None)
                        if isinstance(status.get('error'), dict):
                            receipt['scientific_error'] = {
                                key: status['error'][key] for key in
                                ('code', 'message', 'next_action', 'phase', 'stage_id',
                                 'retryable', 'resumable', 'diagnostics_available')
                                if key in status['error']}
                        save(receipt_path, receipt)
                        if receipt['state'] != announced_state:
                            # User-visible progress from authoritative state, not
                            # another LLM inference or a heartbeat every poll.
                            print(json.dumps({'operation_id': operation_id,
                                              'state': receipt['state'],
                                              'observation': 'state_changed'}), flush=True)
                            announced_state = receipt['state']
                        if operation['status'] in TERMINAL:
                            await retain_terminal_diagnostics(connection, status, args.output, receipt, http=http)
                            raise ScientificOperationFailed(receipt, args.output)
                        if status.get('graph', {}).get('action_required') is True:
                            raise ScientificOperationFailed(receipt, args.output, action_required=True)
                        if recovery and (operation['status'] != 'succeeded'
                                or not operation.get('result_available')):
                            print(json.dumps({'outcome': 'result_not_ready', 'operation_id': operation_id,
                                              'state': receipt['state'], 'resume': str(args.output)}), flush=True)
                            return receipt
                        if operation.get('result_available'):
                            phase = 'get_operation_result'
                            result = await call(connection, phase, {'operation_id': operation_id})
                            phase, observation.failure = None, None
                            if result.get('operation_id') != operation_id:
                                raise RuntimeError('Result operation identity differs from requested operation.')
                            save(args.output / 'result.json', result)
                            receipt.update(await collect_outputs(http, result, args.output), state='verified')
                            save(receipt_path, receipt)
                            summary = ({'operation_id': operation_id, 'state': 'verified',
                                        'receipt_file': str(receipt_path), 'artifacts': receipt['verified_artifacts'],
                                        'inference_submitted': False} if recovery else
                                       {'model': receipt['identity'].get('model_id'),
                                        'operation_id': operation_id, 'state': 'verified',
                                        'artifacts': len(receipt['verified_artifacts'])})
                            if receipt.get('native_outputs'):
                                summary['native_outputs'] = receipt['native_outputs']
                            print(json.dumps(summary), flush=True)
                            return receipt
                        failures = 0
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            print(json.dumps({'operation_id': operation_id, 'state': receipt['state'],
                                              'resume': str(args.output)}), flush=True)
                            return receipt
                        await asyncio.sleep(min(args.poll_seconds, remaining))
                        if time.monotonic() >= deadline:
                            return receipt
        except Exception as error:
            # Local validation, collection, receipt I/O and terminal scientific
            # errors cannot enter the retry path. SDK session teardown can also
            # fail after a successful read; it is still only transport cleanup.
            # Cancellation is never caught.
            info = operation_read_failure(error, observation.failure)
            if receipt['state'] == 'verified' and phase is None and info['retryable']:
                # A failed session close cannot invalidate already verified bytes.
                receipt['session_cleanup_error'] = info
                save(receipt_path, receipt)
                return receipt
            if phase is None and not info['retryable']:
                raise
            phase = phase or 'session_cleanup'
            failures += 1
            remaining = deadline - time.monotonic()
            retry = info['retryable'] and failures < OPERATION_READ_ATTEMPTS and remaining > 0
            delay = max(min(2 ** (failures - 1), 30), info.get('retry_after_seconds', 0)) if retry else 0
            if retry and delay >= remaining:
                retry, delay = False, 0  # No new session after this invocation's wait deadline.
            event = {**info, 'operation_id': operation_id, 'tool': phase,
                     'recorded_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                     'consecutive_failures': failures, 'retry_scheduled': retry,
                     'retry_delay_seconds': delay}
            # Bound receipt growth during a long study; retain exact last errors
            # and the cumulative count without copying raw server messages.
            receipt['observation_failure_count'] = receipt.get('observation_failure_count', 0) + 1
            receipt['observation_errors'] = (receipt.get('observation_errors', []) + [event])[-20:]
            save(receipt_path, receipt)
            if not info['retryable']:
                if not info.get('expected'):
                    raise  # Programming/validation errors are not observation outages.
                receipt['observation'] = observation_outcome(args, receipt, info)
                save(receipt_path, receipt)
                raise OperationObservationError(receipt['observation']) from None
            if not retry:
                receipt['observation'] = observation_outcome(args, receipt, info)
                save(receipt_path, receipt)
                print(json.dumps(receipt['observation']), flush=True)
                return receipt
            print(json.dumps({'operation_id': operation_id, 'observation': 'retrying',
                              'attempt': failures + 1, 'delay_seconds': delay}), file=sys.stderr, flush=True)
            await asyncio.sleep(delay)


def scientific_contract(discovery: dict) -> dict:
    contracts = discovery['contracts']
    contract = next((item for item in contracts if item.get('protocol') == 'scientific-batch-v1'), {})
    # The real get_model_schema response publishes shared artifact policies at
    # its top level, alongside contracts; do not discard them while selecting a
    # transport. Read the current published fields without mutating discovery.
    published = {field: discovery[field] for field in
                 ('artifact_manifest_schema', 'input_artifact_contract') if field in discovery}
    return {**contract, **published} if published else contract


def selected_source_contract(contract: dict, parameters: dict, args):
    """Select the already-published input role; no filename or model-name rules."""
    policy = contract.get('input_artifact_contract')
    if not policy:
        return None, None  # Artifact-role policy is optional for current Apps.
    context = {'operation': getattr(args, 'operation', None), 'parameters': parameters}
    if 'entry' in policy:
        source, selection = policy['entry'], 'the published input entry'
    elif 'entries' in policy:
        entries = policy['entries']
        matches = [entry for entry in entries if isinstance(entry, dict)
                   and entry.get('name') == args.entry_name] if isinstance(entries, list) else []
        if len(matches) != 1:
            raise SourcePreflightError('Choose one unique published input entry name; no upload was submitted.')
        source, selection = matches[0], f'entry {args.entry_name!r}'
        missing = [entry.get('name') for entry in entries if isinstance(entry, dict)
                   and entry.get('required') is True and entry is not source]
        if missing:
            raise SourcePreflightError(f'This request also requires input entries {missing!r}; '
                                       'use a complete manifest. No upload was submitted.')
    else:
        selector = policy.get('operation_parameter') or policy.get('source_kind_parameter', 'parameters.source.kind')
        value = context
        for part in selector.split('.'):
            value = value.get(part) if isinstance(value, dict) else None
        alternatives = policy.get('operations') if 'operation_parameter' in policy else policy.get('source_kinds')
        source = alternatives.get(value) if isinstance(alternatives, dict) else None
        selection = f'{selector}={value!r}'
    if not isinstance(source, dict) or not source:
        raise SourcePreflightError(f'Input selector {selection} is not in the published input_artifact_contract; no upload was submitted.')
    return source, selection


def resolve_source_compression(contract: dict, parameters: dict, args, source: bytes | FileSource):
    """Resolve omitted transport metadata only; never edit source/scientific bytes.

    Explicit choices are left to the existing strict preflight. Plain inputs keep
    the uncompressed encoding. Compressed inputs require a uniquely allowed
    published encoding and its actual magic bytes, never a filename inference.
    """
    explicit = getattr(args, 'compression', None)
    if explicit is not None:
        return args, {'selection': 'explicit', 'compression': explicit}
    detected = ('gzip' if source.startswith(b'\x1f\x8b\x08') else
                'zstd' if source.startswith(b'\x28\xb5\x2f\xfd') else 'none')
    entry, _ = selected_source_contract(contract, parameters, args)
    allowed = (entry.get('allowed_compressions', [entry['compression']] if 'compression' in entry else [])
               if entry else [])
    if detected != 'none' and allowed != [detected]:
        raise SourcePreflightError(
            'compression is omitted for a compressed source; specify it explicitly from the published '
            'input_artifact_contract. Automatic binding requires one allowed encoding matching the '
            'actual source signature. No upload or inference was submitted.')
    resolved = argparse.Namespace(**{**vars(args), 'compression': detected})
    return resolved, {'selection': 'published-single-encoding-and-source-signature' if detected != 'none'
                      else 'uncompressed-source-signature', 'compression': detected,
                      'source_signature': detected}


def preflight_source(contract: dict, parameters: dict, args, size: int) -> None:
    """Validate a published semantic role before reserving or uploading bytes."""
    source, selection = selected_source_contract(contract, parameters, args)
    if source is None:
        return
    mismatches = []
    for argument, field in [('entry_name', 'name'), ('semantic_type', 'semantic_type'),
                            ('media_type', 'media_type')]:
        if field in source and getattr(args, argument) != source[field]:
            mismatches.append(f'{field} must be {source[field]!r}, received {getattr(args, argument)!r}')
    allowed_compressions = source.get('allowed_compressions')
    if allowed_compressions is not None:
        if not isinstance(allowed_compressions, list) or not allowed_compressions:
            raise SourcePreflightError('Published allowed_compressions must be a nonempty list.')
        if args.compression not in allowed_compressions:
            mismatches.append(f'compression must be one of {allowed_compressions!r}, received {args.compression!r}')
    elif 'compression' in source and args.compression != source['compression']:
        mismatches.append(f'compression must be {source["compression"]!r}, received {args.compression!r}')
    if source.get('maximum_bytes') is not None and size > source['maximum_bytes']:
        mismatches.append('input bytes exceed the published source maximum_bytes')
    if size < 1:
        mismatches.append('source_file must contain at least one byte')
    if mismatches:
        raise SourcePreflightError(f'Input artifact metadata for {selection}: ' + '; '.join(mismatches) +
                         '. The entry name is a semantic role, not the local filename. '
                         'The source media type describes the actual bytes, not the outer manifest. '
                         'No upload or inference was submitted.')


def source_reference(path: Path, data: bytes | FileSource, args) -> dict:
    reference = json.loads(path.read_text())
    return validate_source_reference(reference, data, args)


def validate_source_reference(reference: dict, data: bytes | FileSource, args) -> dict:
    for field, expected in {'sha256': digest(data), 'size_bytes': len(data),
                            'media_type': args.media_type, 'compression': args.compression}.items():
        if reference.get(field) != expected:
            raise ValueError('Existing artifact reference does not match exact source bytes and format: ' + field)
    if not isinstance(reference.get('artifact_id'), str) or not reference['artifact_id']:
        raise ValueError('Existing artifact reference must include its finalized artifact_id.')
    return {field: reference[field] for field in ('artifact_id', 'sha256', 'size_bytes', 'media_type', 'compression')}


async def upload(http, model: str, data: bytes | FileSource, media_type: str, compression: str,
                 idempotency_key: str) -> dict:
    measured = {"model_id": model, "sha256": digest(data), "size_bytes": len(data),
                "media_type": media_type, "compression": compression}
    begun = check(await http.post("/v1/scientific-artifacts/uploads", json=measured,
                                 headers={"idempotency-key": idempotency_key})).json()
    if len(data) <= begun["max_content_bytes"]:
        target = begun["content_path"]
        if not isinstance(target, str) or not target.startswith("/") or target.startswith("//"):
            raise RuntimeError("Unsafe same-origin upload path.")
        check(await http.put(target, content=data.chunks() if isinstance(data, FileSource) else data,
                             headers={"content-type": media_type,
                                                            "content-length": str(len(data))}))
    else:
        handle = begun.get("handle", {})
        if urlparse(handle.get("url", "")).scheme != "https":
            raise RuntimeError("Large upload did not return an HTTPS object-storage handle.")
        async with httpx2.AsyncClient(timeout=600, trust_env=False, follow_redirects=False) as storage:
            check(await storage.put(handle["url"],
                content=data.chunks() if isinstance(data, FileSource) else data,
                headers={**handle.get("headers", {}), "content-length": str(len(data))}))
    finalized = check(await http.post(
        "/v1/scientific-artifacts/uploads/" + quote(begun["upload_id"], safe="") + ":finalize",
        json={},
    )).json()
    if finalized.get('state') != 'finalized' or not isinstance(finalized.get('artifact'), dict):
        raise RuntimeError('Upload did not return a finalized artifact.')
    result = finalized['artifact']
    for key, value in measured.items():
        if key != "model_id" and result.get(key) != value:
            raise RuntimeError("Finalized artifact metadata mismatch.")
    return result


async def download(http, reference: dict, target: Path) -> dict:
    for attempt in range(ARTIFACT_DOWNLOAD_ATTEMPTS):
        try:
            result = await _download_once(http, reference, target)
            return {**result, 'transfer_attempts': attempt + 1}
        except (TransientArtifactDownloadError, httpx2.TransportError):
            if attempt + 1 == ARTIFACT_DOWNLOAD_ATTEMPTS:
                raise RuntimeError('Artifact download is temporarily unavailable after bounded retries. '
                                   'Resume the saved operation; do not resubmit GPU work.') from None
            await asyncio.sleep(2 ** attempt)


async def _download_once(http, reference: dict, target: Path) -> dict:
    expected_size = reference['size_bytes']
    if type(expected_size) is not int or expected_size < 0:
        raise ValueError('Artifact size_bytes must be a nonnegative integer.')
    expected_hash = reference['sha256']
    if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(c not in '0123456789abcdef' for c in expected_hash):
        raise ValueError('Artifact sha256 must be a canonical SHA-256 digest.')
    if target.exists():
        verify_artifact_file(target, reference)
        publication = 'verified-existing'
    else:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Stage outside the customer bucket so an interrupted network transfer
        # never appears as a completed artifact. No new global size cap: the
        # exact server-declared size bounds every chunk and the resulting file.
        with tempfile.TemporaryDirectory(prefix='scientific-artifact-') as folder:
            staged = Path(folder) / 'download.partial'
            size, checksum = 0, hashlib.sha256()
            path = '/v1/artifacts/' + quote(reference['artifact_id'], safe='') + '/content'
            async with http.stream('GET', path) as response:
                if not response.is_success:
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise TransientArtifactDownloadError('Temporary artifact read failure.')
                    raise RuntimeError(f'Platform returned HTTP {response.status_code}; inspect the saved evidence.')
                length = response.headers.get('content-length')
                if length is not None and int(length) != expected_size:
                    raise RuntimeError('Artifact Content-Length differs from the declared size.')
                with open(staged, 'xb', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
                    # Stored gzip/zstd bytes are the checksum identity; do not
                    # transparently decode HTTP Content-Encoding during hashing.
                    async for chunk in response.aiter_raw(chunk_size=ARTIFACT_CHUNK_BYTES):
                        size += len(chunk)
                        if size > expected_size:
                            raise RuntimeError('Downloaded artifact exceeds its declared size.')
                        checksum.update(chunk)
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
            if size != expected_size or checksum.hexdigest() != expected_hash:
                raise RuntimeError('Downloaded artifact hash or size mismatch.')
            publication = publish_artifact(staged, target, reference)
    return {'artifact_id': reference['artifact_id'], 'path': str(target),
            'size_bytes': expected_size, 'sha256': expected_hash, 'publication': publication}


async def collect_outputs(http, result: dict, output: Path) -> dict:
    """One flat published manifest, using the existing hash-verified transport."""
    if result.get('terminal_status') != 'succeeded' or result.get('semantic_validation', {}).get('status') != 'passed':
        raise RuntimeError('Published result did not pass semantic validation.')
    collected = await collect_manifest(http, result['output_manifest'], output)
    collected.update(materialize_native_outputs(output, collected['verified_artifacts']))
    return collected


async def collect_manifest(http, reference: dict, output: Path, *, diagnostics=False) -> dict:
    """Transport integrity is distinct from scientific success, including logs."""
    manifest = await download(http, reference, output / 'output-manifest.json')
    document = json.loads((output / 'output-manifest.json').read_text())
    if diagnostics:
        allowed = {'native-failed-diagnostics/v1'} | {
            f'{engine}-failed-{kind}/v1'
            for engine in ('gromacs', 'namd', 'amber', 'lammps', 'openmm')
            for kind in ('result', 'log')
        }
        if (document.get('schema') != 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1'
                or not isinstance(document.get('entries'), list)
                or not document['entries']
                or any(entry.get('semantic_type') not in allowed for entry in document['entries'])):
            raise RuntimeError('Failed-attempt manifest contains non-diagnostic artifacts.')
    entries = document['entries']
    # MD workflows have many native files. Bound both memory and simultaneous
    # transfers without paying one network round trip per file sequentially.
    pending = iter(enumerate(entries))
    artifacts = [None] * len(entries)
    async def worker():
        for index, entry in pending:
            downloaded = await download(http, entry['artifact'], output / f'output-{index:02d}.artifact')
            artifacts[index] = {**entry['artifact'], **downloaded,
                                'name': entry['name'], 'semantic_type': entry['semantic_type']}
    workers = [asyncio.create_task(worker()) for _ in range(min(ARTIFACT_DOWNLOAD_WORKERS, len(entries)))]
    try:
        await asyncio.gather(*workers)
    except BaseException:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        raise
    return {'output_manifest': manifest, 'verified_artifacts': artifacts}


async def retain_terminal_diagnostics(client, status: dict, output: Path, receipt: dict, *, http=None) -> None:
    """Keep a failed run's published explanation without treating it as success."""
    operation = status['operation']
    if operation.get('status') not in TERMINAL:
        raise ValueError('Terminal diagnostics require an unsuccessful terminal operation.')
    receipt['state'] = operation['status']
    receipt['failure_code'] = (receipt.get('scientific_error', {}).get('code')
                               or operation.get('error_code'))
    if operation.get('result_available'):
        try:
            result = await call(client, 'get_operation_result', {'operation_id': receipt['operation_id']})
            save(output / 'failure-result.json', result)
            receipt['failure_result'] = 'failure-result.json'
            if http is not None and result.get('output_manifest'):
                if (result.get('terminal_status') not in TERMINAL
                        or result.get('semantic_validation', {}).get('status') == 'passed'
                        or result.get('operation_id') != receipt['operation_id']):
                    raise RuntimeError('Failed diagnostics do not match the unsuccessful operation.')
                collected = await collect_manifest(
                    http, result['output_manifest'], output / 'failed-attempt', diagnostics=True)
                receipt['diagnostic_manifest'] = collected['output_manifest']
                receipt['diagnostic_artifacts'] = collected['verified_artifacts']
        except Exception as error:
            # The original failed operation remains authoritative. A diagnostics
            # read failure must not trigger a new scientific submission.
            receipt['diagnostics_read_error_type'] = type(error).__name__
    save(output / 'receipt.json', receipt)


async def recover_completed(args) -> dict:
    """Only status/result reads: never reserve, upload, admit, cancel or infer."""
    operation_id = args.recover_operation_id
    if not isinstance(operation_id, str) or not re.fullmatch(r'op-[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?', operation_id):
        raise ValueError('Use the native op-... operation ID returned by submission.')
    endpoint = os.environ['SCIENTIFIC_MODELS_MCP_URL']
    key = os.environ['SCIENTIFIC_MODELS_API_KEY']
    origin = endpoint.removesuffix('/mcp').removesuffix('/mcp/')
    identity = {'operation_id': operation_id, 'endpoint': endpoint,
                'caller_fingerprint': digest(key.encode())}
    path = args.output / 'recovery-receipt.json'
    receipt = load_receipt(path)
    if receipt is None:
        # The caller's existing run directory and any rejected receipts remain
        # untouched. Use a new recovery directory, then reuse its exact identity.
        existing = [item for item in args.output.iterdir()] if args.output.exists() else []
        if existing:
            raise ValueError('Use an empty recovery directory; existing study files are preserved.')
        receipt = {'identity': identity, 'operation_id': operation_id, 'state': 'prepared'}
    if receipt['identity'] != identity:
        raise ValueError('Recovery directory belongs to a different operation or caller.')
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    save(path, receipt)
    headers = {'authorization': 'Bearer ' + key}
    async with httpx2.AsyncClient(base_url=origin, headers=headers, timeout=180,
                                  trust_env=False, follow_redirects=False) as http:
        return await observe_operation(args, http, endpoint, headers, receipt, path, recovery=True)


async def observe_saved(args) -> dict:
    """Read a bound receipt only; inputs and admission code are never opened."""
    paths = [path for name in ('receipt.json', 'recovery-receipt.json')
             if (path := args.output / name).is_file()]
    if len(paths) != 1:
        raise ValueError('Observation requires exactly one existing operation receipt in this directory.')
    path, receipt = paths[0], load_receipt(paths[0])
    if not receipt or not receipt.get('operation_id'):
        raise ValueError('No accepted operation is saved here; observation cannot submit one.')
    endpoint, key = os.environ['SCIENTIFIC_MODELS_MCP_URL'], os.environ['SCIENTIFIC_MODELS_API_KEY']
    identity = receipt.get('identity', {})
    if identity.get('endpoint') != endpoint or identity.get('caller_fingerprint') != digest(key.encode()):
        raise ValueError('Receipt belongs to a different endpoint or caller; no operation was read.')
    headers = {'authorization': 'Bearer ' + key}
    origin = endpoint.removesuffix('/mcp').removesuffix('/mcp/')
    async with httpx2.AsyncClient(base_url=origin, headers=headers, timeout=180,
                                  trust_env=False, follow_redirects=False) as http:
        return await observe_operation(args, http, endpoint, headers, receipt, path)


def bind_uploaded_source(parameters: dict, artifact: dict) -> dict:
    """Resolve the documented uploaded-bundle placeholder, without editing input files.

    Callers write source={kind: uploaded-bundle} in their parameter JSON. The
    verified source upload/reuse supplies every artifact field; filenames and
    guessed artifact IDs are never required in the parameter file.
    """
    if (not isinstance(parameters, dict) or not isinstance(parameters.get('source'), dict)
            or parameters['source'].get('kind') != 'uploaded-bundle'):
        return parameters
    return {**parameters, 'source': {'kind': 'uploaded-bundle', **artifact}}


def batch_operation(document, *, operation_id=None, model_id=None):
    """Read the current native scientific status shared by both batch families."""
    if not isinstance(document, dict):
        raise ValueError('Scientific operation response must be an object.')
    actual_id = document.get('operation_id')
    if (not isinstance(actual_id, str)
            or not re.fullmatch(r'op-[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?', actual_id)
            or (operation_id is not None and actual_id != operation_id)
            or ('id' in document and document['id'] != actual_id)):
        raise ValueError('Scientific operation identity differs from its native operation ID.')
    if (not isinstance(document.get('model_id'), str) or not document['model_id']
            or (model_id is not None and document['model_id'] != model_id)):
        raise ValueError('Scientific operation model differs from the submitted model.')
    operation = document.get('operation')
    # A prepared but not acknowledged native admission has an ID, but no child
    # operation publication yet. Observing it does not authorize re-submission.
    if (operation is None and document.get('status') == 'ADMISSION_PENDING'
            and document.get('state') == 'admission-unknown'):
        return {'operation_id': actual_id, 'status': 'admission_pending', 'result_available': False}
    if (not isinstance(operation, dict) or operation.get('operation_id') != actual_id
            or not isinstance(document.get('status'), str)
            or not re.fullmatch(r'[A-Z][A-Z0-9_]*', document['status'])
            or operation.get('status') != document['status'].lower()
            or type(operation.get('result_available')) is not bool):
        raise ValueError('Scientific operation response has inconsistent current status fields.')
    return operation


def admission_binding(args, receipt):
    """Bind a locally retained ACK to its exact caller and immutable request.

    The server does not echo caller identity or the idempotency key in status.
    This journal is evidence from the original authenticated submission, not a
    guessed server field or an instruction to repeat admission.
    """
    identity, descriptor = receipt.get('identity', {}), receipt.get('request_descriptor', {})
    request = load_receipt(args.output / 'request.json')
    contract = load_receipt(args.output / 'contract.json')
    if (identity.get('model_id') != args.model or identity.get('idempotency_key') != args.idempotency_key
            or not identity.get('endpoint') or not identity.get('caller_fingerprint')
            or descriptor.get('tool') != args.tool or descriptor.get('operation') != args.operation
            or not isinstance(request, dict) or not isinstance(contract, dict)
            or contract.get('name') != args.tool
            or receipt.get('request_sha256') != digest(canonical(request))):
        raise ValueError('Saved admission has no matching immutable request and caller binding.')
    schema = contract['inputSchema']
    wrapped, _ = submission_contract(schema)
    Draft202012Validator(schema).validate(request)
    body = request['request'] if wrapped else request
    if request.get('idempotency_key') != args.idempotency_key or body.get('operation') != args.operation:
        raise ValueError('Saved admission differs from the original operation or idempotency key.')
    return {'identity_sha256': digest(canonical(identity)), 'request_sha256': receipt['request_sha256'],
            'tool': args.tool, 'operation': args.operation}


def recover_saved_admission(args, receipt):
    """Recover an exact acceptance saved just before the operation receipt.

    A missing ACK can be reconciled by replaying the exact idempotent request.
    A mismatched ACK is an evidence error, not permission to submit again.
    """
    if receipt.get('operation_id') or receipt.get('state') not in {'submitting', 'admission_unknown'}:
        return receipt
    try:
        binding = admission_binding(args, receipt)
        saved = load_receipt(args.output / 'admission.json')
        if saved is None:
            return receipt
        if not isinstance(saved, dict) or saved.get('binding') != binding:
            raise ValueError('No matching journaled acknowledgement.')
        operation = batch_operation(saved['response'], model_id=args.model)
    except (ValueError, KeyError, TypeError, RuntimeError) as error:
        raise RuntimeError('Previous admission is ambiguous; no matching request-bound acknowledgement '
                           'exists. Preserve the evidence for review; do not resubmit.') from error
    receipt.update(operation_id=operation['operation_id'], state=operation['status'], recovered_saved_admission=True)
    save(args.output / 'receipt.json', receipt)
    return receipt


def recoverable_admission(receipt):
    """Bound retries across worker restarts, not merely one Python invocation."""
    return bool(receipt and receipt.get('state') in {'submitting', 'admission_unknown'}
        and not receipt.get('operation_id') and receipt.get('request_sha256')
        and receipt.get('request_descriptor') and receipt.get('identity')
        and receipt.get('admission_replay_attempts', 0) < ADMISSION_REPLAY_ATTEMPTS)


async def admit(client, args, receipt, request):
    binding = admission_binding(args, receipt)
    receipt['state'] = 'submitting'
    save(args.output / 'receipt.json', receipt)
    try:
        accepted = await call(client, args.tool, request)
    except ExplicitRejection as error:
        receipt.update(state='rejected', last_rejection=error.error)
        save(args.output / 'receipt.json', receipt)
        raise
    except Exception:
        receipt['state'] = 'admission_unknown'
        save(args.output / 'receipt.json', receipt)
        raise
    operation = batch_operation(accepted, model_id=args.model)
    if operation['status'] == 'admission_pending':
        # A prepared ID is not native admission. Preserve the same request;
        # do not leave the client polling an operation that does not exist yet.
        receipt['state'] = 'admission_unknown'
        save(args.output / 'receipt.json', receipt)
        raise httpx2.ReadError('Exact request admission remains pending.')
    save(args.output / 'admission.json', {'binding': binding, 'response': accepted})
    save(args.output / 'submission.json', accepted)
    receipt.update(operation_id=operation['operation_id'], state=operation['status'])
    save(args.output / 'receipt.json', receipt)


async def replay_admission(args, receipt, headers):
    """The current Scientific AI contract deduplicates this exact owner/key/body.

    Never rebuild/upload a request, discover another tool, or choose an ID from
    a jobs list. Source and caller identity were checked by _run before entry.
    """
    admission_binding(args, receipt)
    if not recoverable_admission(receipt):
        raise RuntimeError('Exact admission reconciliation attempts exhausted; preserve the original request.')
    receipt['admission_replay_attempts'] = receipt.get('admission_replay_attempts', 0) + 1
    save(args.output / 'receipt.json', receipt)
    request = load_receipt(args.output / 'request.json')
    async with httpx2.AsyncClient(headers=headers, timeout=180, trust_env=False) as http:
        async with Client(streamable_http_client(receipt['identity']['endpoint'], http_client=http)) as client:
            await admit(client, args, receipt, request)


async def run(args) -> dict:
    while True:
        try:
            return await _run(args)
        except Exception as error:
            # Reuse the existing transport classifier, but only for a saved
            # idempotent admission. Scientific/application failures never retry.
            receipt = load_receipt(args.output / 'receipt.json')
            if recoverable_admission(receipt) and operation_read_failure(error)['retryable']:
                await asyncio.sleep(min(2 ** receipt.get('admission_replay_attempts', 0), 8))
                continue
            leaf = error
            while isinstance(leaf, BaseExceptionGroup) and len(leaf.exceptions) == 1:
                leaf = leaf.exceptions[0]
            if leaf is not error and isinstance(leaf, (ParameterPreflightError, SourcePreflightError, ToolAvailabilityError)):
                raise leaf from error
            raise


async def _run(args) -> dict:
    endpoint = os.environ["SCIENTIFIC_MODELS_MCP_URL"]
    key = os.environ["SCIENTIFIC_MODELS_API_KEY"]
    origin = endpoint.removesuffix("/mcp").removesuffix("/mcp/")
    source = FileSource(args.source)
    parameters = json.loads(args.parameters.read_text())
    identity = {"model_id": args.model, "source_sha256": digest(source),
                "parameters_sha256": digest(canonical(parameters)), "endpoint": endpoint,
                "caller_fingerprint": digest(key.encode()), "idempotency_key": args.idempotency_key}
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_path = args.output / "receipt.json"
    receipt = load_receipt(receipt_path)
    if receipt is None:
        receipt = {"identity": identity, "state": "prepared", "manifest_id": "scientist-cohort-" + str(uuid4())}
    if receipt["identity"] != identity:
        raise ValueError("Output directory belongs to a different request.")
    if getattr(args, 'observe_only', False) and not receipt.get('operation_id'):
        raise RuntimeError('Read-only observation requires an existing operation; nothing was submitted.')
    if receipt.get("state") == "verified":
        return receipt
    receipt = recover_saved_admission(args, receipt)
    save(receipt_path, receipt)
    headers = {"authorization": "Bearer " + key}
    if receipt.get('state') in {'submitting', 'admission_unknown'} and not receipt.get('operation_id'):
        await replay_admission(args, receipt, headers)
    if getattr(args, 'reconcile_only', False):
        if not receipt.get('operation_id'):
            raise RuntimeError('No prior admission exists to reconcile.')
        return receipt  # The study executor owns subsequent observation/results.
    async with httpx2.AsyncClient(base_url=origin, headers=headers, timeout=180,
                                  trust_env=False, follow_redirects=False) as http:
        if not receipt.get("operation_id"):
            async with httpx2.AsyncClient(headers=headers, timeout=180, trust_env=False) as mcp_http:
                async with Client(streamable_http_client(endpoint, http_client=mcp_http)) as client:
                    if receipt["state"] in {"submitting", "admission_unknown"}:
                        raise RuntimeError("Previous admission is ambiguous; inspect evidence before retrying.")
                    tools = (await client.list_tools()).tools
                    tool = next((item for item in tools if item.name == args.tool), None)
                    if tool is None:
                        detail = {'code': 'tool_not_in_authorized_catalog', 'model_id': args.model,
                            'tool_name': args.tool, 'uploads_submitted_this_invocation': False,
                            'inference_submitted_this_invocation': False,
                            'message': f'The MCP catalog returned for this API key does not expose {args.tool} '
                                f'for {args.model}. Check this key\'s model grants and the published model catalog. '
                                'This is not evidence of a transient connection failure or a missing MCP server. '
                                'Nothing was uploaded or submitted; do not retry unchanged, switch keys or substitute an engine.'}
                        save(args.output / 'tool-availability-error.json', detail)
                        raise ToolAvailabilityError(detail['message'])
                    save(args.output / "contract.json", tool.model_dump(mode="json", by_alias=True))
                    discovery = await call(client, 'get_model_schema', {'model_id': args.model,
                        'protocol': 'scientific-batch-v1', 'tool_name': args.tool})
                    save(args.output / 'model-contract.json', discovery)
                    contract = scientific_contract(discovery)
                    try:
                        args, compression = resolve_source_compression(contract, parameters, args, source)
                        preflight_source(contract, parameters, args, len(source))
                    except SourcePreflightError as error:
                        save(args.output / 'source-preflight-error.json', {
                            'code': 'invalid_source_metadata', 'message': str(error),
                            'source_sha256': identity['source_sha256'],
                            'input_contract_sha256': digest(canonical(contract.get('input_artifact_contract'))),
                            'uploads_submitted_this_invocation': False,
                            'inference_submitted_this_invocation': False})
                        raise
                    save(args.output / 'source-preflight.json', {
                        **compression, 'source_sha256': identity['source_sha256'], 'size_bytes': len(source),
                        'input_contract_sha256': digest(canonical(contract.get('input_artifact_contract'))),
                        'source_bytes_unchanged': True})
                    try:
                        preflight_parameters(tool.input_schema, parameters, source, args)
                    except ParameterPreflightError as error:
                        save(args.output / 'parameter-preflight-error.json', {
                            'code': 'invalid_parameter_file', 'message': str(error),
                            'parameters_sha256': identity['parameters_sha256'],
                            'tool_schema_sha256': digest(canonical(tool.input_schema)),
                            'uploads_submitted_this_invocation': False,
                            'inference_submitted_this_invocation': False})
                        raise
                    descriptor = {'entry_name': args.entry_name, 'semantic_type': args.semantic_type,
                                  'media_type': args.media_type, 'compression': args.compression,
                                  'tool': args.tool, 'operation': args.operation}
                    if receipt.get('request_descriptor', descriptor) != descriptor:
                        raise ValueError('Saved manifest role or operation differs; preserve the original receipt for explicit recovery.')
                    previous_manifest = args.output / 'input-manifest.json'
                    if 'manifest_artifact' in receipt and previous_manifest.exists():
                        previous = json.loads(previous_manifest.read_text())['entries'][0]
                        if previous['name'] != args.entry_name or previous['semantic_type'] != args.semantic_type:
                            raise ValueError('Existing uploaded manifest has a different semantic role; do not reuse it under changed arguments.')
                    receipt['request_descriptor'] = descriptor
                    save(receipt_path, receipt)
                    if "source_artifact" not in receipt:
                        reused_source = getattr(args, 'source_artifact', None)
                        receipt["source_artifact"] = source_reference(reused_source, source, args) if reused_source else await upload(
                            http, args.model, source, args.media_type, args.compression,
                            args.idempotency_key + "-source")
                        save(receipt_path, receipt)
                    receipt['source_artifact'] = validate_source_reference(receipt['source_artifact'], source, args)
                    parameters = bind_uploaded_source(parameters, receipt['source_artifact'])
                    manifest = {"schema": "fs2-serve.nebius.ai/scientific-artifact-manifest/v1",
                                "manifest_id": receipt["manifest_id"], "entries": [{
                                    "name": args.entry_name, "semantic_type": args.semantic_type,
                                    "artifact": receipt["source_artifact"]}]}
                    if contract.get('artifact_manifest_schema'):
                        Draft202012Validator(contract['artifact_manifest_schema']).validate(manifest)
                    save(args.output / "input-manifest.json", manifest)
                    if "manifest_artifact" not in receipt:
                        receipt["manifest_artifact"] = await upload(
                            http, args.model, canonical(manifest),
                            "application/vnd.fs2.scientific-manifest+json", "none",
                            args.idempotency_key + "-manifest")
                        save(receipt_path, receipt)
                    body = {"schema": "fs2-serve.nebius.ai/scientific-run-request/v1",
                               "operation": args.operation, "service_class": args.service_class,
                               "input_manifest": receipt["manifest_artifact"], "parameters": parameters,
                               "client_context": {"display_name": args.display_name,
                                                  "correlation_id": args.idempotency_key}}
                    request = submission_arguments(tool.input_schema, body, args.idempotency_key)
                    save(args.output / "request.json", request)
                    receipt['request_sha256'] = digest(canonical(request))
                    await admit(client, args, receipt, request)
        return await observe_operation(args, http, endpoint, headers, receipt, receipt_path)


def command_line() -> dict:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    if '--observe-output' in sys.argv:
        parser.add_argument('--observe-output', dest='output', required=True, type=Path,
                            help='Original receipt directory. Only observe/download this accepted operation.')
        parser.add_argument('--wait-seconds', type=float, default=180)
        parser.add_argument('--poll-seconds', type=float, default=10)
        args = parser.parse_args()
        with receipt_lock(args.output):
            return asyncio.run(observe_saved(args))
    if '--recover-operation-id' in sys.argv:
        parser.add_argument('--recover-operation-id', required=True,
                            help='Original succeeded operation ID; retrieve its verified outputs without new admission.')
        parser.add_argument('--output', required=True, type=Path,
                            help='New local receipt/artifact folder; existing scientific results are not overwritten.')
        args = parser.parse_args()
        # The lock is held in the existing local receipt-lock area, not S3/FUSE.
        with receipt_lock(args.output):
            return asyncio.run(recover_completed(args))
    parser.add_argument("--model", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument('--source-artifact', type=Path,
                        help='Optional finalized artifact JSON matching exact source bytes; never a filename substituted for an artifact ID.')
    parser.add_argument("--media-type", required=True)
    parser.add_argument("--compression", choices=("none", "gzip", "zstd"), default=None,
                        help='Explicit choices are preserved. Omitted compression binds a sole published gzip/zstd encoding only when actual source magic agrees; plain input keeps none. No recompression or filename inference.')
    parser.add_argument("--entry-name", required=True)
    parser.add_argument("--semantic-type", required=True)
    parser.add_argument("--parameters", required=True, type=Path,
                        help='Existing JSON containing ONLY the model parameter object, not a scientific-run request envelope. It is checked against the discovered submission parameters schema before any upload. For an uploaded-bundle source, set source to {"kind":"uploaded-bundle"}; the client injects the exact finalized --source upload/reference before validation and submission. Do not invent artifact fields. Other source kinds retain their published contract.')
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--service-class", choices=("customer-batch", "bulk-backfill"), default="customer-batch")
    parser.add_argument("--wait-seconds", type=float, default=1800)
    parser.add_argument("--poll-seconds", type=float, default=10)
    args = parser.parse_args()
    with receipt_lock(args.output):
        return asyncio.run(run(args))


def main() -> None:
    try:
        result = command_line()
    except Exception as error:
        leaf = error
        while isinstance(leaf, BaseExceptionGroup) and len(leaf.exceptions) == 1:
            leaf = leaf.exceptions[0]
        if isinstance(leaf, OperationObservationError):
            print(json.dumps(leaf.outcome), flush=True)
            code = {'authorization_failed': 77, 'operation_not_found': 66}.get(leaf.outcome['outcome'], 65)
        elif isinstance(leaf, ScientificOperationFailed):
            print(json.dumps(leaf.outcome), flush=True)
            code = 1
        elif isinstance(leaf, ToolAvailabilityError):
            print(json.dumps({'status': 'failed', 'code': 'tool_not_in_authorized_catalog',
                              'message': str(leaf)}), flush=True)
            code = 1
        elif isinstance(leaf, (ParameterPreflightError, SourcePreflightError)):
            print(json.dumps({'outcome': 'request_rejected', 'code': type(leaf).__name__,
                              'message': str(leaf)}), flush=True)
            code = 65
        else:
            raise  # Unexpected code errors remain diagnosable, with their traceback.
        raise SystemExit(code) from None
    # An observation timeout is a resumable incomplete operation, not shell
    # success. This also prevents `first && second` from overlapping admissions.
    raise SystemExit(0 if result['state'] == 'verified' else 75)


if __name__ == "__main__":
    main()
