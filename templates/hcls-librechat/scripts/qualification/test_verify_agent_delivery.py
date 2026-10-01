from verify_agent_delivery import workspace_selection


def test_documented_workspace_links_match_the_existing_browser_selection():
    expected = ('study/a b', 'study/a b/result.csv')
    assert workspace_selection('/demos?tab=workspace&path=study%2Fa+b&file=study%2Fa+b%2Fresult.csv') == expected
    assert workspace_selection('/demos?tab=workspace&path=study%2Fa+b&file=result.csv') == expected
    assert workspace_selection('/demos?path=/workspace/study/a%20b&file=/workspace/study/a%20b/result.csv') == expected
    assert workspace_selection('/demos?path=study') == ('study', '')


def test_paths_are_not_silently_normalized_past_the_servers_validation():
    assert workspace_selection('/demos?path=study&file=../other.csv') == ('study', '../other.csv')
