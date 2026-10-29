import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from scientific_verified_results import deliver


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}


def publication(folder):
    entries = []
    for name, data in [('result.json', b'{"task_complete":false,"samples":0}'),
                       ('artifacts/mask | [test].bin', bytes(range(256))), ('empty.txt', b'')]:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries.append({'path': name, 'size_bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'schema': 'scientific-ai/customer-publication/v1',
                'operation_id': 'op-publication-fixture', 'files': entries}
    save(folder / 'manifest.json', manifest)
    return manifest


def failed_run(folder):
    operation = 'op-failed-fixture'
    receipt = {'operation_id': operation, 'state': 'failed', 'identity': {'model_id': 'isaac-healthcare'}}
    status = {'operation_id': operation, 'model_id': 'isaac-healthcare', 'status': 'FAILED',
              'operation': {'operation_id': operation, 'status': 'failed', 'result_available': False},
              'error': {'code': 'EXECUTION_FAILED', 'stage_id': 'simulate',
                        'message': 'Recording samples exceed the requested scene cap or are empty'}}
    save(folder / 'receipt.json', receipt)
    save(folder / 'status.json', status)
    return receipt, status


def test_failure_delivery_reports_saved_facts_without_diagnosing_ambiguous_errors(tmp_path):
    folder = tmp_path / 'run'
    _, status = failed_run(folder)
    before = (folder / 'status.json').read_bytes()
    result = deliver({'results': [{'kind': 'failure', 'path': 'run'}]}, tmp_path)
    text = result['report_markdown']
    assert result['inference_submitted'] is False
    for value in ('op-failed-fixture', 'isaac-healthcare', 'failed', 'simulate', 'EXECUTION_FAILED',
                  status['error']['message'], 'Root cause: not established', 'not retained, not zero',
                  '/demos?tab=workspace&path=run&file=run%2Fstatus.json'):
        assert value in text
    assert 'zero valid samples' not in text and 'configuration failure' not in text
    assert (folder / 'status.json').read_bytes() == before


def test_missing_failure_details_are_not_invented_and_message_is_literal(tmp_path):
    folder = tmp_path / 'run'
    _, status = failed_run(folder)
    status.pop('error')
    save(folder / 'status.json', status)
    text = deliver({'results': [{'kind': 'failure', 'path': 'run'}]}, tmp_path)['report_markdown']
    assert '| Failed stage | not retained |' in text
    assert '| Error code | not retained |' in text
    assert '\nnot retained\n' in text
    status['error'] = {'message': 'Actual message with ``` and [markup](https://fixture.invalid)\nsecond line'}
    save(folder / 'status.json', status)
    text = deliver({'results': [{'kind': 'failure', 'path': 'run'}]}, tmp_path)['report_markdown']
    assert '````text\n' + status['error']['message'] + '\n````' in text


@pytest.mark.parametrize('change', ['receipt-id', 'status-id', 'nested-id', 'model', 'pending',
                                  'success', 'conflicting-state', 'message-type'])
def test_failure_delivery_rejects_unrelated_or_nonfailed_evidence(tmp_path, change):
    folder = tmp_path / 'run'
    receipt, status = failed_run(folder)
    if change == 'receipt-id':
        receipt['operation_id'] = 'not-a-native-operation'
    elif change == 'status-id':
        status['operation_id'] = 'op-other'
    elif change == 'nested-id':
        status['operation']['operation_id'] = 'op-other'
    elif change == 'model':
        status['model_id'] = 'different-model'
    elif change in ('pending', 'success'):
        receipt['state'] = status['operation']['status'] = 'running' if change == 'pending' else 'succeeded'
        status['status'] = receipt['state'].upper()
    elif change == 'conflicting-state':
        status['operation']['status'] = 'succeeded'
    else:
        status['error']['message'] = {'model_authored_diagnosis': 'zero samples'}
    save(folder / 'receipt.json', receipt)
    save(folder / 'status.json', status)
    with pytest.raises(ValueError):
        deliver({'results': [{'kind': 'failure', 'path': 'run'}]}, tmp_path)


def test_typed_failure_delivery_uses_retained_files_only(tmp_path, monkeypatch):
    from jsonschema import Draft202012Validator

    failed_run(tmp_path / 'run')
    spec = importlib.util.spec_from_file_location('failure_execution', Path(__file__).with_name('execution-mcp.py'))
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    args = {'results': [{'kind': 'failure', 'path': 'run'}]}
    tool = next(tool for tool in execution.TOOLS if tool['name'] == 'deliver_scientific_results')
    Draft202012Validator(tool['inputSchema']).validate(args)
    assert execution.deliver_scientific_results(args) == deliver(args, tmp_path)


def test_failure_delivery_accepts_bound_recovery_without_echoing_private_fields(tmp_path):
    folder = tmp_path / 'run'
    receipt, status = failed_run(folder)
    receipt['identity'] = {'operation_id': receipt['operation_id'], 'caller_fingerprint': 'PRIVATE-CALLER'}
    status['debug'] = {'credential': 'PRIVATE-DEBUG'}
    save(folder / 'recovery-receipt.json', receipt)
    (folder / 'receipt.json').unlink()
    save(folder / 'status.json', status)
    text = deliver({'results': [{'kind': 'failure', 'path': 'run'}]}, tmp_path)['report_markdown']
    assert 'isaac-healthcare' in text and 'run%2Frecovery-receipt.json' in text
    assert 'PRIVATE' not in text


def test_publication_delivery_preserves_full_hashes_and_workspace_links(tmp_path):
    manifest = publication(tmp_path / 'run')
    result = deliver({'results': [{'kind': 'publication', 'path': 'run'}]}, tmp_path)
    text = result['report_markdown']
    assert result['inference_submitted'] is False
    assert '`op-publication-fixture`' in text
    for entry in manifest['files']:
        assert f"`{entry['sha256']}`" in text
    assert '/demos?tab=workspace&path=run%2Fartifacts&file=run%2Fartifacts%2Fmask+%7C+%5Btest%5D.bin' in text
    assert r'mask \| \[test\].bin' in text
    assert 'not the scientific validity' in text
    assert '…' not in text


def test_typed_publication_delivery_uses_the_verified_renderer(tmp_path, monkeypatch):
    from jsonschema import Draft202012Validator

    publication(tmp_path / 'run')
    spec = importlib.util.spec_from_file_location('publication_execution', Path(__file__).with_name('execution-mcp.py'))
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    args = {'results': [{'kind': 'publication', 'path': 'run'}]}
    tool = next(tool for tool in execution.TOOLS if tool['name'] == 'deliver_scientific_results')
    Draft202012Validator(tool['inputSchema']).validate(args)
    assert execution.deliver_scientific_results(args) == deliver(args, tmp_path)


@pytest.mark.parametrize('change', ['changed', 'missing', 'truncated-hash', 'duplicate',
                                  'traversal', 'absolute', 'invalid-id', 'boolean-size'])
def test_publication_rejects_invalid_or_changed_evidence(tmp_path, change):
    folder = tmp_path / 'run'
    manifest = publication(folder)
    entry = manifest['files'][0]
    if change == 'changed':
        (folder / entry['path']).write_bytes(b'changed')
    elif change == 'missing':
        (folder / entry['path']).unlink()
    elif change == 'truncated-hash':
        entry['sha256'] = entry['sha256'][:8]
    elif change == 'duplicate':
        manifest['files'].append(dict(entry))
    elif change == 'traversal':
        entry['path'] = '../outside.json'
    elif change == 'absolute':
        entry['path'] = str(folder / entry['path'])
    elif change == 'invalid-id':
        manifest['operation_id'] = 'op-x` forged'
    elif change == 'boolean-size':
        entry['size_bytes'] = False
    save(folder / 'manifest.json', manifest)
    before = (folder / 'manifest.json').read_bytes()
    with pytest.raises(ValueError):
        deliver({'results': [{'kind': 'publication', 'path': 'run'}]}, tmp_path)
    assert (folder / 'manifest.json').read_bytes() == before


def ligand(folder):
    data = {'schema': 'scientific-openff-preparation/v1', 'input_smiles': 'C[NH3+]',
            'partial_charges_e': [0.2, 0.8], 'atom_count': 2, 'formal_charge_e': 1, 'charge_sum_e': 1,
            'force_field': 'openff-2.2.1.offxml', 'charge_method': 'AmberTools AM1-BCC',
            'cpu_reference_energy_kj_mol': 123.25, 'charge_seconds': 10.12, 'elapsed_seconds': 12.45,
            'versions': {'fixture': 'test-only'}}
    files = {name: save(folder / name, data if name == 'preparation.json' else {'fixture': name})
             for name in ('preparation.json', 'charges.json', 'ligand.top', 'ligand.gro')}
    save(folder / 'manifest.json', {'schema': 'scientific-openff-files/v1', 'files': files})


def test_openff_exact_measurements_encoded_links_and_limitations(tmp_path):
    folder = tmp_path / 'my results' / 'ligand-1'
    ligand(folder)
    result = deliver({'results': [{'kind': 'openff', 'path': str(folder)}]}, tmp_path)
    assert result['schema'] == 'scientific-verified-delivery/v1'
    report = result['report_markdown']
    assert '| Atoms | 2 |' in report and '| Formal charge (e) | 1 |' in report
    assert '123.25' in report and 'path=my+results%2Fligand-1' in report
    assert 'equivalence have not been validated' in report
    assert result['inference_submitted'] is False


def test_changed_file_missing_file_and_escape_never_deliver(tmp_path):
    ligand(tmp_path / 'ligand')
    (tmp_path / 'ligand/ligand.top').write_text('changed')
    with pytest.raises(ValueError, match='differ'):
        deliver({'results': [{'kind': 'openff', 'path': 'ligand'}]}, tmp_path)
    with pytest.raises(ValueError, match='workspace'):
        deliver({'results': [{'kind': 'openff', 'path': '../other'}]}, tmp_path)
    with pytest.raises(FileNotFoundError):
        deliver({'results': [{'kind': 'native-md', 'path': 'absent'}]}, tmp_path)


def test_charge_totals_cannot_be_invented_even_with_updated_manifest(tmp_path):
    folder = tmp_path / 'ligand'
    ligand(folder)
    data = json.loads((folder / 'preparation.json').read_text())
    data['charge_sum_e'] = 0
    meta = save(folder / 'preparation.json', data)
    manifest = json.loads((folder / 'manifest.json').read_text())
    manifest['files']['preparation.json'] = meta
    save(folder / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='totals disagree'):
        deliver({'results': [{'kind': 'openff', 'path': str(folder)}]}, tmp_path)


def test_smiles_backslashes_remain_literal_in_code_span(tmp_path):
    folder = tmp_path / 'ligand'
    ligand(folder)
    data = json.loads((folder / 'preparation.json').read_text())
    data['input_smiles'] = r'F/C=C\F'
    meta = save(folder / 'preparation.json', data)
    manifest = json.loads((folder / 'manifest.json').read_text())
    manifest['files']['preparation.json'] = meta
    save(folder / 'manifest.json', manifest)
    text = deliver({'results': [{'kind': 'openff', 'path': str(folder)}]}, tmp_path)['report_markdown']
    assert r'Input SMILES: `F/C=C\F`.' in text


def md_fixture(folder, engine='gromacs'):
    native = folder / 'native/result-00'
    native.mkdir(parents=True)
    (native / 'production.mdp').write_text('integrator = sd\ndt = 0.002\nnsteps = 10000\npcoupl = C-rescale\n')
    (native / 'system.gro').write_text('fixture\n6598\n')
    files = [{'path': str(path), 'native_path': path.name,
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
             for path in native.iterdir()]
    result = {'schema': f'fs2-serve.nebius.ai/{engine}-workflow-result/v1', 'status': 'succeeded',
              'operation_id': 'test-operation', 'completed_steps': ['nvt', 'npt', 'production'],
              'gpu_snapshot_used': False, 'commands': [],
              'files': [{**f, 'path': f['native_path']} for f in files]}
    meta = save(folder / 'output-00.artifact', result)
    save(folder / 'receipt.json', {'state': 'verified', 'operation_id': 'test-operation',
        'verified_artifacts': [{**meta, 'path': str(folder / 'output-00.artifact')}]})
    save(folder / 'native-files.json', {'schema': 'scientific-ai/native-md-files/v1', 'results': [
        {'engine': engine, 'source_result_sha256': meta['sha256'], 'files': files}]})


def test_md_reports_actual_config_not_longer_run_or_invented_statistics(tmp_path):
    md_fixture(tmp_path / 'run')
    text = deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)['report_markdown']
    assert '6598' in text and '| sd | 10000 | 0.002 | 20 | C-rescale |' in text
    assert '1 ns' not in text and 'GPU snapshot' not in text
    assert 'none are invented' in text and 'convergence are not established' in text
    (tmp_path / 'run/native/result-00/production.mdp').write_text('nsteps=500000\n')
    with pytest.raises(ValueError, match='changed'):
        deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)


@pytest.mark.parametrize('engine', ['gromacs', 'namd', 'amber', 'lammps', 'openmm'])
def test_recovery_receipt_delivers_without_copying_or_changing_files(tmp_path, engine):
    folder = tmp_path / 'run'
    md_fixture(folder, engine)
    (folder / 'receipt.json').rename(folder / 'recovery-receipt.json')
    before = {str(path): path.read_bytes() for path in folder.rglob('*') if path.is_file()}
    result = deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)
    assert result['inference_submitted'] is False
    assert f'{engine.upper()}: completed engine operation' in result['report_markdown']
    assert 'file=run%2Frecovery-receipt.json' in result['report_markdown']
    assert not (folder / 'receipt.json').exists()
    assert before == {str(path): path.read_bytes() for path in folder.rglob('*') if path.is_file()}


def test_recovery_cannot_bypass_existing_receipt_or_operation_identity(tmp_path):
    folder = tmp_path / 'run'
    md_fixture(folder)
    receipt = json.loads((folder / 'receipt.json').read_text())
    save(folder / 'recovery-receipt.json', receipt)
    save(folder / 'receipt.json', {**receipt, 'state': 'failed'})
    with pytest.raises(ValueError, match='verified completed-result receipt'):
        deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)
    (folder / 'receipt.json').unlink()
    save(folder / 'recovery-receipt.json', {**receipt, 'operation_id': 'other-operation'})
    with pytest.raises(ValueError, match='does not match the completed operation'):
        deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)


def test_recovery_receipt_still_verifies_original_result_bytes(tmp_path):
    folder = tmp_path / 'run'
    md_fixture(folder)
    (folder / 'receipt.json').rename(folder / 'recovery-receipt.json')
    (folder / 'output-00.artifact').write_text('{}')
    with pytest.raises(ValueError, match='differ from their saved manifest'):
        deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)


def test_no_model_authored_fields_accepted(tmp_path):
    with pytest.raises(ValueError, match='exactly'):
        deliver({'results': [{'kind': 'mmcif', 'path': 'file', 'atoms': 500}]}, tmp_path)


def test_compound_delivery_includes_all_files_and_fails_if_any_is_missing(tmp_path, monkeypatch):
    import scientific_verified_results as reports
    monkeypatch.setattr(reports, 'mmcif_card', lambda path, root: 'Measured fixture inventory')
    (tmp_path / 'requested.csv').write_text('chain,count\nA,76\n')
    args = {'results': [{'kind': 'mmcif', 'path': 'source.cif'},
                        {'kind': 'file', 'path': 'requested.csv'}]}
    result = deliver(args, tmp_path)
    assert result['result_count'] == 2
    assert 'Measured fixture inventory' in result['report_markdown']
    assert '[requested.csv](/demos?' in result['report_markdown']
    assert hashlib.sha256((tmp_path / 'requested.csv').read_bytes()).hexdigest() in result['report_markdown']
    assert 'not a scientific validation' in result['report_markdown']
    args['results'].append({'kind': 'file', 'path': 'missing.png'})
    with pytest.raises(ValueError, match='does not exist'):
        deliver(args, tmp_path)


def test_typed_inventory_preserves_measured_files_without_ending_request(monkeypatch):
    spec = importlib.util.spec_from_file_location('inventory_execution', Path(__file__).with_name('execution-mcp.py'))
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    seen = []
    def measured(args):
        seen.append(args)
        return {'schema': 'scientific-verified-delivery/v1', 'report_markdown': 'Measured fixture',
                'status': 'completed', 'result_count': 1, 'inference_submitted': False}
    monkeypatch.setattr(execution, 'deliver_scientific_results', measured)
    current = execution.inspect_mmcif_inventory({'path': 'exact.cif'})
    assert current['schema'] == 'scientific-mmcif-inventory/v1'
    assert 'Continue any requested exports' in current['guidance']
    assert seen == [{'results': [{'kind': 'mmcif', 'path': 'exact.cif'}]}]
    for invalid in ({}, {'path': ''}, {'path': 'exact.cif', 'finish_request': 'true'},
                    {'path': 'exact.cif', 'finish_request': True},
                    {'path': 'exact.cif', 'finish_request': False},
                    {'path': 'exact.cif', 'finish_request': True, 'report': 'invented'}):
        with pytest.raises(ValueError, match='exact input path'):
            execution.inspect_mmcif_inventory(invalid)
