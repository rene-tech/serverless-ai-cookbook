"""Mode-selection guidance must not equate prefix continuation with restyling."""
from pathlib import Path

ROOT = Path(__file__).parent


def test_recorded_motion_guidance_is_seeded_and_uses_live_contracts():
    # The primary agent deliberately loads domain procedures through skills,
    # rather than appending the old full manual to every conversation.
    seed = (ROOT / 'seed-workbench.js').read_text()
    core = (ROOT / 'agent-instructions.md').read_text()
    assert 'instructions: coreAgentInstructions' in seed
    assert 'skills_enabled: true' in seed
    assert 'Read the relevant skill for execution' in core
    skill = (ROOT.parents[1] / 'skills/scientific-ai/generative-media/SKILL.md').read_text()
    assert 'whole-sequence controls' in skill
    assert 'Do not silently substitute prefix' in skill
    assert 'Numeric action-array' in skill
    assert 'augmentation.mode: transfer' in skill
    assert 'augmentation.conditioning.controls' in skill
    assert 'do not copy the LeRobot parameter shape into the native request' in skill
    assert 'does **not** establish' in skill
    assert 'not yet live-tested' not in skill
