"""Dedicated MCP bridge ownership, identity, compact exact artifacts and SDK wiring."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest

SOURCE = Path(__file__).with_name('medical-mcp.py')
spec = importlib.util.spec_from_file_location('medical_mcp', SOURCE)
medical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(medical)


def test_workspace_symlink_and_traversal_are_rejected(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'; root.mkdir()
    outside = tmp_path / 'outside.wav'; outside.write_bytes(b'private')
    (root / 'link.wav').symlink_to(outside)
    monkeypatch.setattr(medical, 'ROOT', root)
    for value in ['../outside.wav', str(outside), 'link.wav']:
        with pytest.raises(ValueError, match='inside the mounted workspace'):
            medical.workspace_file(value)


def test_completed_result_is_retained_without_llm_transcript_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(medical, 'ROOT', tmp_path)
    operation = {'id': str(uuid4()), 'status': 'succeeded', 'model_id': 'nemotron-clinical-en',
                 'result': {'text': 'metoprolol 25 milligrams', 'words': [], 'runtime': {'checkpoint_sha256': 'a' * 64}}}
    result = medical.retain(operation)
    assert 'text' not in result
    transcript = next(item for item in result['artifacts'] if item['name'] == 'transcript.txt')
    assert (tmp_path / transcript['path']).read_bytes() == b'metoprolol 25 milligrams\n'
    assert transcript['sha256'] == hashlib.sha256(b'metoprolol 25 milligrams\n').hexdigest()
    assert medical.retain(operation) == result
    operation['result']['text'] = 'changed'
    with pytest.raises(ValueError, match='refusing to overwrite'):
        medical.retain(operation)


def test_structured_errors_preserved():
    error = {'error': {'code': 'queue_full', 'durable_admission': False, 'retryable': True}}
    assert medical.unpack({'structuredContent': error}) == error


def test_real_stdio_sdk_lists_bounded_typed_tools_and_rejects_invalid_artifact(tmp_path):
    from mcp import Client
    from mcp.client.stdio import stdio_client, StdioServerParameters
    async def exercise():
        server = StdioServerParameters(command=sys.executable, args=[str(SOURCE)], env={'SCIENTIFIC_WORKSPACE': str(tmp_path)})
        async with Client(stdio_client(server)) as client:
            result = await client.list_tools()
            tools = {tool.name: tool.model_dump(by_alias=True) for tool in result.tools}
            assert set(tools) == {'describe_clinical_asr', 'upload_clinical_workspace_audio',
                                  'transcribe_clinical_audio', 'get_clinical_transcription', 'cancel_clinical_transcription'}
            assert tools['transcribe_clinical_audio']['inputSchema']['properties']['audio_artifact']['pattern'].startswith('^artifact:sha256:')
            invalid = await client.call_tool('transcribe_clinical_audio', {'audio_artifact': '/etc/passwd', 'idempotency_key': 'stable-test-key'})
            assert invalid.is_error
    asyncio.run(exercise())
