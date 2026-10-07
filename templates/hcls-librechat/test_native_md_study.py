"""Offline fixtures qualify integration, not any native engine's performance."""
import asyncio
import csv
import json
from pathlib import Path
import re

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow
from test_native_md_report import recorded_run, bind_result

pytest_plugins = ('test_scientific_study',)


def analysis_plan(manifest, expected=3):
    return {'schema': study.SCHEMA, 'title': 'Native MD report', 'steps': [
        {'id': 'timings', 'kind': 'analysis', 'method': 'native-md-timing',
         'arguments': {'manifest_file': manifest, 'expected_repeats': expected}}],
        'deliverables': [
            {'name': 'Native timing report', 'role': 'report',
             'source': {'step': 'timings', 'file': 'native-timing-report.md'}},
            {'name': 'Native timing rows', 'role': 'metrics',
             'source': {'step': 'timings', 'file': 'native-timings.csv'}},
            {'name': 'Native timing provenance', 'role': 'provenance',
             'source': {'step': 'timings', 'file': 'native-timing-report.json'}}]}


def finish(identifier, **kwargs):
    for _ in range(5):
        value = asyncio.run(study.advance(identifier, **kwargs))
        if value['state'] in study.FINAL:
            return value
    pytest.fail('Study did not terminate within its explicit phase count')


def test_actual_native_helper_is_discoverable_and_hash_frozen(mounted):
    folder = mounted / 'recovered'
    recorded_run(folder)
    before = {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    discovery = describe_workflow(['batch', 'native-md-timing'])
    assert 'native-files.json' in json.dumps(discovery)
    started = study.submit(analysis_plan(str(folder / 'native-files.json')), mounted / 'study')
    receipt = json.loads((study.directory(started['id']) / 'receipt.json').read_text())
    assert set(receipt['implementations']) == {'native-md-timing', 'native-md-verified-results'}
    value = finish(started['id'])
    assert value['state'] == 'completed'
    files = value['steps']['timings']['files']
    data = json.loads(Path(files['native-timing-report.json']['path']).read_text())
    assert data['complete'] and data['reported_repeats'] == 3
    assert [row['performance_ns_per_day'] for row in data['timing_rows']] == [123.5] * 3
    with Path(files['native-timings.csv']['path']).open() as stream:
        assert len(list(csv.DictReader(stream))) == 3
    assert len(value['artifacts']) == 3
    assert before == {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def test_future_batch_native_mapping_produces_complete_report_without_replay(mounted):
    source = mounted / 'bundle.tar.gz'
    source.write_bytes(b'offline fixture, not native input')
    parameters = mounted / 'parameters.json'
    parameters.write_text('{}')
    plan = analysis_plan({'step': 'simulate', 'file': 'native-files.json'})
    plan['steps'].insert(0, {'id': 'simulate', 'kind': 'batch', 'model': 'gromacs',
        'tool': 'submit_gromacs_workflow', 'operation': 'run-workflow',
        'source': str(source), 'parameters': str(parameters), 'entry_name': 'gromacs-inputs',
        'semantic_type': 'gromacs-input-bundle/v1', 'media_type': 'application/x-tar',
        'compression': 'gzip', 'idempotency_key': 'offline-test-not-submitted',
        'display_name': 'Offline native fixture'})
    started = study.submit(plan, mounted / 'study')
    calls = []

    async def model(step, record):
        calls.append(step['idempotency_key'])
        folder = Path(record['output_directory']) / 'steps' / step['id'] / 'operation'
        recorded_run(folder)
        (folder / 'recovery-receipt.json').rename(folder / 'receipt.json')
        return {'state': 'completed', 'operation_id': 'operation-one',
                'files': {p.name: study.measure(p) for p in folder.iterdir()
                          if p.is_file() and p.name != 'receipt.json'}}

    value = finish(started['id'], model_runner=model)
    assert value['state'] == 'completed' and len(calls) == 1
    assert finish(started['id'], model_runner=model)['state'] == 'completed'
    assert len(calls) == 1
    text = Path(value['steps']['timings']['files']['native-timing-report.md']['path']).read_text()
    assert '123.5' in text and 'repeat-3' in text and 'Source log' in text


@pytest.mark.parametrize('filename', ['result.json', 'output-manifest.json'])
def test_platform_envelope_is_rejected_before_any_study_admission(mounted, filename):
    path = mounted / filename
    path.write_text('{}')
    with pytest.raises(ValueError, match='exact native-files.json'):
        study.submit(analysis_plan(str(path)), mounted / 'study')
    assert not (mounted / 'study/study-binding.json').exists()


def test_missing_timing_rows_retain_honest_diagnostics_not_success(mounted):
    folder = mounted / 'recovered'
    native, mapping = recorded_run(folder)
    native['commands'] = native['commands'][:1]
    bind_result(folder, native, mapping)
    started = study.submit(analysis_plan(str(folder / 'native-files.json')), mounted / 'study')
    value = finish(started['id'])
    assert value['state'] != 'completed' and not value.get('artifacts')
    reports = list((mounted / 'study/steps/timings').glob('generation-*/native-timing-report.json'))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert not report['complete'] and not report['timing_rows']
    assert any('Expected 3' in gap for gap in report['gaps'])


def test_changed_native_log_cannot_become_a_report(mounted):
    folder = mounted / 'recovered'
    recorded_run(folder)
    (folder / 'native/result-00/repeat-1-1.log').write_text('changed')
    started = study.submit(analysis_plan(str(folder / 'native-files.json')), mounted / 'study')
    assert finish(started['id'])['state'] != 'completed'
    assert not list((mounted / 'study').rglob('native-timing-report.md'))


def test_portable_saved_study_example_passes_real_admission_validation(mounted):
    source = Path(__file__).resolve().parents[2] / 'skills/scientific-ai/gromacs/references/timing-study.md'
    example = json.loads(re.search(r'```json\n(.*?)\n```', source.read_text(), re.S)[1])
    for name in ('source', 'parameters'):
        path = mounted / ('input.tar.gz' if name == 'source' else 'parameters.json')
        path.write_text('offline fixture' if name == 'source' else '{}')
        example['steps'][0][name] = str(path)
    assert study.validate(example)
    assert example['steps'][1]['method'] == 'native-md-timing'
    assert example['steps'][1]['arguments']['expected_repeats'] == 3
