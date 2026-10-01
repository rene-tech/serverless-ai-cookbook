import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def execution(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('typed_openff_execution', Path(__file__).with_name('execution-mcp.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path / 'jobs')
    monkeypatch.setattr(module, 'WORKSPACE', str(tmp_path))
    return module


def arguments():
    return {'smiles': 'C[NH3+]', 'force_field': 'openff-2.2.1.offxml', 'output_directory': 'ligand'}


def test_identity_bound_before_launch_and_repeated_call_never_recomputes(execution, monkeypatch):
    inspect = Mock(return_value=SimpleNamespace(returncode=0, stdout='{"status":"identity_defined"}'))
    monkeypatch.setattr(execution.subprocess, 'run', inspect)
    launches = []

    def start(args, on_admit):
        on_admit('existing-job')
        assert next((execution.ROOT / 'openff-index').glob('*.json')).is_file()
        launches.append(args)
        return {'job_id': 'existing-job', 'status': 'running'}
    monkeypatch.setattr(execution, 'execute', start)
    monkeypatch.setattr(execution, 'read_job', lambda args: {'job_id': args['job_id'], 'status': 'completed'})
    first = execution.prepare_openff_ligand(arguments())
    second = execution.prepare_openff_ligand(arguments())
    assert first['job_id'] == second['job_id'] and second['reused_existing_job']
    assert len(launches) == 1 and inspect.call_count == 1
    with pytest.raises(ValueError, match='another preparation'):
        execution.prepare_openff_ligand({**arguments(), 'smiles': 'CCO'})


def test_undefined_stereo_is_a_question_not_a_job(execution, monkeypatch):
    monkeypatch.setattr(execution.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({'status': 'needs_user_input', 'outputs_created': False})))
    monkeypatch.setattr(execution, 'execute', lambda *a, **k: pytest.fail('No preparation authorized'))
    result = execution.prepare_openff_ligand({**arguments(), 'smiles': 'CC(O)CC'})
    assert result['status'] == 'needs_user_input' and not result['outputs_created']
    assert not (Path(execution.WORKSPACE) / 'ligand').exists()


def test_existing_results_and_different_method_preserved(execution):
    output = Path(execution.WORKSPACE) / 'ligand'
    output.mkdir()
    (output / 'customer.txt').write_text('preserve')
    with pytest.raises(ValueError, match='already contains'):
        execution.prepare_openff_ligand(arguments())
    assert (output / 'customer.txt').read_text() == 'preserve'
    with pytest.raises(ValueError, match='no method substitution'):
        execution.prepare_openff_ligand({**arguments(), 'force_field': 'different.offxml'})


def test_interrupted_preparation_not_implicitly_resubmitted(execution, monkeypatch):
    monkeypatch.setattr(execution.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        returncode=0, stdout='{"status":"identity_defined"}'))
    def interrupted(args, on_admit):
        on_admit('saved-job')
        raise OSError('process interrupted after identity persisted')
    monkeypatch.setattr(execution, 'execute', interrupted)
    with pytest.raises(OSError):
        execution.prepare_openff_ligand(arguments())
    monkeypatch.setattr(execution, 'read_job', lambda args: {'job_id': args['job_id'], 'status': 'interrupted'})
    monkeypatch.setattr(execution, 'execute', lambda *a, **k: pytest.fail('Must not relaunch'))
    assert execution.prepare_openff_ligand(arguments())['status'] == 'interrupted'
