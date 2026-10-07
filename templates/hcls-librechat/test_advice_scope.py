"""Generic advice boundaries; actual model behavior needs exact-image replay."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def advice():
    text = (ROOT / 'agent-instructions.md').read_text()
    return ' '.join(text.split('**Explain or recommend:**', 1)[1]
                   .split('- **Inspect existing data:**', 1)[0].split())


def test_advice_keeps_method_compatibility_and_no_unsolicited_execution():
    text = advice()
    assert 'method/compatibility advice' in text
    assert 'execution, installation or catalog discovery' in text
    assert 'Do not parameterize or simulate.' in text


def test_unrequested_properties_are_omitted_and_requested_facts_are_evidence_bound():
    text = advice()
    assert 'Do not volunteer molecule-specific counts or properties the user did not ask for.' in text
    assert 'If requested, compute them from the exact supplied input with tools' in text
    assert 'cite that evidence, never memory' in text
    assert 'primary documentation for uncertain method/convention claims' in text


def test_scope_rule_is_generic_not_a_fixture_answer_or_added_budget():
    text = advice()
    assert not re.search(r'\d|SMILES|hydroxyl|formula|case_id|replay', text)
    assert len((ROOT / 'agent-instructions.md').read_text()) < 10000
