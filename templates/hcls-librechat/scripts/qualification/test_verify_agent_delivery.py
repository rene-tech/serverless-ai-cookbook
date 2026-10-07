import json

from verify_agent_delivery import (expected_rejection, requires_verbatim_measurements,
                                   tool_failures, workspace_selection)


def test_documented_workspace_links_match_the_existing_browser_selection():
    expected = ('study/a b', 'study/a b/result.csv')
    assert workspace_selection('/demos?tab=workspace&path=study%2Fa+b&file=study%2Fa+b%2Fresult.csv') == expected
    assert workspace_selection('/demos?tab=workspace&path=study%2Fa+b&file=result.csv') == expected
    assert workspace_selection('/demos?path=/workspace/study/a%20b&file=/workspace/study/a%20b/result.csv') == expected
    assert workspace_selection('/demos?path=study') == ('study', '')


def test_paths_are_not_silently_normalized_past_the_servers_validation():
    assert workspace_selection('/demos?path=study&file=../other.csv') == ('study', '../other.csv')


def test_only_file_cards_allow_prose_while_scientific_measurements_stay_exact():
    def call(kinds):
        return {'args': json.dumps({'results': [{'kind': kind, 'path': 'fixture'} for kind in kinds]})}
    assert not requires_verbatim_measurements(call(['file', 'file']))
    for kinds in (['mmcif'], ['openff'], ['native-md'], ['mmcif', 'file'], []):
        assert requires_verbatim_measurements(call(kinds))
    assert requires_verbatim_measurements({})


def test_plain_text_inspector_failure_is_not_lost_without_json_status():
    calls = [{'name': 'inspect_mmcif_inventory', 'output':
              'Structure inventory failed: Traceback (most recent call last):\n'
              'FileNotFoundError: missing explicit fixture\n'}]
    errors = tool_failures(calls)
    assert len(errors) == 1 and errors[0]['exception_type'] == 'FileNotFoundError'
    assert expected_rejection(errors[0], 'missing-file', ['missing-file'])
    assert not expected_rejection(errors[0], 'real-input', ['missing-file'])
    assert not expected_rejection(errors[0], 'missing-file', [])


def test_named_negative_cannot_hide_transport_or_unrelated_errors():
    calls = [{'name': 'inspect_mmcif_inventory', 'output': 'MCP error -32000: Request timed out'},
             {'name': 'execute_command', 'output': 'Traceback (most recent call last):\nValueError: wrong shape'}]
    errors = tool_failures(calls)
    assert len(errors) == 2
    assert all(not expected_rejection(error, 'missing-file', ['missing-file']) for error in errors)
    assert not tool_failures([{'name': 'read_file', 'output': 'Missing values are unknown, not zero.'}])
