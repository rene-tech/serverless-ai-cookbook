"""Local process witness: restart only an idle worker under its existing owner."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import scientific_study as studies
from scientific_receipts import receipt_lock


def until(read, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = read()
            if predicate(value):
                return value
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    raise AssertionError('Expected local process transition did not occur')


def test_locked_drained_worker_refresh_preserves_api_supervisor_and_queue(tmp_path, monkeypatch):
    for name, value in {'SCIENTIFIC_WORKSPACE': str(tmp_path / 'workspace'),
        'SCIENTIFIC_EXECUTION_DIR': str(tmp_path / 'execution'),
        'SCIENTIFIC_RECEIPT_LOCK_DIR': str(tmp_path / 'locks'),
        'SCIENTIFIC_STUDY_OWNER': 'local-refresh-fixture', 'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance',
        'SCIENTIFIC_MODELS_MCP_URL': 'https://fixture.invalid/mcp',
        'SCIENTIFIC_MODELS_API_KEY': 'synthetic-no-network'}.items():
        monkeypatch.setenv(name, value)
    studies.workspace().mkdir()
    script = str(Path(__file__).with_name('scientific-study-worker.py'))
    supervisor = subprocess.Popen([sys.executable, script, '--', sys.executable,
        '-c', 'import time; time.sleep(60)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    health_path = Path(os.environ['SCIENTIFIC_EXECUTION_DIR']) / 'study-worker.json'
    read_health = lambda: json.loads(health_path.read_text())
    try:
        original = until(read_health, lambda value: value.get('pid') and value.get('current_study') is None)
        worker = original['pid']
        children = Path(f'/proc/{supervisor.pid}/task/{supervisor.pid}/children').read_text().split()
        api = next(int(value) for value in children if int(value) != worker)
        api_start = Path(f'/proc/{api}/stat').read_text().rsplit(')', 1)[1].split()[19]
        assert studies.list_studies() == []
        # The real worker holds this same nonblocking local lock across a phase.
        # A busy phase cannot be interrupted by this maintenance procedure.
        with receipt_lock(studies.registry() / 'queue-worker'):
            assert studies.list_studies() == []
            assert b'--worker' in Path(f'/proc/{worker}/cmdline').read_bytes().split(b'\0')
            assert int(Path(f'/proc/{worker}/stat').read_text().rsplit(')', 1)[1].split()[1]) == supervisor.pid
            os.kill(worker, signal.SIGTERM)
            children_after = until(lambda: Path(f'/proc/{supervisor.pid}/task/{supervisor.pid}/children').read_text().split(),
                lambda values: str(worker) not in values and len(values) == 2)
            replacement = next(int(value) for value in children_after if int(value) != api)
            assert replacement != worker and supervisor.poll() is None
            assert Path(f'/proc/{api}/stat').read_text().rsplit(')', 1)[1].split()[19] == api_start
        updated = until(read_health, lambda value: value.get('pid') == replacement)
        assert updated['current_study'] is None and updated['blocked_by_study'] is None
        assert studies.list_studies() == []
    finally:
        supervisor.terminate()
        supervisor.wait(timeout=10)
