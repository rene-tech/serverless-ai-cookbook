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
from clinical_report import Reporter, report_limits, bounded_completion_schema, generation_warnings, ContextBudgetExceeded, optional_questions
from document import completion_schema


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
    assert receipt['body']['response_format']['json_schema']['schema']['properties']['facts']['maxItems'] == 8
    assert 'emit each supported fact ONCE' in receipt['body']['messages'][0]['content']
    assert receipt['context_budget'] == {'input_tokens': 1000, 'max_output_tokens': 2048, 'context_tokens': 8192, 'reserve_tokens': 64}
    assert value.chunk_chars == 3500 and value.review_workers == 1
    value.complete('extract-000', 'source only', {'segments': []})
    assert sum(request.url.path.endswith('completions') for request in calls) == 1
    value.close()


def test_over_budget_never_sends_partial_source_to_inference(tmp_path, monkeypatch):
    value, calls = reporter(tmp_path, monkeypatch, 7000)
    with pytest.raises(ContextBudgetExceeded, match='clinical_context_budget_exceeded') as failure:
        value.complete('extract-000', 'source only', {'segments': [{'id': 'S1', 'text': 'unchanged full source'}]})
    assert failure.value.stage == 'extract-000'
    assert value.generation_warnings == []
    assert len(calls) == 2
    assert not (tmp_path / 'calls').exists()
    value.close()


def test_optional_question_exact_preflight_preserves_facts_without_admitting_model_request(tmp_path, monkeypatch):
    value, calls = reporter(tmp_path, monkeypatch, 7000)
    facts = [{'id': 'F0001', 'statement': 'No fever.', 'source_phrases': [{'quote': 'No fever.'}]}]
    before = json.dumps(facts, sort_keys=True)
    uncertainties = []
    questions = optional_questions(value, {'language': 'en', 'facts': facts, 'uncertainties': []}, facts, uncertainties)
    assert questions == [] and json.dumps(facts, sort_keys=True) == before
    assert [request.url.path for request in calls] == ['/v1/models', '/tokenize']
    assert value.generation_warnings[0]['code'] == 'optional_questions_context_budget_exceeded'
    assert value.generation_warnings[0]['provider_request_admitted'] is False
    assert uncertainties[0]['kind'] == 'optional_stage_omitted'
    receipt = json.loads((tmp_path / 'calls/questions/preflight-rejected.json').read_text())
    assert receipt['status'] == 'not_admitted'
    assert receipt['context_budget']['input_tokens'] == 7000
    assert len(receipt['request_sha256']) == 64
    assert not (tmp_path / 'calls/questions/request.json').exists()
    assert not (tmp_path / 'calls/questions/response.json').exists()
    value.close()


def test_other_optional_question_failures_and_required_stage_budget_remain_fatal():
    for error in [ValueError('malformed provider response'), ContextBudgetExceeded('extract-000', {})]:
        def fail(*_args):
            raise error
        value = SimpleNamespace(complete=fail, generation_warnings=[])
        with pytest.raises(type(error), match=str(error)):
            optional_questions(value, {}, [], [])
        assert value.generation_warnings == []


def test_invalid_limits_fail_closed(monkeypatch):
    monkeypatch.setenv('CLINICAL_REPORT_REVIEW_WORKERS', '100')
    with pytest.raises(ValueError, match='outside supported bounds'):
        report_limits()


def test_bounded_generation_does_not_change_default_schema_or_fabricate_empty_facts():
    data = {'segments': [{'id': 'S1', 'text': 'No fever.'}]}
    assert completion_schema('extract-000', data)['properties']['facts']['maxItems'] == 50
    schema = bounded_completion_schema('extract-000', data)
    assert schema['properties']['facts']['maxItems'] == 8
    assert schema['properties']['facts']['minItems'] == 0
    assert schema['properties']['uncertainties']['maxItems'] == 8
    assert schema['properties']['excluded_segments']['maxItems'] == 1
    assert generation_warnings('extract-000', {'facts': [], 'uncertainties': []}) == []


def test_cap_and_repetition_are_visible_incompleteness_not_repair():
    fact = {'section': 'history', 'source_phrases': [{'source_id': 'S1', 'quote': 'No fever.'}]}
    value = {'facts': [fact] * 8, 'uncertainties': []}
    warnings = generation_warnings('extract-000', value)
    assert [item['code'] for item in warnings] == ['bounded_generation_capacity_reached', 'repeated_extraction_candidates']
    assert warnings[-1]['count'] == 7
    assert len(value['facts']) == 8  # Raw candidates are not silently repaired/discarded.
