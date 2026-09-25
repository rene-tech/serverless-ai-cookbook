#!/usr/bin/env python3
"""Dedicated clinical ASR client: workspace bytes over HTTP, typed remote MCP."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Annotated
from urllib.parse import urlencode, urlsplit

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.mcpserver import MCPServer
from pydantic import Field

mcp = MCPServer('Medical speech on Nebius', instructions='This is the dedicated fine-tuned clinical ASR endpoint, not the existing Scientific AI model catalog. Read describe_clinical_asr first. Upload workspace WAV bytes with upload_clinical_workspace_audio, then pass its immutable artifact reference to transcribe_clinical_audio. Poll the SAME operation; never resubmit because a wait expired. Full results are saved in Workspace. Synthetic/de-identified inputs only; all transcripts need clinician review. Keep base-versus-tuned identity explicit and do not claim better held-out accuracy without measured evidence.')
ROOT = Path(os.environ.get('SCIENTIFIC_WORKSPACE', '/workspace')).resolve()


def connection():
    endpoint = os.environ.get('SCIENTIFIC_MEDICAL_SPEECH_HTTP_URL', '').rstrip('/')
    parsed = urlsplit(endpoint)
    key = os.environ.get('SCIENTIFIC_MEDICAL_SPEECH_API_KEY', '')
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not key:
        raise ValueError('Dedicated medical speech HTTPS endpoint and server credential must be configured')
    return endpoint, key


def workspace_file(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Supply a workspace-relative path')
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT or not path.is_file():
        raise ValueError('Existing file must be inside the mounted workspace')
    return path


def unpack(value):
    response = value if isinstance(value, dict) else value.model_dump(mode='json', by_alias=True)
    data = response.get('structuredContent')
    if data is None:
        parts = [entry['text'] for entry in response.get('content', []) if entry.get('type') == 'text']
        if len(parts) != 1:
            raise ValueError('Expected one structured medical speech result')
        data = json.loads(parts[0])
    if response.get('isError') and 'error' not in data:
        return {'error': {'code': 'remote_tool_failed', 'retryable': False, 'durable_admission': 'unknown'}}
    return data


async def remote(tool, arguments):
    endpoint, key = connection()
    try:
        async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + key}, timeout=40, trust_env=False, follow_redirects=False) as http:
            async with Client(streamable_http_client(endpoint + '/mcp', http_client=http)) as client:
                return unpack(await client.call_tool(tool, arguments))
    except Exception:
        # A lost submit response does not mean no work was accepted.
        return {'error': {'code': 'medical_endpoint_connection_failed', 'retryable': True,
                          'durable_admission': 'unknown' if tool == 'transcribe_clinical_audio' else False},
                'guidance': 'Keep the same artifact and idempotency key; never invent a fresh submit identity to recover.'}


def retain(operation):
    if operation.get('status') != 'succeeded' or not isinstance(operation.get('result'), dict):
        return operation
    identifier = operation.get('id', '')
    if not re.fullmatch(r'[a-f0-9-]{36}', identifier):
        raise ValueError('Invalid operation identity')
    result = operation['result']
    if not isinstance(result.get('text'), str):
        raise ValueError('Completed operation has no transcript')
    directory = (ROOT / '.medical-speech' / identifier).resolve()
    if not directory.is_relative_to(ROOT):
        raise ValueError('Result directory must remain inside the mounted workspace')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    artifacts = []
    for name, content in [('result.json', json.dumps(operation, indent=2).encode()), ('transcript.txt', (result['text'] + '\n').encode())]:
        destination = directory / name
        if destination.exists() and destination.read_bytes() != content:
            raise ValueError('Existing result bytes differ; refusing to overwrite evidence')
        if not destination.exists():
            # /workspace is an isolated Object Storage mount: byte writes and
            # read-back hashes, not POSIX chmod or atomic-rename guarantees.
            destination.write_bytes(content)
        if destination.read_bytes() != content:
            raise ValueError('Workspace result read-back differs from model bytes')
        relative = destination.relative_to(ROOT).as_posix()
        artifacts.append({'name': name, 'path': relative, 'sha256': hashlib.sha256(content).hexdigest(),
                          'size_bytes': len(content), 'workspace_url': '/demos?' + urlencode({'tab': 'workspace', 'file': relative})})
    return {'id': identifier, 'status': 'succeeded', 'model_id': operation.get('model_id'),
            'runtime': result.get('runtime'), 'audio_seconds': result.get('audio_seconds'),
            'elapsed_seconds': result.get('elapsed_seconds'), 'word_count': len(result.get('words', [])),
            'artifacts': artifacts, 'clinical_validation': False,
            'guidance': 'Read the saved full transcript/result; do not reconstruct its text from a tool summary. Use clinical_report_from_workspace for a separate physician-reviewed draft.'}


@mcp.tool()
async def describe_clinical_asr() -> dict:
    """Read the live dedicated ASR model/checkpoint identity, protocol, limits and privacy boundaries."""
    return await remote('describe_clinical_asr', {})


@mcp.tool()
async def upload_clinical_workspace_audio(workspace_path: Annotated[str, Field(min_length=1, max_length=1000)]) -> dict:
    """Upload one existing mono16k PCM16 WAV directly from the mounted workspace over HTTP. No raw bytes/base64 enter chat. Returns immutable artifact reference for transcribe_clinical_audio; this step does not run ASR."""
    path = workspace_file(workspace_path)
    if path.suffix.lower() != '.wav' or not 44 < path.stat().st_size <= 64 * 1024 * 1024:
        raise ValueError('Use mono16k PCM16 WAV up to 64MiB; convert non-WAV audio with the installed ffmpeg first')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    endpoint, key = connection()
    async with httpx2.AsyncClient(timeout=120, trust_env=False, follow_redirects=False) as client:
        with path.open('rb') as stream:
            response = await client.post(endpoint + '/v1/artifacts', headers={'Authorization': 'Bearer ' + key}, files={'file': (path.name, stream, 'audio/wav')})
    value = response.json()
    if not response.is_success:
        return value if isinstance(value.get('error'), dict) else {'error': {'code': 'artifact_upload_failed', 'retryable': False, 'durable_admission': False}}
    if value.get('sha256') != digest or value.get('artifact') != 'artifact:sha256:' + digest:
        raise ValueError('Uploaded artifact does not match the exact source audio bytes')
    return {**value, 'workspace_path': path.relative_to(ROOT).as_posix(), 'inference_submitted': False}


@mcp.tool()
async def transcribe_clinical_audio(audio_artifact: Annotated[str, Field(pattern=r'^artifact:sha256:[a-f0-9]{64}$')],
                                    idempotency_key: Annotated[str, Field(min_length=8, max_length=128)],
                                    model: str = 'nemotron-clinical-en') -> dict:
    """Submit one immutable artifact to the dedicated medical Nemotron model, with one stable idempotency key. Returns durable operation ID; poll it with get_clinical_transcription. Do not substitute an existing platform model or change keys on retry."""
    return retain(await remote('transcribe_clinical_audio', {'audio_artifact': audio_artifact, 'idempotency_key': idempotency_key, 'model': model}))


@mcp.tool()
async def get_clinical_transcription(operation_id: Annotated[str, Field(pattern=r'^[a-f0-9-]{36}$')],
                                     wait_seconds: Annotated[int, Field(ge=0, le=25)] = 15) -> dict:
    """Observe the SAME dedicated operation for a bounded wait. Completed exact transcript/JSON are saved under .medical-speech in Workspace, with hashes/download links. Waiting never submits more inference."""
    deadline = time.monotonic() + wait_seconds
    while True:
        value = await remote('get_clinical_transcription', {'operation_id': operation_id})
        if value.get('status') in {'succeeded', 'failed', 'cancelled'} or 'error' in value and value['error'] or time.monotonic() >= deadline:
            return retain(value)
        await asyncio.sleep(min(1, max(0, deadline - time.monotonic())))


@mcp.tool()
async def cancel_clinical_transcription(operation_id: Annotated[str, Field(pattern=r'^[a-f0-9-]{36}$')]) -> dict:
    """Request cancellation of one dedicated medical ASR operation, preserving its original identity and outcome."""
    return await remote('cancel_clinical_transcription', {'operation_id': operation_id})


if __name__ == '__main__':
    mcp.run(transport='stdio')
