"""Real stdio concurrency: pending observations cannot starve another chat."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


def test_eight_observations_do_not_block_ping_or_an_independent_command(tmp_path):
    root = tmp_path / 'jobs'
    requests = []
    for index in range(8):
        job = str(uuid.uuid4())
        directory = root / job
        directory.mkdir(parents=True)
        (directory / 'request.json').write_text('{}')
        (directory / 'status.json').write_text(json.dumps({'job_id': job, 'status': 'running',
            'worker_pid': os.getpid(), 'worker_start': Path('/proc/self/stat').read_text().split()[21]}))
        requests.append({'jsonrpc': '2.0', 'id': index, 'method': 'tools/call', 'params': {
            'name': 'read_execution', 'arguments': {'job_id': job, 'wait_seconds': 3}}})
    requests += [{'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                 {'jsonrpc': '2.0', 'id': 100, 'method': 'ping'},
                 {'jsonrpc': '2.0', 'id': 101, 'method': 'tools/call', 'params': {
                     'name': 'execute_command', 'arguments': {'command': 'printf independent-result'}}}]
    env = {**os.environ, 'SCIENTIFIC_EXECUTION_DIR': str(root), 'SCIENTIFIC_WORKSPACE': str(tmp_path)}
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('execution-mcp.py'))],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    started = time.monotonic()
    try:
        process.stdin.write(''.join(json.dumps(r) + '\n' for r in requests))
        process.stdin.close()
        first = [json.loads(process.stdout.readline()), json.loads(process.stdout.readline())]
        assert {v['id'] for v in first} == {100, 101}
        assert time.monotonic() - started < 2, 'An independent request queued behind a long observation'
        command = next(v['result'] for v in first if v['id'] == 101)
        assert json.loads(command['content'][0]['text'])['output'] == 'independent-result'
        remaining = [json.loads(line) for line in process.stdout]
        process.wait(timeout=10)
        assert process.returncode == 0
        assert {v['id'] for v in remaining} == set(range(8))
        assert len(list(root.glob('*/request.json'))) == 9  # no observation starts a job
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
