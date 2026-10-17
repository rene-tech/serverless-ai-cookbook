"""Exercise actual shell jobs and reconnects over the stdio protocol."""
import json
import os
from pathlib import Path
import subprocess
import sys
import importlib.util
import pytest

SCRIPT = Path(__file__).with_name('execution-mcp.py')


def call(tmp_path, name, args):
    env = dict(os.environ, SCIENTIFIC_EXECUTION_DIR=str(tmp_path / 'jobs'),
               SCIENTIFIC_WORKSPACE=str(tmp_path))
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': name, 'arguments': args}}
    proc = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(request) + '\n',
                          env=env, text=True, capture_output=True, check=True, timeout=30)
    result = json.loads(proc.stdout)['result']
    return result, json.loads(result['content'][0]['text'])


def test_actual_python_file_and_failed_exit(tmp_path):
    _, result = call(tmp_path, 'execute_command', {
        'command': "python3 -c \"from pathlib import Path; Path('result.txt').write_text(str(6 * 7))\""})
    assert result['status'] == 'completed'
    assert (tmp_path / 'result.txt').read_text() == '42'
    envelope, result = call(tmp_path, 'execute_command', {'command': 'echo failure; exit 7'})
    assert envelope['isError'] is True
    assert result['exit_code'] == 7
    assert result['output'] == 'failure\n'


def test_job_continues_after_mcp_disconnect_and_output_is_paged(tmp_path):
    _, started = call(tmp_path, 'execute_command', {
        'command': "sleep 0.3; python3 -c \"print('x' * 40000, end='')\"", 'wait_seconds': 0})
    _, result = call(tmp_path, 'read_execution', {'job_id': started['job_id'], 'wait_seconds': 3})
    assert result['status'] == 'completed'
    assert len(result['output']) == 4000
    assert result['output_size_bytes'] == 40000
    assert result['returned_bytes'] == 4000
    assert 'retained at output_path' in result['output_guidance']
    assert result['more_output'] is True
    _, rest = call(tmp_path, 'read_execution', {'job_id': started['job_id'],
        'offset': result['next_offset'], 'max_bytes': 32000})
    assert len(rest['output']) == 32000
    assert rest['more_output'] is True
    _, final = call(tmp_path, 'read_execution', {'job_id': started['job_id'],
        'offset': rest['next_offset']})
    assert len(final['output']) == 4000
    assert final['more_output'] is False


def test_command_deadline(tmp_path):
    envelope, result = call(tmp_path, 'execute_command', {
        'command': 'sleep 30', 'timeout_seconds': 1, 'wait_seconds': 3})
    assert envelope['isError'] is True
    assert result['status'] == 'timed_out'


def test_bounded_thirty_second_observation_returns_early_after_reconnect(tmp_path):
    import time
    _, started = call(tmp_path, 'execute_command', {
        'command': 'sleep 0.2; printf completed', 'wait_seconds': 0})
    before = time.monotonic()
    _, result = call(tmp_path, 'read_execution', {'job_id': started['job_id'], 'wait_seconds': 30})
    assert time.monotonic() - before < 5
    assert result['status'] == 'completed' and result['output'] == 'completed'
    assert result['job_id'] == started['job_id']
    assert len(list((tmp_path / 'jobs').glob('*/request.json'))) == 1


def test_observation_deadline_preserves_pending_job_without_new_execution(tmp_path, monkeypatch):
    import uuid
    spec = importlib.util.spec_from_file_location('execution_test', SCRIPT)
    execution = importlib.util.module_from_spec(spec); spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'ROOT', tmp_path)
    job = str(uuid.uuid4()); directory = tmp_path / job; directory.mkdir()
    original = '{"command":"existing workflow","timeout_seconds":0}'
    (directory / 'request.json').write_text(original)
    now = [0.0]
    monkeypatch.setattr(execution.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(execution.time, 'sleep', lambda delay: now.__setitem__(0, now[0] + delay))
    result = execution.read_job({'job_id': job, 'wait_seconds': 30})
    assert now[0] == pytest.approx(25)
    assert result['requested_wait_seconds'] == 30
    assert result['effective_wait_seconds'] == 25
    assert result['transport_margin_seconds'] == 5
    assert result['status'] == 'starting' and result['job_id'] == job
    assert (directory / 'request.json').read_text() == original
    assert not (directory / 'status.json').exists()
    with pytest.raises(ValueError, match='0 to 30'):
        execution.read_job({'job_id': job, 'wait_seconds': 31})
    assert len(list(tmp_path.glob('*/request.json'))) == 1


def test_observation_interrupted_worker_returns_early_without_retry(tmp_path, monkeypatch):
    import uuid
    spec = importlib.util.spec_from_file_location('execution_test', SCRIPT)
    execution = importlib.util.module_from_spec(spec); spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'ROOT', tmp_path)
    job = str(uuid.uuid4()); directory = tmp_path / job; directory.mkdir()
    (directory / 'request.json').write_text('{}')
    (directory / 'status.json').write_text(json.dumps({'job_id': job, 'status': 'running',
        'worker_pid': 999999999, 'worker_start': 'nonexistent'}))
    monkeypatch.setattr(execution.time, 'sleep', lambda _: pytest.fail('No wait after interrupted receipt'))
    result = execution.read_job({'job_id': job, 'wait_seconds': 30})
    assert result['status'] == 'interrupted' and result['job_id'] == job
    assert len(list(tmp_path.glob('*/request.json'))) == 1


def test_actual_pending_observation_fits_existing_mcp_deadline_and_reconnects(tmp_path):
    import time
    # A real stdio command must return before the exact configured client call
    # timeout, not merely pass a mocked clock test. The original job continues.
    configuration = SCRIPT.with_name('render-config.mjs').read_text()
    section = configuration.split("'environment-execution': {", 1)[1].split("'structure-viewer':", 1)[0]
    assert 'timeout: 30000' in section
    _, started = call(tmp_path, 'execute_command', {'command': 'sleep 26; printf finished', 'wait_seconds': 0})
    before = time.monotonic()
    _, pending = call(tmp_path, 'read_execution', {'job_id': started['job_id'], 'wait_seconds': 30})
    elapsed = time.monotonic() - before
    assert 24.8 <= elapsed < 29
    assert pending['status'] == 'running'
    assert pending['effective_wait_seconds'] + pending['transport_margin_seconds'] == 30
    _, completed = call(tmp_path, 'read_execution', {'job_id': started['job_id'], 'wait_seconds': 3})
    assert completed['status'] == 'completed' and completed['output'] == 'finished'
    assert completed['job_id'] == started['job_id']
    assert len(list((tmp_path / 'jobs').glob('*/request.json'))) == 1


def test_retired_workflow_file_rejected_without_process_or_admission(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('execution_test', SCRIPT)
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    (tmp_path / 'a plan.json').write_text('{"schema":"scientific-workflow/v1","steps":[]}')
    with pytest.raises(ValueError, match='scientific-workflow/v2'):
        execution.run_scientific_workflow({
            'plan_file': 'a plan.json', 'output_directory': 'study results'})
    assert not list((tmp_path / 'jobs').glob('*/request.json'))


@pytest.mark.parametrize('arguments', [
    {'steps': [], 'output_directory': 'study'},
    {'plan_file': 'plan.json', 'output_directory': 'study', 'resume': False},
])
def test_old_launcher_arguments_rejected_before_process(tmp_path, monkeypatch, arguments):
    spec = importlib.util.spec_from_file_location('execution_test', SCRIPT)
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'jobs')
    with pytest.raises(ValueError, match='Supply only'):
        execution.run_scientific_workflow(arguments)
    assert not list((tmp_path / 'jobs').glob('*/request.json'))


def test_launcher_advertises_only_current_whole_study_contract():
    spec = importlib.util.spec_from_file_location('execution_test', SCRIPT)
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    schema = next(t['inputSchema'] for t in execution.TOOLS if t['name']=='run_scientific_workflow')
    assert set(schema['properties']) == {'study', 'plan_file', 'output_directory'}
    assert schema['properties']['study']['oneOf'][0]['properties']['schema'] == {'const': 'scientific-workflow/v2'}
