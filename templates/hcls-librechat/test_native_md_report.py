import csv
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


@pytest.mark.parametrize('engine,args,extra', [
    ('namd', ['namd3', '+p8', 'simulation.namd'], {}),
    ('amber', ['pmemd.cuda', '-i', 'mdin'], {'kind': 'pmemd'}),
    ('lammps', ['lmp', '-in', 'simulation.in'], {}),
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
