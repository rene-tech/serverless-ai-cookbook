"""Read-only progress projection uses existing receipts, never a new submission."""
import copy
import json

import pytest

import scientific_study as study


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    record = {'output_directory': str(tmp_path / 'study'),
              'steps': {'simulate': {'operation_id': 'operation-one'}}}
    plan = {'steps': [{'id': 'simulate', 'kind': 'batch'}]}
    path = tmp_path / 'study/steps/simulate/operation/status.json'
    path.parent.mkdir(parents=True)
    return record, plan, path


def status():
    return {'operation': {'id': 'operation-one', 'status': 'running', 'gpu_type': 'private-device'},
            'progress': {'schema': 'scientific-ai/progress/v1', 'available': True, 'stale': True,
                         'updated_at': '2026-10-16T12:00:00Z', 'stale_after_seconds': 120,
                         'gpu_count': 8, 'native_job_id': 'private-native-job', 'steps': [
                             {'step_id': 'production', 'state': 'running', 'unit': 'ns',
                              'completed_units': 2.5, 'durable_completed_units': 2,
                              'target_units': 10, 'rate': 200, 'rate_unit': 'ns/day',
                              'rate_updated_at': '2026-10-16T12:00:00Z',
                              'runtime': {'image': 'private-image'}, 'gpu_count': 8}]}}


def test_saved_progress_is_bound_read_only_and_public(saved):
    record, plan, path = saved
    path.write_text(json.dumps(status()))
    before, original = path.read_bytes(), copy.deepcopy(record)
    values = study.model_progress(record, plan)
    assert values[0]['operation_id'] == 'operation-one'
    assert values[0]['progress']['stale'] is True
    row = values[0]['progress']['steps'][0]
    assert (row['completed_units'], row['durable_completed_units'], row['rate']) == (2.5, 2, 200)
    assert 'private-' not in json.dumps(values) and 'gpu' not in json.dumps(values)
    assert path.read_bytes() == before and record == original


@pytest.mark.parametrize('content', [None, '{broken', '[]', 'x' * (1024 * 1024 + 1),
                                    json.dumps({'operation': {'id': 'another-operation'}, 'progress': status()['progress']})])
def test_missing_invalid_or_other_operation_progress_stays_unknown(saved, content):
    record, plan, path = saved
    if content is not None:
        path.write_text(content)
    assert study.model_progress(record, plan) == []


def test_native_model_units_and_unknown_values_are_not_assumed_to_be_md(saved):
    record, plan, path = saved
    plan['steps'][0]['kind'] = 'native'
    value = status()
    row = value['progress']['steps'][0]
    row.update(unit='structures', completed_units=7, durable_completed_units=None,
               rate=None, rate_unit='structures/s', target_units=20)
    path.with_name('operation.json').write_text(json.dumps({**value['operation'], 'progress': value['progress']}))
    observed = study.model_progress(record, plan)[0]['progress']['steps'][0]
    assert observed['completed_units'] == 7 and observed['unit'] == 'structures'
    assert observed['durable_completed_units'] is None and observed['rate'] is None


def test_resume_uses_latest_observation_without_summing_attempts(saved):
    record, plan, path = saved
    value = status()
    path.write_text(json.dumps(value))
    assert study.model_progress(record, plan)[0]['progress']['steps'][0]['completed_units'] == 2.5
    value['progress']['steps'][0].update(completed_units=2.1, durable_completed_units=2, rate=None)
    path.write_text(json.dumps(value))
    row = study.model_progress(record, plan)[0]['progress']['steps'][0]
    assert row['completed_units'] == 2.1 and row['durable_completed_units'] == 2 and row['rate'] is None
