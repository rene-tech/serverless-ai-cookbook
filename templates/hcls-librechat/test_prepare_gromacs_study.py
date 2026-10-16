"""The standard composer uses existing verified publication and study schemas."""
import json
from pathlib import Path

import pytest

import prepare_gromacs_study as helper


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_STUDY_LOCK_ROOT', str(tmp_path / 'locks'))
    root = Path(__file__).resolve().parent
    monkeypatch.setattr(helper, 'BUNDLER', root.parents[1] / 'skills/scientific-ai/gromacs/scripts/make-input-bundle.py')
    monkeypatch.setattr(helper, 'RENDERER', root / 'native_md_preview.py')
    source = tmp_path / 'inputs'
    source.mkdir()
    (source / 'simulation.tpr').write_bytes(b'unit-test TPR fixture, not a real simulation')
    (source / 'protocol.txt').write_text('Retain the user protocol unchanged')
    calls = []
    def gmx(command, **kwargs):
        assert command == ['gmx', 'dump', '-s', str(source / 'simulation.tpr')]
        calls.append(command)
        kwargs['stdout'].write(b'inputrec:\n   integrator = md\n   dt = 0.002\n   nsteps = 500000\n   init-step = 0\n')
    monkeypatch.setattr(helper.subprocess, 'run', gmx)
    return source, tmp_path / 'prepared', calls


def test_exact_tpr_becomes_a_complete_existing_study_without_admission(prepared):
    source, output, calls = prepared
    original = {p.name: p.read_bytes() for p in source.iterdir()}
    result = helper.prepare(source, 'simulation.tpr', 1, output)
    assert result['finalized'] and not result['inference_submitted']
    assert result['protocol']['requested_steps'] == 500000
    assert not result['scientific_settings_changed']
    assert result['next_call']['arguments']['plan_file'] == result['plan_file']
    plan = json.loads(Path(result['plan_file']).read_bytes())
    assert [s['kind'] for s in plan['steps']] == ['batch', 'analysis']
    assert plan['steps'][1]['arguments']['parameters'] == {'expected_repeats': 1, 'structure_preview': True}
    parameters = json.loads((output / 'parameters.json').read_bytes())
    step = parameters['jobs'][0]['steps'][0]
    assert step['expected_outputs'] == ['final.gro', 'state.cpt']
    assert '-cpi' not in step['args'] and '-maxwarn' not in step['args']
    assert original == {p.name: p.read_bytes() for p in source.iterdir()}
    assert len(calls) == 1 and not (output / 'run').exists()


def test_replay_preserves_one_plan_and_refuses_changed_inputs(prepared):
    source, output, _ = prepared
    first = helper.prepare(source, 'simulation.tpr', 1, output)
    second = helper.prepare(source, 'simulation.tpr', 1, output)
    assert second['replayed'] and first['plan_file'] == second['plan_file']
    (source / 'protocol.txt').write_text('Different input bytes')
    with pytest.raises(RuntimeError, match='differ'):
        helper.prepare(source, 'simulation.tpr', 1, output)


@pytest.mark.parametrize('duration', [2, 0, -1, float('nan'), float('inf')])
def test_wrong_or_nonfinite_duration_cannot_admit_or_change_tpr(prepared, duration):
    source, output, _ = prepared
    with pytest.raises(ValueError):
        helper.prepare(source, 'simulation.tpr', duration, output)
    assert not output.exists()


@pytest.mark.parametrize('path', ['../elsewhere.tpr', '/tmp/other.tpr', 'coordinates.gro'])
def test_tpr_selection_must_be_explicit_inside_source(prepared, path):
    source, output, _ = prepared
    with pytest.raises(ValueError):
        helper.prepare(source, path, 1, output)


def test_output_cannot_contaminate_original_inputs(prepared):
    source, _, _ = prepared
    with pytest.raises(ValueError):
        helper.prepare(source, 'simulation.tpr', 1, source / 'outputs')
