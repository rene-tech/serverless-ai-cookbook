import hashlib
import json
from pathlib import Path

import pytest
from scientific_verified_results import deliver


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}


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


def md_fixture(folder):
    native = folder / 'native/result-00'
    native.mkdir(parents=True)
    (native / 'production.mdp').write_text('integrator = sd\ndt = 0.002\nnsteps = 10000\npcoupl = C-rescale\n')
    (native / 'system.gro').write_text('fixture\n6598\n')
    files = [{'path': str(path), 'native_path': path.name,
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
             for path in native.iterdir()]
    result = {'schema': 'fs2-serve.nebius.ai/gromacs-workflow-result/v1', 'status': 'succeeded',
              'operation_id': 'test-operation', 'completed_steps': ['nvt', 'npt', 'production'],
              'gpu_snapshot_used': False, 'commands': [],
              'files': [{**f, 'path': f['native_path']} for f in files]}
    meta = save(folder / 'output-00.artifact', result)
    save(folder / 'receipt.json', {'state': 'verified', 'operation_id': 'test-operation',
        'verified_artifacts': [{**meta, 'path': str(folder / 'output-00.artifact')}]})
    save(folder / 'native-files.json', {'schema': 'scientific-ai/native-md-files/v1', 'results': [
        {'engine': 'gromacs', 'source_result_sha256': meta['sha256'], 'files': files}]})


def test_md_reports_actual_config_not_longer_run_or_invented_statistics(tmp_path):
    md_fixture(tmp_path / 'run')
    text = deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)['report_markdown']
    assert '6598' in text and '| sd | 10000 | 0.002 | 20 | C-rescale |' in text
    assert '1 ns' not in text and 'GPU snapshot used: False' in text
    assert 'none are invented' in text and 'convergence are not established' in text
    (tmp_path / 'run/native/result-00/production.mdp').write_text('nsteps=500000\n')
    with pytest.raises(ValueError, match='changed'):
        deliver({'results': [{'kind': 'native-md', 'path': 'run'}]}, tmp_path)


def test_no_model_authored_fields_accepted(tmp_path):
    with pytest.raises(ValueError, match='exactly'):
        deliver({'results': [{'kind': 'mmcif', 'path': 'file', 'atoms': 500}]}, tmp_path)
