"""Transport failures must never appear as fast scientific passes."""
import importlib.util
from pathlib import Path
import httpx
import pytest
import json
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('instruction_replay',
    Path(__file__).with_name('replay_agent_instructions.py'))
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_message_level_provider_error_is_not_a_success():
    result = replay.summarize([{'isCreatedByUser': False, 'content': None,
                               'error': True, 'text': 'illegal_model_request'}])
    assert result['errors'] == ['illegal_model_request']
    assert result['empty_answer']
    assert result['scientific_pass'] is None


def test_nonempty_response_still_needs_scientific_evaluation():
    result = replay.summarize([{'isCreatedByUser': False, 'content': [
        {'type': 'text', 'text': 'Here is my answer'},
        {'type': 'think', 'think': 'private'},
        {'type': 'tool_call', 'tool_call': {'name': 'inspect', 'runStepDurationMs': 250}}
    ]}])
    assert result['scientific_pass'] is None
    assert result['provider_usage'] is None
    assert result['tool_seconds'] == .25
    assert result['reasoning_characters'] == 7
    assert result['visible_text'] == 'Here is my answer'


def test_transient_observation_retry_preserves_failure_without_posting():
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(503 if len(requests) == 1 else 200, json={'active':False})
    warnings = []
    with httpx.Client(base_url='https://qa.invalid', transport=httpx.MockTransport(respond)) as client:
        result = replay.observe_get(client, '/api/agents/chat/status/existing-id', warnings, pause=lambda _:None)
    assert result.json() == {'active':False}
    assert [request.method for request in requests] == ['GET', 'GET']
    assert len({str(request.url) for request in requests}) == 1
    assert warnings[0]['http_status'] == 503


def test_persistent_observation_failure_remains_failed_and_bounded():
    warnings = []
    with httpx.Client(base_url='https://qa.invalid', transport=httpx.MockTransport(
            lambda _:httpx.Response(503))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            replay.observe_get(client, '/existing', warnings, pause=lambda _:None)
    assert len(warnings) == 3


def test_expired_qa_session_reauthenticates_once_without_resubmitting_work():
    requests = []
    def respond(request):
        requests.append((request.method, request.url.path))
        if request.url.path == '/api/auth/login':
            return httpx.Response(200, json={'token': 'replacement-test-token'})
        return httpx.Response(200 if request.headers.get('Authorization') ==
                              'Bearer replacement-test-token' else 401, json={'active': False})
    warnings = []
    with httpx.Client(base_url='https://qa.invalid', transport=httpx.MockTransport(respond)) as client:
        result = replay.observe_get(client, '/api/agents/chat/status/existing-id', warnings,
            reauthenticate=lambda: replay.authenticate(client, {'email': 'qa@example.invalid'}))
    assert result.json() == {'active': False}
    assert requests == [('GET', '/api/agents/chat/status/existing-id'),
                        ('POST', '/api/auth/login'), ('GET', '/api/agents/chat/status/existing-id')]
    assert warnings[0]['kind'] == 'qualification_session_expired'


def test_persistent_401_is_not_an_authentication_loop():
    refreshes = []
    with httpx.Client(base_url='https://qa.invalid', transport=httpx.MockTransport(
            lambda _: httpx.Response(401))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            replay.observe_get(client, '/existing', [], reauthenticate=lambda: refreshes.append(True))
    assert refreshes == [True]


def test_expired_session_is_checked_before_the_first_chat_post(tmp_path, monkeypatch):
    requests = []
    def respond(request):
        requests.append((request.method, request.url.path))
        if request.url.path == '/api/auth/login':
            return httpx.Response(200, json={'token': 'replacement-test-token'})
        if request.headers.get('Authorization') != 'Bearer replacement-test-token':
            return httpx.Response(401)
        if request.url.path == '/api/agents/chat':
            return httpx.Response(200, json={'conversationId': 'qa-conversation', 'streamId': 'qa-stream'})
        if request.url.path == '/api/agents/chat/status/qa-conversation':
            return httpx.Response(200, json={'active': False})
        if request.url.path == '/api/messages/qa-conversation':
            return httpx.Response(200, json=[{'isCreatedByUser': False, 'content': [{'type': 'text', 'text': 'Measured result'}]}])
        return httpx.Response(200, json=[])
    original_client = httpx.Client
    monkeypatch.setattr(replay.httpx, 'Client', lambda **kw: original_client(**kw, transport=httpx.MockTransport(respond)))
    session, login = tmp_path / 'session.json', tmp_path / 'login.json'
    session.write_text(json.dumps({'token': 'expired-test-token'}))
    login.write_text(json.dumps({'email': 'qa@example.invalid', 'password': 'test-fixture-only'}))
    args = SimpleNamespace(output=tmp_path / 'output', base_url='http://127.0.0.1:13203',
        session=session, login=login, instruction_text='Original instructions', cohort_id='qa',
        reasoning_effort=None, use_seeded_agent=True, deadline=30)
    result = replay.run_case(args, 'expired-test-token', {'id': 'seeded-qa', 'model': 'test-model',
        'instructions': 'Original instructions'}, {'case_id': 'test-case', 'prompt': 'Inspect inputs'}, 'test-model')
    assert requests[:4] == [('GET', '/api/agents'), ('POST', '/api/auth/login'),
                           ('GET', '/api/agents'), ('POST', '/api/agents/chat')]
    assert requests.count(('POST', '/api/agents/chat')) == 1
    assert result['transport_warnings'][0]['kind'] == 'qualification_session_expired'
    assert result['scientific_pass'] is None
