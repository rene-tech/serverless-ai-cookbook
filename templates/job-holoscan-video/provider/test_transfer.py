"""CPU checks of once-only execution and scoped object transfer; no provider calls."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('transfer', Path(__file__).with_name('transfer.py'))
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


class Response(io.BytesIO):
    status = 200


class TransferTest(unittest.TestCase):
    def exercise(self, *, timeout=False, wrong_digest=False, job_mode=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = b'owned bundle bytes'
            counter = root / 'executions'
            code = ('import os,time;from pathlib import Path;'
                    f'Path({str(counter)!r}).write_text("executed");'
                    'Path(os.environ["HOLOSCAN_PROVIDER_OUTPUT"],"science.txt").write_text("completed");')
            if timeout:
                code += 'time.sleep(60)'
            command = json.dumps([sys.executable, '-I', '-c', code]).encode()
            (root / 'command.json').write_bytes(command)
            config = {
                'input': {'url': 'https://example.invalid/input', 'size_bytes': len(incoming),
                          'sha256': '0' * 64 if wrong_digest else hashlib.sha256(incoming).hexdigest()},
                'output': {'url': 'https://example.invalid/output', 'max_bytes': 65536},
                'claim': {'url': 'https://example.invalid/claim', 'headers': {'If-None-Match': '*'}},
                'command_sha256': hashlib.sha256(command).hexdigest(),
                'execution_timeout_s': 1 if timeout else 10,
            }
            if job_mode:
                del config['claim']
            (root / 'config.json').write_text(json.dumps(config))
            state = {'claimed': False, 'uploads': []}

            class Opener:
                def open(self, request, timeout):
                    self_timeout = timeout
                    assert self_timeout > 0
                    assert request.get_method() == 'PUT'
                    assert request.get_header('If-none-match') == '*'
                    if state['claimed']:
                        raise HTTPError(request.full_url, 412, 'already claimed', {}, None)
                    state['claimed'] = True
                    return Response()

            def object_open(request):
                if request.get_method() == 'GET':
                    return Response(incoming)
                self.assertEqual(request.get_method(), 'PUT')
                state['uploads'].append(request.data.read())
                return Response()

            with patch.object(transfer, 'build_opener', return_value=Opener()), patch.object(transfer, 'open_object', side_effect=object_open):
                if wrong_digest:
                    with self.assertRaisesRegex(transfer.TransferError, 'integrity'):
                        transfer.execute(root / 'config.json', root / 'command.json', endpoint_idle=not job_mode)
                    self.assertFalse(counter.exists())
                    self.assertFalse(state['uploads'])
                    return
                result = transfer.execute(root / 'config.json', root / 'command.json', endpoint_idle=not job_mode)
                self.assertEqual(result, 124 if timeout else 0)
                self.assertTrue(counter.exists())
                if not job_mode:
                    counter.unlink()
                    self.assertEqual(transfer.execute(root / 'config.json', root / 'command.json', endpoint_idle=True), 0)
                    self.assertFalse(counter.exists(), 'A repeated Endpoint start must never execute science')
                self.assertEqual(len(state['uploads']), 1)
                with tarfile.open(fileobj=io.BytesIO(state['uploads'][0])) as archive:
                    proof = json.load(archive.extractfile('transfer-result.json'))
                    self.assertEqual(proof['execution_exit_code'], result)
                    self.assertIn('science.txt', archive.getnames())

    def test_finite_job_mode_requires_no_endpoint_marker(self):
        self.exercise(job_mode=True)

    def test_once_only_claim_and_complete_output(self):
        self.exercise()

    def test_timeout_exports_partial_logs_without_replaying(self):
        self.exercise(timeout=True)

    def test_integrity_failure_prevents_execution(self):
        self.exercise(wrong_digest=True)

    def test_signed_redirects_and_credentialed_urls_are_rejected(self):
        for value in ['http://example.invalid/file', 'https://user:pass@example.invalid/file']:
            with self.assertRaises(transfer.TransferError):
                transfer.checked_url(value)
        with self.assertRaises(transfer.TransferError):
            transfer.NoRedirect().redirect_request(None, None, None, None, None, None)


if __name__ == '__main__':
    unittest.main()
