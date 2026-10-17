"""Run in the workbench image; mock hosted calls, retain real receipt/file code."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

if not Path('/app/skill/md-precheck/scripts/run-precheck.py').exists():
    raise unittest.SkipTest('Run this installed-dependency test in the pinned workbench image.')

spec = importlib.util.spec_from_file_location('runner', '/app/skill/md-precheck/scripts/run-precheck.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Response:
    def __init__(self, value):
        self.value = value

    def model_dump(self, **kwargs):
        return {'structuredContent': self.value, 'isError': False}


class Fixture:
    def __init__(self, root):
        self.calls, self.submissions = [], []
        self.found, self.wrong, self.corrupt = False, False, False
        self.reject, self.status = False, 'SUCCEEDED'
        source = root / 'input.tar.gz'
        source.write_bytes(b'public fixture')
        self.args = SimpleNamespace(file=source, output_dir=root / 'reports', input_format='tar.gz',
            idempotency_key='mdprecheck-unit-0001', probes=[], intent=['stage=production'], nsteps=5000,
            threads=2, define=[], **dict.fromkeys(('coords', 'top', 'mdp', 'ndx', 'tpr',
                                                                  'fasta', 'workflow', 'chain_names')))
        self.args.output_dir.mkdir()
        self.data = {'html': b'<!DOCTYPE html><title>Report</title>', 'json': b'{"status":"warn"}'}
        self.pointers = {kind: {'artifact_id': kind, 'sha256': hashlib.sha256(raw).hexdigest(),
            'size_bytes': len(raw), 'media_type': 'text/html' if kind == 'html' else 'application/json',
            'compression': 'none'} for kind, raw in self.data.items()}

    async def upload(self, *args):
        return {'artifact': {'artifact_id': 'input-fixture', **runner.upload.file_identity(self.args.file),
                             'media_type': 'application/gzip', 'compression': 'none'}}

    async def call_tool(self, name, value):
        self.calls.append(name)
        if name == 'get_model_schema':
            result = {'contracts': [{'input_schema': {'type': 'object'}}]}
        elif name == 'lookup_mdprecheck':
            result = {'found': self.found, 'workload_fingerprint': 'exact-options',
                      **self.envelope('sync-existing')}
        elif name == 'run_mdprecheck':
            self.submissions.append(value)
            if self.reject:
                result = {'error': {'code': 'NOT_AUTHORIZED', 'retryable': False}}
            else:
                result = self.envelope('sync-new')
        elif name == 'get_scientific_artifact':
            result = self.pointers[value['artifact_id']]
        elif name == 'download_scientific_artifact':
            result = {'handle': {'method': 'GET', 'url': 'https://objects.invalid/'+value['artifact_id'], 'headers': {}}}
        else:
            raise AssertionError(name)
        return Response(result)

    def envelope(self, oid):
        return {'operation': {'id': oid, 'status': self.status}, 'result': {
            'status': 'warn', 'findings': [],
            'workload_fingerprint': 'different-options' if self.wrong else 'exact-options',
            'artifacts': self.pointers}}

    def stream(self, method, url, headers):
        assert method == 'GET' and 'Authorization' not in headers
        data = b'corrupt' if self.corrupt else self.data[url.rsplit('/', 1)[1]]
        class Stream:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            def raise_for_status(self): pass
            async def aiter_bytes(self): yield data
        return Stream()

    async def run(self):
        with patch.object(runner.upload, 'transfer', self.upload), patch.object(runner.asyncio, 'sleep', AsyncMock()):
            return await runner.execute(self.args, self, self, 'https://platform.invalid/mcp', 'synthetic-key')


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/workspace')
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(Path(self.temp.name))

    async def test_direct_result_then_redownload_without_new_submission(self):
        f = self.fixture
        result = await f.run()
        self.assertEqual(len(f.submissions), 1)
        self.assertNotIn('wait_seconds', f.submissions[0])
        self.assertNotIn('idempotency_key', f.submissions[0])
        self.assertNotIn('get_operation', f.calls)
        self.assertNotIn('get_operation_result', f.calls)
        self.assertEqual(result['status'], 'warn')
        self.assertEqual(len(result['files']), 2)
        await f.run()
        self.assertEqual(len(f.submissions), 1)
        self.assertNotIn('synthetic-key', (f.args.output_dir / 'receipt.json').read_text())

    async def test_exact_lookup_reuses_without_inference(self):
        f = self.fixture
        f.found = True
        result = await f.run()
        self.assertTrue(result['reused'])
        self.assertEqual(result['operation_id'], 'sync-existing')
        self.assertEqual(f.submissions, [])

    async def test_explicit_rerun_submits_fresh_check_then_resumes_same_operation(self):
        f = self.fixture
        f.found, f.args.rerun = True, True
        result = await f.run()
        self.assertFalse(result['reused'])
        self.assertEqual(result['operation_id'], 'sync-new')
        self.assertEqual(len(f.submissions), 1)
        resumed = await f.run()
        self.assertEqual(resumed['operation_id'], 'sync-new')
        self.assertEqual(len(f.submissions), 1)

    async def test_rerun_requires_new_receipt_identity(self):
        f = self.fixture
        f.found = True
        await f.run()
        f.args.rerun = True
        with self.assertRaisesRegex(ValueError, 'changed'):
            await f.run()
        self.assertEqual(f.submissions, [])

    async def test_different_options_report_is_never_delivered(self):
        self.fixture.wrong = True
        with self.assertRaisesRegex(ValueError, 'exact requested inputs/options'):
            await self.fixture.run()
        self.assertFalse((self.fixture.args.output_dir / 'delivery.json').exists())

    async def test_changed_options_cannot_replay_receipt(self):
        await self.fixture.run()
        self.fixture.args.intent = ['stage=equilibration']
        with self.assertRaisesRegex(ValueError, 'changed'):
            await self.fixture.run()

    async def test_non_retryable_rejection_is_not_looped(self):
        self.fixture.reject = True
        with self.assertRaisesRegex(ValueError, 'submission failed'):
            await self.fixture.run()
        self.assertEqual(len(self.fixture.submissions), 1)

    async def test_corrupt_download_is_not_published(self):
        self.fixture.corrupt = True
        with self.assertRaisesRegex(ValueError, 'checksum'):
            await self.fixture.run()
        self.assertFalse((self.fixture.args.output_dir / 'report.html').exists())

    async def test_lost_response_is_not_automatically_resubmitted(self):
        f = self.fixture
        f.reject = True
        with self.assertRaises(ValueError):
            await f.run()
        f.reject = False
        with self.assertRaisesRegex(ValueError, 'response was lost'):
            await f.run()
        self.assertEqual(len(f.submissions), 1)


if __name__ == '__main__':
    unittest.main()
