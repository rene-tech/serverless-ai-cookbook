"""Failed scientific work retains its explanation without being relabeled passed."""
import asyncio
import json

import pytest

from test_scientific_batch_client import client


@pytest.mark.parametrize('fetch_fails', [False, True])
def test_failed_run_keeps_result_or_diagnostics_failure_without_resubmission(tmp_path, monkeypatch, fetch_fails):
    requests = []
    async def rpc(connection, tool, arguments):
        requests.append((tool, arguments))
        if fetch_fails:
            raise ConnectionError('transient read failure')
        return {'terminal_status': 'failed', 'semantic_validation': {'status': 'failed'},
                'failure_code': 'native-stage-error'}
    monkeypatch.setattr(client, 'call', rpc)
    receipt = {'operation_id': 'original-operation', 'state': 'running'}
    status = {'operation': {'id': 'original-operation', 'status': 'failed', 'error_code': 'Error'},
              'batch': {'result_published': True}}
    asyncio.run(client.retain_terminal_diagnostics(None, status, tmp_path, receipt))
    saved = json.loads((tmp_path / 'receipt.json').read_text())
    assert saved['state'] == 'failed'
    assert requests == [('get_scientific_result', {'operation_id': 'original-operation'})]
    assert 'verified_artifacts' not in saved
    if fetch_fails:
        assert saved['diagnostics_read_error_type'] == 'ConnectionError'
    else:
        assert json.loads((tmp_path / saved['failure_result']).read_text())['terminal_status'] == 'failed'


def test_no_published_result_is_not_invented(tmp_path, monkeypatch):
    async def rpc(*args):
        raise AssertionError('No result was published')
    monkeypatch.setattr(client, 'call', rpc)
    receipt = {'operation_id': 'original-operation'}
    asyncio.run(client.retain_terminal_diagnostics(None, {'operation': {'status': 'cancelled'}}, tmp_path, receipt))
    assert receipt['state'] == 'cancelled' and 'failure_result' not in receipt


@pytest.mark.parametrize('semantic_type,accepted', [
    ('lammps-failed-log/v1', True), ('amber-failed-result/v1', True),
    ('native-failed-diagnostics/v1', True), ('lammps-file/v1', False),
])
def test_failed_manifest_downloads_only_diagnostics_without_success_claim(
        tmp_path, monkeypatch, semantic_type, accepted):
    downloads = []
    async def rpc(connection, tool, arguments):
        assert tool == 'get_scientific_result'
        return {'operation_id': 'original-operation', 'terminal_status': 'failed',
                'semantic_validation': {'status': 'failed'},
                'output_manifest': {'artifact_id': 'manifest'}}
    async def download(http, reference, target):
        downloads.append((reference['artifact_id'], target))
        target.parent.mkdir(parents=True, exist_ok=True)
        if reference['artifact_id'] == 'manifest':
            target.write_text(json.dumps({
                'schema': 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1',
                'entries': [{'name': '../untrusted-native-name', 'semantic_type': semantic_type,
                             'artifact': {'artifact_id': 'log'}}]}))
        else:
            target.write_text('ERROR: exact native diagnostic')
        return {'artifact_id': reference['artifact_id'], 'path': str(target)}
    monkeypatch.setattr(client, 'call', rpc)
    monkeypatch.setattr(client, 'download', download)
    receipt = {'operation_id': 'original-operation'}
    status = {'operation': {'status': 'failed'}, 'batch': {'result_published': True}}
    asyncio.run(client.retain_terminal_diagnostics(None, status, tmp_path, receipt, http=object()))
    saved = json.loads((tmp_path / 'receipt.json').read_text())
    assert saved['state'] == 'failed' and 'verified_artifacts' not in saved
    if accepted:
        assert len(saved['diagnostic_artifacts']) == 1
        assert downloads[1][1] == tmp_path / 'failed-attempt' / 'output-00.artifact'
    else:
        assert len(downloads) == 1
        assert saved['diagnostics_read_error_type'] == 'RuntimeError'
        assert 'diagnostic_artifacts' not in saved


def test_conflicting_operation_cannot_supply_failure_artifacts(tmp_path, monkeypatch):
    async def rpc(*args):
        return {'operation_id': 'another-operation', 'terminal_status': 'failed',
                'output_manifest': {'artifact_id': 'wrong-manifest'}}
    async def collect(*args, **kwargs):
        raise AssertionError('Conflicting operation must not download a manifest')
    monkeypatch.setattr(client, 'call', rpc)
    monkeypatch.setattr(client, 'collect_manifest', collect)
    receipt = {'operation_id': 'original-operation'}
    status = {'operation': {'status': 'failed'}, 'batch': {'result_published': True}}
    asyncio.run(client.retain_terminal_diagnostics(None, status, tmp_path, receipt, http=object()))
    assert receipt['state'] == 'failed'
    assert receipt['diagnostics_read_error_type'] == 'RuntimeError'
