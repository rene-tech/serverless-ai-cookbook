"""Recovery discovery is executable without network, credentials or MD."""
from contextlib import nullcontext
import importlib.util
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
HELPER = ROOT / 'scripts/scientific-batch-acceptance.py'
SKILL = ROOT.parents[1] / 'skills/scientific-ai/gromacs/SKILL.md'


def test_default_help_exposes_complete_read_only_recovery_mode():
    result = subprocess.run([sys.executable, str(HELPER), '--help'],
                            capture_output=True, text=True, check=True)
    assert '--recover-operation-id OPERATION_ID --output /workspace/md/recovered' in result.stdout
    assert 'No model, source, parameters or idempotency key is needed for recovery.' in result.stdout
    assert 'does not upload inputs, submit, resubmit or cancel work' in result.stdout


def test_recovery_help_does_not_require_submission_arguments():
    result = subprocess.run([sys.executable, str(HELPER), '--recover-operation-id',
                             '00000000-0000-4000-8000-000000000001', '--help'],
                            capture_output=True, text=True, check=True)
    usage = result.stdout.split('\n\n', 1)[0]
    assert '--recover-operation-id' in usage and '--output' in usage
    assert '--model' not in usage and '--source' not in usage
    assert 'without new admission' in result.stdout


def test_complete_installed_skill_example_selects_only_recovery(monkeypatch, tmp_path):
    blocks = re.findall(r'```sh\n(.*?)\n```', SKILL.read_text(), re.S)
    recovery = [block for block in blocks if '--recover-operation-id' in block]
    assert len(recovery) == 1
    arguments = shlex.split(recovery[0].replace('\\\n', ''))
    assert arguments[:2] == ['/opt/scientific-client/bin/python',
                             '/opt/bionemo/invoke-scientific-batch.py']
    operation = '00000000-0000-4000-8000-000000000001'
    arguments[arguments.index('OPERATION_ID')] = operation
    arguments[arguments.index('/workspace/md/recovered')] = str(tmp_path / 'recovered')
    spec = importlib.util.spec_from_file_location('batch_help_test', HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    calls = []

    async def recover(args):
        calls.append(vars(args))

    async def forbidden_submit(args):
        raise AssertionError('Recovery example must not select submission.')

    monkeypatch.setattr(sys, 'argv', arguments[1:])
    monkeypatch.setattr(helper, 'recover_completed', recover)
    monkeypatch.setattr(helper, 'run', forbidden_submit)
    monkeypatch.setattr(helper, 'receipt_lock', lambda _: nullcontext())
    helper.main()
    assert calls == [{'recover_operation_id': operation, 'output': tmp_path / 'recovered'}]
    assert not (tmp_path / 'recovered').exists()
