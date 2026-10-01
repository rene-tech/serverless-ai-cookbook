"""Transport failures must never appear as fast scientific passes."""
import importlib.util
from pathlib import Path
import httpx
import pytest

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
