"""Impossible segmented output names fail before any study/model admission."""
import copy
import json
from pathlib import Path

import pytest
from test_workflow_discovery import execution, study, mounted


def plan(folder, outputs, command='mdrun', model='gromacs'):
    parameters = folder / 'parameters.json'
    parameters.write_text(json.dumps({'jobs': [{'id': 'md', 'steps': [
        {'id': 'production', 'command': command, 'args': ['-deffnm', 'md'], 'expected_outputs': outputs}]}]}))
    return {'schema': 'scientific-workflow/v2', 'title': 'Native MD', 'steps': [{
        'id': 'simulate', 'kind': 'batch', 'model': model, 'tool': 'submit_gromacs_workflow',
        'operation': 'run-workflow', 'source': str(folder / 'input.tar.gz'),
        'parameters': str(parameters), 'entry_name': 'gromacs-inputs',
        'semantic_type': 'gromacs-input-bundle/v1', 'media_type': 'application/x-tar',
        'compression': 'gzip', 'idempotency_key': 'test-only', 'display_name': 'Native MD'}],
        'deliverables': [{'name': 'Native mapping', 'role': 'support',
                          'source': {'step': 'simulate', 'file': 'native-files.json'}}]}


@pytest.mark.parametrize('mode', ['object', 'text', 'file'])
def test_exact_observed_failed_request_is_rejected_before_admission(mounted, monkeypatch, mode):
    value = plan(mounted, ['md.xtc', 'md.cpt', 'md.gro', 'md.log', 'md.edr'])
    before = (mounted / 'parameters.json').read_bytes()
    monkeypatch.setattr(study, 'submit', lambda *a: pytest.fail('No GPU or saved study admission'))
    args = {'output_directory': str(mounted / 'run')}
    if mode == 'file':
        path = mounted / 'plan.json'; path.write_text(json.dumps(value)); args['plan_file'] = str(path)
    else:
        args['study'] = value if mode == 'object' else json.dumps(value)
    with pytest.raises(ValueError, match='No study was admitted.*-noappend') as error:
        execution.run_scientific_workflow(args)
    assert 'trjcat' in str(error.value) and 'correct the draft and retry' in str(error.value)
    assert (mounted / 'parameters.json').read_bytes() == before
    assert not (mounted / 'run').exists()


@pytest.mark.parametrize('command,outputs,model', [
    ('mdrun', ['md.gro', 'md.cpt'], 'gromacs'),
    ('mdrun', [], 'gromacs'),
    ('mdrun', ['md.part0001.xtc'], 'gromacs'),
    ('trjcat', ['complete.xtc'], 'gromacs'),
    ('mdrun', ['md.log'], 'another-model'),
])
def test_valid_or_other_engine_outputs_are_not_rewritten(mounted, monkeypatch, command, outputs, model):
    value = plan(mounted, outputs, command, model)
    before = copy.deepcopy(value)
    submitted = []
    def submit(p, out):
        submitted.append(copy.deepcopy(p))
        return {'id': 'private-receipt', 'output_directory': str(out), 'steps': {}, 'state': 'queued'}
    monkeypatch.setattr(study, 'submit', submit)
    result = execution.run_scientific_workflow({'study': value, 'output_directory': str(mounted / 'run')})
    assert submitted == [before] and value == before
    assert result['output_directory'] == str(mounted / 'run') and result['operations'] == []
    assert 'private-receipt' not in json.dumps(result)


def test_existing_workflow_replay_exposes_only_its_native_identity(mounted, monkeypatch):
    value = plan(mounted, ['md.xtc'])
    output = mounted / 'run'; output.mkdir()
    (output / 'study-binding.json').write_text('{}')
    monkeypatch.setattr(study, 'submit', lambda p, out: {'id': 'private-receipt',
        'output_directory': str(out), 'steps': {'simulate': {'operation_id': 'op-original-job', 'state': 'running'}}})
    result = execution.run_scientific_workflow({'study': value, 'output_directory': str(output)})
    assert result['operation_id'] == 'op-original-job'
    assert result['output_directory'] == str(output)
    assert 'private-receipt' not in json.dumps(result)
