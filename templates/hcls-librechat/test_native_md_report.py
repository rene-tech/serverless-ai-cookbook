import csv
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys

import pytest

import native_md_report as report
from test_scientific_verified_results import md_fixture, save


def recorded_run(folder, engine='gromacs', segments=1):
    md_fixture(folder, engine)
    native_path = folder / 'output-00.artifact'
    native = json.loads(native_path.read_text())
    manifest = json.loads((folder / 'native-files.json').read_text())
    native['job_id'] = 'benchmark'
    native['completed_steps'] = ['finite-tpr', 'repeat-1', 'repeat-2', 'repeat-3']
    native['commands'] = [{'step_id': 'finite-tpr', 'command': ['gmx', 'convert-tpr', '-s', 'original.tpr',
                                                               '-o', 'benchmark.tpr', '-nsteps', '10000']}]
    for index in (1, 2, 3):
        for segment in range(1, segments + 1):
            name = f'repeat-{index}-{segment}.log'
            path = folder / 'native/result-00' / name
            meta = save(path, {'fixture': 'not a real simulation'})
            native['files'].append({**meta, 'path': name})
            manifest['results'][0]['files'].append({**meta, 'path': str(path), 'native_path': name})
            native['commands'].append({'step_id': f'repeat-{index}', 'segment': segment,
                'command': ['gmx', 'mdrun', '-s', 'benchmark.tpr'], 'exit_code': 0,
                'wall_seconds': 3.125, 'performance_ns_per_day': 123.5,
                'checkpoint_step': segment * 10000, 'log': name})
    bind_result(folder, native, manifest)
    (folder / 'receipt.json').rename(folder / 'recovery-receipt.json')
    return native, manifest


def bind_result(folder, native, manifest):
    meta = save(folder / 'output-00.artifact', native)
    manifest['results'][0]['source_result_sha256'] = meta['sha256']
    save(folder / 'native-files.json', manifest)
    path = folder / ('recovery-receipt.json' if (folder / 'recovery-receipt.json').exists() else 'receipt.json')
    receipt = json.loads(path.read_text())
    receipt['verified_artifacts'] = [{**meta, 'path': str(folder / 'output-00.artifact')}]
    save(path, receipt)


def test_report_cli_emits_real_nonempty_rows_without_modifying_native_files(tmp_path):
    folder = tmp_path / 'recovered'
    recorded_run(folder)
    before = {str(path): path.read_bytes() for path in folder.rglob('*') if path.is_file()}
    command = [sys.executable, str(Path(report.__file__)), '--workspace', str(tmp_path),
               '--receipt-dir', str(folder), '--output-dir', str(tmp_path / 'report'), '--expected-repeats', '3']
    result = subprocess.run(command, text=True, capture_output=True, check=True)
    value = json.loads(result.stdout)
    assert value['complete'] and value['timing_row_count'] == 3 and not value['inference_submitted']
    assert before == {str(path): path.read_bytes() for path in folder.rglob('*') if path.is_file()}
    data = json.loads((tmp_path / 'report/native-timing-report.json').read_text())
    assert data['timing_rows'][0]['requested_steps'] == 10000
    assert data['timing_rows'][0]['checkpoint_step'] == 10000
    assert data['timing_rows'][0]['executed_steps'] is None
    assert data['timing_rows'][0]['durably_completed_steps'] is None
    rows = list(csv.DictReader((tmp_path / 'report/native-timings.csv').open()))
    assert len(rows) == 3 and rows[0]['performance_ns_per_day'] == '123.5'
    assert rows[0]['executed_steps'] == ''
    text = (tmp_path / 'report/native-timing-report.md').read_text()
    assert 'recovery-receipt.json' in text and '123.5' in text and 'unknown' in text
    again = subprocess.run(command, text=True, capture_output=True, check=True)
    assert again.stdout == result.stdout


def test_empty_or_missing_timing_cannot_be_a_complete_report(tmp_path):
    folder = tmp_path / 'recovered'
    native, manifest = recorded_run(folder)
    native['commands'] = native['commands'][:1]
    bind_result(folder, native, manifest)
    value = report.write_report(folder, tmp_path / 'report', tmp_path, 3)
    assert not value['complete'] and value['timing_row_count'] == 0
    assert any('No native' in gap for gap in value['gaps'])
    command = [sys.executable, str(Path(report.__file__)), '--workspace', str(tmp_path),
               '--receipt-dir', str(folder), '--output-dir', str(tmp_path / 'report'), '--expected-repeats', '3']
    assert subprocess.run(command, capture_output=True).returncode == 2


def test_changed_artifact_or_source_log_prevents_report(tmp_path):
    folder = tmp_path / 'recovered'
    recorded_run(folder)
    path = folder / 'native/result-00/repeat-1-1.log'
    original = path.read_bytes()
    path.write_bytes(original.replace(b'fixture', b'changed'))
    with pytest.raises(ValueError, match='differ'):
        report.write_report(folder, tmp_path / 'report', tmp_path, 3)
    assert not (tmp_path / 'report').exists()


def test_segments_are_not_independent_repeats_and_missing_rates_stay_unknown(tmp_path):
    folder = tmp_path / 'recovered'
    native, manifest = recorded_run(folder, segments=2)
    value = report.collect(folder, tmp_path, 3)
    assert value['complete'] and value['reported_repeats'] == 3 and len(value['timing_rows']) == 6
    native['commands'][1]['performance_ns_per_day'] = None
    bind_result(folder, native, manifest)
    value = report.collect(folder, tmp_path, 3)
    assert not value['complete'] and value['timing_rows'][0]['performance_ns_per_day'] is None
    assert not report.collect(folder, tmp_path, 6)['complete']


def test_existing_different_report_is_preserved(tmp_path):
    folder = tmp_path / 'recovered'
    recorded_run(folder)
    output = tmp_path / 'report'
    report.write_report(folder, output, tmp_path, 3)
    original = (output / 'native-timings.csv').read_bytes()
    with pytest.raises(ValueError, match='Existing report differs'):
        report.write_report(folder, output, tmp_path, 4)
    assert (output / 'native-timings.csv').read_bytes() == original


def test_requested_steps_are_bound_to_the_exact_tpr_and_native_override():
    command = {'command': ['gmx', 'mdrun', '-s', 'target.tpr']}
    other = [{'command': ['gmx', 'convert-tpr', '-o', 'other.tpr', '-nsteps', '99999']}]
    assert report.requested_steps('gromacs', command, other) is None
    assert report.requested_steps('gromacs', {'command': command['command'] + ['-nsteps', '1000']}, other) == 1000


def test_openmm_uses_explicit_segment_steps_and_excludes_minimization():
    assert report.requested_steps('openmm', {'requested_steps': 7500}, []) == 7500
    assert report.requested_steps('openmm', {}, []) is None
    assert report.is_simulation('openmm', {'kind': 'production'})
    assert report.is_simulation('openmm', {'kind': 'equilibrate'})
    assert not report.is_simulation('openmm', {'kind': 'minimize'})


@pytest.mark.parametrize('engine,args,extra', [
    ('namd', ['namd3', '+p8', 'simulation.namd'], {}),
    ('amber', ['pmemd.cuda', '-i', 'mdin'], {'kind': 'pmemd'}),
    ('lammps', ['lmp', '-in', 'simulation.in'], {}),
    ('openmm', ['python', '-m', 'fs2_openmm.engine', 'segment-request.json'], {'kind': 'production'}),
])
def test_other_md_command_shapes_do_not_invent_unrecorded_rates(tmp_path, engine, args, extra):
    folder = tmp_path / 'recovered'
    native, manifest = recorded_run(folder, engine)
    native['commands'] = [{**row, **extra, 'command': args} for row in native['commands'][1:]]
    for row in native['commands']:
        row['performance_ns_per_day'] = None
        if engine in ('amber', 'lammps'):
            row['argv'] = row.pop('command')
    bind_result(folder, native, manifest)
    value = report.collect(folder, tmp_path, 3)
    assert not value['complete'] and len(value['timing_rows']) == 3
    assert all(row['performance_ns_per_day'] is None for row in value['timing_rows'])


def observed_openmm(folder):
    native, manifest = recorded_run(folder, 'openmm')
    native['commands'] = [{**native['commands'][1], 'kind': 'production',
        'executed_steps': 25, 'durably_completed_steps': 25,
        'checkpoint_step': 126, 'requested_steps': 25,
        'validation': {'scientific': {'particles': 123}, 'initial_step': 101,
                       'final_step': 126, 'timestep_ps': .004, 'simulation_time_ps': 123,
                       'integration_seconds': 1.25, 'setup_seconds': .5}}]
    native['completed_steps'] = ['repeat-1']
    name = 'openmm-output/repeat-1/segment-000001/state.csv'
    path = folder / 'native/result-00' / name
    path.parent.mkdir(parents=True)
    path.write_text('#"Step","Time (ps)","Temperature (K)"\n120,122.976,298.5\n124,122.992,299.75\n')
    meta = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
    native['files'].append({**meta, 'path': name})
    manifest['results'][0]['files'].append({**meta, 'path': str(path), 'native_path': name})
    bind_result(folder, native, manifest)
    return native, manifest, path


def test_scientific_html_uses_observed_fields_and_separates_cumulative_time(tmp_path):
    folder, output = tmp_path / 'renamed-recovery', tmp_path / 'report'
    observed_openmm(folder)
    before = {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    value = report.write_report(folder, output, tmp_path)
    data = json.loads((output / 'native-timing-report.json').read_text())
    observed = data['observations'][0]
    assert observed['atom_count'] == 123
    assert observed['segment_physical_time_ps'] == .1
    assert observed['simulation_time_ps'] == 123
    assert observed['temperature_k'] == 299.75 and observed['temperature_step'] == 124
    document = (output / 'native-md-report.html').read_text()
    for expected in ['Integration time (s)</dt><dd>1.25', 'Engine setup time (s)</dt><dd>0.5',
                     'Native command wall time (s)</dt><dd>3.125', 'Last reported temperature (K)</dt><dd>299.75',
                     'Temperature observation step</dt><dd>124', 'Final step</dt><dd>126',
                     'Total operation elapsed time: unknown', 'Queue time: unknown',
                     '<title>Native MD report — ' + value['operation_id']]:
        assert expected in document
    assert before == {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def test_missing_science_stays_unknown_and_html_escapes_verified_identity(tmp_path):
    folder = tmp_path / 'run'
    native, manifest = recorded_run(folder)
    identity = 'op-example<script>alert(1)</script>'
    native['operation_id'] = identity
    receipt_file = folder / 'recovery-receipt.json'
    receipt = json.loads(receipt_file.read_text())
    receipt['operation_id'] = identity
    save(receipt_file, receipt)
    bind_result(folder, native, manifest)
    data = report.collect(folder, tmp_path)
    assert data['observations'][0]['atom_count'] is None
    assert data['observations'][0]['temperature_k'] is None
    document = report.html_report(data, tmp_path)
    assert html.escape(identity) in document and '<script>alert(1)</script>' not in document
    assert 'Last reported temperature (K)</dt><dd>unknown' in document
    assert 'Completed segment steps (recorded executed steps)</dt><dd>unknown' in document


def test_changed_temperature_evidence_is_rejected_without_publishing(tmp_path):
    folder, output = tmp_path / 'run', tmp_path / 'report'
    _, _, source = observed_openmm(folder)
    source.write_text(source.read_text().replace('299.75', '399.75'))
    with pytest.raises(ValueError, match='differ'):
        report.write_report(folder, output, tmp_path)
    assert not output.exists()
