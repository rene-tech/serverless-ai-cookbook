"""Transport failures must never appear as fast scientific passes."""
import importlib.util
from pathlib import Path

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
