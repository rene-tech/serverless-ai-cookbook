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
