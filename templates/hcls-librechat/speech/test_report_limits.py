"""Exact context accounting and immutable request provenance; no model calls."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / 'skills/scientific-ai/clinical-documentation/scripts'
sys.path.insert(0, str(SCRIPTS))
from clinical_report import Reporter, report_limits


def reporter(tmp_path, monkeypatch, input_tokens=1000):
    for name, value in {'MAX_OUTPUT_TOKENS': '2048', 'CONTEXT_TOKENS': '8192',
                        'CHUNK_CHARS': '3500', 'REVIEW_WORKERS': '1'}.items():
        monkeypatch.setenv('CLINICAL_REPORT_' + name, value)
    calls = []
    def handle(request):
        calls.append(request)
        assert request.headers['Authorization'] == 'Bearer private-mock'
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [{'id': 'fastino-healthcare'}]})
        if request.url.path == '/tokenize':
            return httpx.Response(200, json={'count': input_tokens, 'max_model_len': 8192})
        assert request.url.path == '/v1/chat/completions'
        body = json.loads(request.content)
        assert body['max_tokens'] <= 2048
        assert body['chat_template_kwargs'] == {'enable_thinking': False}
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    actual = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: actual(**kwargs, transport=httpx.MockTransport(handle)))
    value = Reporter(SimpleNamespace(output=tmp_path), 'fastino-healthcare', 'https://report.test/v1', 'private-mock')
    return value, calls


def test_exact_tokenizer_precedes_inference_and_receipt_matches_request(tmp_path, monkeypatch):
    value, calls = reporter(tmp_path, monkeypatch)
    value.complete('extract-000', 'source only', {'segments': []})
    assert [request.url.path for request in calls] == ['/v1/models', '/tokenize', '/v1/chat/completions']
    receipt = json.loads((tmp_path / 'calls/extract-000/request.json').read_text())
    assert receipt['body'] == json.loads(calls[-1].content)
    assert receipt['context_budget'] == {'input_tokens': 1000, 'max_output_tokens': 2048, 'context_tokens': 8192, 'reserve_tokens': 64}
    assert value.chunk_chars == 3500 and value.review_workers == 1
    value.complete('extract-000', 'source only', {'segments': []})
    assert sum(request.url.path.endswith('completions') for request in calls) == 1
    value.close()


def test_over_budget_never_sends_partial_source_to_inference(tmp_path, monkeypatch):
    value, calls = reporter(tmp_path, monkeypatch, 7000)
    with pytest.raises(ValueError, match='clinical_context_budget_exceeded'):
        value.complete('extract-000', 'source only', {'segments': [{'id': 'S1', 'text': 'unchanged full source'}]})
    assert len(calls) == 2
    assert not (tmp_path / 'calls').exists()
    value.close()


def test_invalid_limits_fail_closed(monkeypatch):
    monkeypatch.setenv('CLINICAL_REPORT_REVIEW_WORKERS', '100')
    with pytest.raises(ValueError, match='outside supported bounds'):
        report_limits()
