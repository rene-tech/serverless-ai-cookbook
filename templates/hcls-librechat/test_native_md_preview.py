"""Fixture-only verification of the renderer; live native evidence is separate."""
import hashlib
import json
from pathlib import Path

import pytest

import native_md_preview as preview
from test_native_md_report import recorded_run, bind_result

PDB = 'ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C\nEND\n'


def fixture(folder):
    native, manifest = recorded_run(folder)
    path = folder / 'native/result-00/final.gro'
    path.write_text('offline coordinate fixture, not a simulation')
    meta = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
    native['files'].append({**meta, 'path': 'final.gro'})
    manifest['results'][0]['files'].append({**meta, 'path': str(path), 'native_path': 'final.gro'})
    native['commands'][-1]['command'] += ['-c', 'final.gro']
    bind_result(folder, native, manifest)
    return path, native, manifest


@pytest.fixture
def renderer(tmp_path, monkeypatch):
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'viewer-mcp.py').write_text('def viewer_html(text, fmt, title, entries):\n return "<html>" + title + text + "</html>"\n')
    monkeypatch.setenv('BIONEMO_ASSET_ROOT', str(assets))
    calls = []
    def convert(command, **kwargs):
        assert command[:2] == ['gmx', 'editconf']
        assert kwargs['timeout'] == 60 and kwargs['check']
        calls.append(command)
        Path(command[-1]).write_text(PDB)
    monkeypatch.setattr(preview.subprocess, 'run', convert)
    return calls


def test_exact_verified_final_coordinates_render_without_simulation(tmp_path, renderer):
    folder, output = tmp_path / 'run', tmp_path / 'preview'
    source, _, _ = fixture(folder)
    before = {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    files = preview.render_preview(folder, output, tmp_path)
    assert len(renderer) == 1 and renderer[0][3] == str(source)
    assert set(files) == {'final-structure-1.pdb', 'md-structure-preview.html', 'md-structure-preview.json'}
    assert 'not a trajectory animation' in (output / 'md-structure-preview.html').read_text()
    provenance = json.loads((output / 'md-structure-preview.json').read_text())
    assert not provenance['inference_submitted'] and not provenance['scientific_validity_claim']
    assert provenance['frames'][0]['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert before == {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    assert preview.render_preview(folder, output, tmp_path) == files


def test_openmm_mmcif_preview_uses_verified_bytes_without_conversion(tmp_path, renderer):
    folder = tmp_path / 'run'
    native, manifest = recorded_run(folder, engine='openmm')
    name = 'openmm-output/production/segment-000001/structure.cif'
    path = folder / 'native/result-00' / name
    path.parent.mkdir(parents=True)
    text = 'data_example\nloop_\n_atom_site.id\n_atom_site.Cartn_x\n1 0.0\n'
    path.write_text(text)
    meta = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
    native['files'].append({**meta, 'path': name})
    native['completed_steps'] = ['production']
    native['commands'] = [{'step_id': 'production', 'kind': 'production', 'segment': 1, 'exit_code': 0,
                           'validation': {'structure_file': 'structure.cif'}}]
    manifest['results'][0]['files'].append({**meta, 'path': str(path), 'native_path': name})
    bind_result(folder, native, manifest)
    output = tmp_path / 'preview'
    files = preview.render_preview(folder, output, tmp_path)
    assert not renderer
    assert 'final-structure-1.cif' in files
    assert (output / 'final-structure-1.cif').read_text() == text
    result = json.loads((output / 'md-structure-preview.json').read_text())
    assert result['frames'][0]['source_sha256'] == meta['sha256']
    path.write_text('changed')
    with pytest.raises(ValueError, match='differ|changed'):
        preview.render_preview(folder, tmp_path / 'other', tmp_path)


def test_changed_coordinate_or_existing_preview_is_not_silently_replaced(tmp_path, renderer):
    folder, output = tmp_path / 'run', tmp_path / 'preview'
    source, _, _ = fixture(folder)
    preview.render_preview(folder, output, tmp_path)
    (output / 'final-structure-1.pdb').write_text('preserve me')
    with pytest.raises(ValueError, match='Existing preview differs'):
        preview.render_preview(folder, output, tmp_path)
    source.write_text('changed native coordinates')
    with pytest.raises(ValueError, match='changed|differ'):
        preview.render_preview(folder, tmp_path / 'other', tmp_path)


def test_missing_final_coordinates_are_not_guessed_from_other_gro_files(tmp_path, renderer):
    folder = tmp_path / 'run'
    _, native, manifest = fixture(folder)
    native['commands'][-1]['command'][-1] = 'absent.gro'
    bind_result(folder, native, manifest)
    with pytest.raises(ValueError, match='absent from the verified native manifest'):
        preview.render_preview(folder, tmp_path / 'preview', tmp_path)
    assert not renderer


def test_declared_deffnm_and_subdirectory_are_resolved_exactly(tmp_path, renderer):
    folder = tmp_path / 'run'
    path, native, manifest = fixture(folder)
    native['commands'][-1]['command'] = ['gmx', 'mdrun', '-deffnm', 'final']
    bind_result(folder, native, manifest)
    preview.render_preview(folder, tmp_path / 'preview', tmp_path)
    assert renderer[0][3] == str(path)


def test_native_failure_is_not_turned_into_a_visual_success(tmp_path, renderer):
    folder = tmp_path / 'run'
    _, native, manifest = fixture(folder)
    native['status'] = 'failed'
    bind_result(folder, native, manifest)
    with pytest.raises(ValueError):
        preview.render_preview(folder, tmp_path / 'preview', tmp_path)
    assert not renderer


def test_saved_phase_cli_uses_the_same_verified_manifest(tmp_path, renderer, monkeypatch, capsys):
    fixture(tmp_path / 'run')
    binding = tmp_path / 'input-bindings.json'
    binding.write_text(json.dumps({'schema': 'scientific-python-bindings/v1',
        'inputs': {'native_manifest': str(tmp_path / 'run/native-files.json')}, 'parameters': {}}))
    monkeypatch.setenv('WORKSPACE', str(tmp_path))
    monkeypatch.setattr('sys.argv', ['preview', '--inputs', str(binding), '--output-dir', str(tmp_path / 'preview')])
    preview.main()
    result = json.loads(capsys.readouterr().out)
    assert not result['inference_submitted']
    assert {'native-timing-report.json', 'native-timing-report.md', 'native-timings.csv',
            'md-structure-preview.html'} <= set(result['files'])
    assert json.loads((tmp_path / 'preview/native-timing-report.json').read_text())['complete']


def test_phase_scratch_is_not_a_workspace_publication(tmp_path, renderer, monkeypatch, capsys):
    from native_md_report import write_report
    workspace = tmp_path / 'workspace'
    fixture(workspace / 'run')
    scratch = tmp_path / 'private-phase'
    scratch.mkdir()
    binding = scratch / 'input-bindings.json'
    binding.write_text(json.dumps({'schema': 'scientific-python-bindings/v1',
        'inputs': {'native_manifest': str(workspace / 'run/native-files.json')},
        'parameters': {'expected_repeats': 3}}))
    monkeypatch.setenv('WORKSPACE', str(workspace))
    monkeypatch.setattr('sys.argv', ['preview', '--inputs', str(binding), '--output-dir', str(scratch / 'output')])
    preview.main()
    result = json.loads(capsys.readouterr().out)
    assert 'md-structure-preview.html' in result['files']
    assert 'workspace_url' not in json.dumps(result)
    write_report(workspace / 'run', workspace / 'reference', workspace, 3)
    for name in ['native-timing-report.json', 'native-timing-report.md', 'native-timings.csv']:
        assert (scratch / 'output' / name).read_bytes() == (workspace / 'reference' / name).read_bytes()


@pytest.mark.parametrize('options', [{'expected_repeats': True}, {'expected_repeats': 0},
                                   {'structure_preview': 'true'}, {'unknown': 1}])
def test_invalid_report_parameters_never_render(tmp_path, renderer, monkeypatch, options):
    binding = tmp_path / 'input-bindings.json'
    binding.write_text(json.dumps({'schema': 'scientific-python-bindings/v1',
        'inputs': {'native_manifest': str(tmp_path / 'run/native-files.json')}, 'parameters': options}))
    monkeypatch.setattr('sys.argv', ['preview', '--inputs', str(binding), '--output-dir', str(tmp_path / 'preview')])
    with pytest.raises(ValueError):
        preview.main()
    assert not renderer
