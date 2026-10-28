"""Instructions cover the dependency race observed in the real QA client."""
from pathlib import Path


def test_bioemu2_requires_observed_tool_results_before_dependent_work():
    text = (Path(__file__).parents[1] / 'bioemu2/SKILL.md').read_text()
    for required in (
        'separate tool rounds',
        'Never predict operation IDs',
        'timeout/404/failed tool is not evidence of success',
        'Only copy a UI marker returned by a **successful** viewer call',
        'Contact conditioning is soft',
    ):
        assert required in text
