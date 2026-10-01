import hashlib
import importlib.util
import json
from pathlib import Path
import shlex

import pytest
from scientific_starter import resolve


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / 'examples' / 'v9'
    case = root / 'molecular-dynamics' / 'example'
    case.mkdir(parents=True)
    recipes, objects = [], []
    def put(name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        path.write_bytes(data)
        objects.append({'path': name, 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    for model in ('gromacs', 'namd', 'amber', 'lammps'):
        directory = 'molecular-dynamics/example/' + model
        params = {'jobs': [{'id': 'original', 'steps': [{'id': 'run', 'command': 'native'}]}]}
        put(directory + '/parameters.json', params)
        put(directory + '/input.tar.gz', b'exact native fixture bytes')
        put(directory + '/input-manifest.template.json', {'entries': [{
            'name': model + '-inputs', 'semantic_type': model + '-input-bundle/v1', 'artifact': {
                '$file': directory + '/input.tar.gz', 'compression': 'gzip', 'media_type': 'application/x-tar'}}]})
        recipes.append({'model_id': model, 'tool_name': 'submit_' + model + '_workflow', 'arguments': {
            'operation': 'run-workflow', 'parameters': params,
            'input_manifest': {'$manifest': directory + '/input-manifest.template.json'}}})
    put('molecular-dynamics/example/recipes.json', {'recipes': recipes,
        'expected': {'description': 'Reference example; not converged sampling.'}})
    (root / 'manifest.json').write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/customer-starter-pack/v1',
                                                   'version': 'v9', 'objects': objects}))
    return tmp_path, case


@pytest.mark.parametrize('model', ['gromacs', 'namd', 'amber', 'lammps'])
def test_preserves_selected_engine_bytes_and_stable_identity(pack, model):
    workspace, case = pack
    before = (case / model / 'parameters.json').read_bytes()
    plan = resolve(str(case), model, 'studies/new', workspace, '/python', '/existing-client.py')
    assert plan == resolve(str(case), model, 'studies/new', workspace, '/python', '/existing-client.py')
    command = shlex.split(plan['command'])
    assert command[command.index('--model') + 1] == model
    assert Path(command[command.index('--parameters') + 1]).read_bytes() == before
    assert len(plan['provenance']['files']) == 4
    assert plan['provenance']['pack_version'] == 'v9'
    assert plan['identity'] != resolve(str(case), model, 'studies/other', workspace, '/python', '/existing-client.py')['identity']


def test_changed_input_and_unsupported_model_never_admitted(pack):
    workspace, case = pack
    (case / 'gromacs/input.tar.gz').write_bytes(b'changed')
    with pytest.raises(ValueError, match='differs from its manifest'):
        resolve(str(case), 'gromacs', 'studies/run', workspace, '/python', '/client')
    with pytest.raises(ValueError, match='supported engines'):
        resolve(str(case), 'not-gromacs', 'studies/run', workspace, '/python', '/client')
    with pytest.raises(ValueError, match='inside the mounted'):
        resolve(str(case), 'gromacs', '/elsewhere', workspace, '/python', '/client')
    with pytest.raises(ValueError, match='Preserve the starter pack'):
        resolve(str(case), 'gromacs', str(case / 'results'), workspace, '/python', '/client')


def test_index_is_recorded_before_launch_and_replays_never_start_a_second_job(pack, monkeypatch):
    workspace, case = pack
    spec = importlib.util.spec_from_file_location('starter_execution', Path(__file__).with_name('execution-mcp.py'))
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'ROOT', workspace / 'jobs')
    monkeypatch.setattr(execution, 'WORKSPACE', str(workspace))
    launches = []
    def start(args, on_admit):
        on_admit('retained-job')
        assert next((execution.ROOT / 'starter-index').glob('*.json')).is_file()
        launches.append(args)
        return {'job_id': 'retained-job', 'status': 'running'}
    monkeypatch.setattr(execution, 'execute', start)
    monkeypatch.setattr(execution, 'read_job', lambda args: {'job_id': args['job_id'], 'status': 'completed'})
    args = {'case_directory': str(case), 'model': 'gromacs', 'output_directory': 'studies/new'}
    first = execution.run_starter_example(args)
    second = execution.run_starter_example(args)
    assert first['job_id'] == second['job_id'] and second['reused_existing_job']
    assert len(launches) == 1
    with pytest.raises(ValueError, match='another request'):
        execution.run_starter_example({**args, 'model': 'namd'})
