import json

from verify_agent_delivery import requires_verbatim_measurements, workspace_selection


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
