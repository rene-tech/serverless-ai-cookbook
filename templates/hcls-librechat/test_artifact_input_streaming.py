"""Customer inputs never require a whole multi-gigabyte object in client RAM."""
import asyncio
import hashlib
from pathlib import Path
import tracemalloc

import pytest

from test_scientific_batch_client import client


def test_file_source_hash_magic_and_chunks_are_bounded(tmp_path, monkeypatch):
    path = tmp_path / 'input.tar.gz'
    chunk = b'\x1f\x8b\x08\x00' + b'x' * (1024**2 - 4)
    expected = hashlib.sha256()
    with path.open('wb') as output:
        for _ in range(96):
            output.write(chunk)
            expected.update(chunk)
    monkeypatch.setattr(Path, 'read_bytes', lambda _: (_ for _ in ()).throw(AssertionError('unbounded read')))

    async def consume(source):
        checksum, size = hashlib.sha256(), 0
        async for value in source.chunks():
            assert len(value) <= client.ARTIFACT_CHUNK_BYTES
            checksum.update(value)
            size += len(value)
        return checksum.hexdigest(), size

    tracemalloc.start()
    try:
        source = client.FileSource(path)
        actual = asyncio.run(consume(source))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert source.startswith(b'\x1f\x8b\x08')
    assert client.digest(source) == expected.hexdigest()
    assert actual == (expected.hexdigest(), 96 * 1024**2)
    assert peak < 8 * 1024**2


@pytest.mark.parametrize('during', [False, True])
def test_source_mutation_prevents_completion(tmp_path, during):
    path = tmp_path / 'data'
    path.write_bytes(b'a' * (client.ARTIFACT_CHUNK_BYTES * 3))
    source = client.FileSource(path)

    async def changed():
        iterator = source.chunks()
        if during:
            await anext(iterator)
        with path.open('r+b') as output:
            output.seek(client.ARTIFACT_CHUNK_BYTES * 2)
            output.write(b'b')
        async for _ in iterator:
            pass

    with pytest.raises(ValueError, match='Input changed'):
        asyncio.run(changed())


def test_same_origin_upload_streams_and_finalizes_exact_metadata(tmp_path):
    path = tmp_path / 'data'
    path.write_bytes(b'bounded input' * 10000)
    source = client.FileSource(path)
    calls = []

    class Response:
        is_success = True
        def __init__(self, value):
            self.value = value
        def json(self):
            return self.value

    class HTTP:
        async def post(self, path, *, json, headers=None):
            calls.append(path)
            if path.endswith('/uploads'):
                return Response({'max_content_bytes': len(source), 'content_path': '/upload',
                                 'upload_id': 'fixture', 'operation_id': 'operation'})
            return Response({'artifact_id': 'stored', 'sha256': source.sha256, 'size_bytes': len(source),
                             'media_type': 'application/octet-stream', 'compression': 'none'})
        async def put(self, path, *, content, headers):
            assert not isinstance(content, bytes)
            checksum = hashlib.sha256()
            async for chunk in content:
                checksum.update(chunk)
            assert checksum.hexdigest() == source.sha256
            assert headers['content-length'] == str(len(source))
            return Response({})

    result = asyncio.run(client.upload(HTTP(), 'gromacs', source, 'application/octet-stream', 'none', 'fixture'))
    assert result['sha256'] == source.sha256 and len(calls) == 2


def test_large_presigned_upload_streams_without_forwarding_platform_credentials(tmp_path, monkeypatch):
    path = tmp_path / 'input'
    path.write_bytes(b'large scientific input fixture')
    source = client.FileSource(path)
    calls = []

    class Response:
        is_success = True
        def __init__(self, value):
            self.value = value
        def json(self):
            return self.value

    class HTTP:
        async def post(self, path, *, json, headers=None):
            calls.append(path)
            if path.endswith('/uploads'):
                return Response({'max_content_bytes': 1, 'upload_id': 'fixture', 'operation_id': 'operation',
                    'handle': {'url': 'https://storage.example.test/input', 'headers': {'x-object': 'bound'}}})
            return Response({'artifact_id': 'stored', 'sha256': source.sha256, 'size_bytes': len(source),
                             'media_type': 'application/octet-stream', 'compression': 'none'})

    class Storage:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        async def put(self, url, *, content, headers):
            assert url == 'https://storage.example.test/input'
            assert headers == {'x-object': 'bound', 'content-length': str(len(source))}
            checksum = hashlib.sha256()
            async for chunk in content:
                checksum.update(chunk)
            assert checksum.hexdigest() == source.sha256
            return Response({})

    def storage_client(**kwargs):
        assert kwargs == {'timeout': 600, 'trust_env': False, 'follow_redirects': False}
        return Storage()

    monkeypatch.setattr(client.httpx2, 'AsyncClient', storage_client)
    result = asyncio.run(client.upload(HTTP(), 'gromacs', source, 'application/octet-stream', 'none', 'fixture'))
    assert result['sha256'] == source.sha256 and len(calls) == 2
