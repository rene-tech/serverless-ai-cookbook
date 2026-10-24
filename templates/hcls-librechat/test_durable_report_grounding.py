"""CPU-only receipt and report regression; synthetic files, no model calls."""
import asyncio
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

import pytest

import native_md_report as reporter
import scientific_study as study
import scientific_workflow_view as view
from test_native_md_observations import recovery, amber_command
from test_native_md_report import recorded_run, bind_result, observed_openmm
from test_scientific_study import mounted, plan  # noqa: F401


def amber_fixture(root):
    return recovery(root, 'amber', amber_command(), {'nested/report.results': '''
 NSTEP = 100 TIME(PS) = 15.500 TEMP(K) = 310.0 PRESS = 1.0
 NSTEP = 500 TIME(PS) = 17.500 TEMP(K) = 297.25 PRESS = 1.0
 A V E R A G E S O V E R 5 S T E P S
 NSTEP = 500 TIME(PS) = 17.500 TEMP(K) = 303.5 PRESS = 1.0
 | Average timings for all steps:
 | ns/day = 63.5 seconds/ns = 1360
'''})


def test_manual_status_never_establishes_supervisor_ownership(mounted):
    output = mounted / 'manual'
    output.mkdir()
    (output / 'STUDY.json').write_text(json.dumps({'state': 'running',
        'operations': ['op-already-accepted'], 'remaining': ['analysis', 'report']}))
    before = (output / 'STUDY.json').read_bytes()
    with pytest.raises(ValueError, match='does not schedule work'):
        view.read_workflow(str(output))
    assert (output / 'STUDY.json').read_bytes() == before
    assert study.list_studies() == []


def test_full_registered_scope_and_stopped_or_ambiguous_dispositions(mounted):
    started = study.submit(plan(), mounted / 'whole')
    public = view.public_workflow(started)
    assert [p['id'] for p in public['registered_phases']] == ['prepare', 'model', 'report']
    assert public['continuation_state'] == 'registered' and public['operations'] == []
    # An operation ID by itself is not ownership of future phases.
    unknown = view.public_workflow({'output_directory': str(mounted / 'unknown'),
        'study_admission': 'unknown', 'steps': {'model': {'operation_id': 'op-known'}}})
    assert not unknown['durable_workflow'] and unknown['continuation_state'] == 'unconfirmed'
    assert unknown['operation_admission'] == 'unknown' and unknown['operation_id'] == 'op-known'
    for state, expected in [('needs_attention', 'blocked'), ('failed', 'stopped'), ('cancelled', 'stopped')]:
        result = view.public_workflow({**started, 'state': state,
            'steps': {'model': {'operation_id': 'op-known', 'state': 'running'}},
            'failure': {'admission': 'not-submitted', 'message': 'later phase rejected'}})
        assert result['continuation_state'] == expected
        assert result['operation_id'] == 'op-known'
        assert result['failure']['admission'] == 'not-submitted'


def test_later_handwritten_phases_cannot_change_admitted_scope(mounted):
    started = study.submit(plan(), mounted / 'whole')
    saved = study.directory(started['id']) / 'plan.json'
    changed = json.loads(saved.read_text())
    changed['steps'].append({'id': 'extra', 'kind': 'analysis', 'method': 'write-json',
                            'arguments': {'filename': 'unexpected.json', 'value': 1}})
    saved.write_text(json.dumps(changed))
    observed = view.read_workflow(str(mounted / 'whole'))
    assert observed['continuation_state'] == 'unconfirmed' and not observed['durable_workflow']
    assert 'plan identity changed' in observed['registration_failure']
    failed = asyncio.run(study.advance(started['id']))
    assert failed['state'] == 'failed' and not failed['durable_study']
    assert not list((mounted / 'whole').rglob('unexpected.json'))


@pytest.mark.parametrize('changed', ['temperature', 'operation_id', 'source'])
def test_typed_projection_rejects_manual_values_ids_or_changed_evidence(mounted, changed):
    folder = amber_fixture(mounted)
    data = reporter.collect(folder, mounted)
    assert data['complete'] and data['observations'][0]['temperature_k'] == 297.25
    summary = reporter.verified_summary(json.dumps(data), mounted)
    assert '| Last reported temperature (K) | 297.25 |' in summary['text']
    assert '| Temperature observation step | 500 |' in summary['text']
    assert '303.5' not in summary['text'] and '310.0' not in summary['text']
    if changed == 'temperature':
        data['observations'][0]['temperature_k'] = 303.5
    elif changed == 'operation_id':
        data['operation_id'] = 'op-unsupported-manual-id'
    else:
        source = Path(data['observations'][0]['temperature_file'])
        source.write_text(source.read_text().replace('297.25', '298.25'))
    with pytest.raises(ValueError, match='differ'):
        reporter.verified_summary(json.dumps(data), mounted)


def test_retained_six_phase_study_and_typed_assembly_finish_without_inference(mounted):
    shapes = [('gromacs', ['gmx', 'mdrun'], {}), ('gromacs', ['gmx_mpi', 'mdrun'], {}),
        ('amber', [], {}), ('namd', ['namd3', 'simulation.namd'], {}),
        ('lammps', ['lmp', '-in', 'simulation.in'], {}), ('openmm', [], {})]
    steps, sections, originals = [], [], {}
    for index, (engine, argv, extra) in enumerate(shapes):
        root = mounted / f'retained {index}'
        if engine == 'amber':
            folder = amber_fixture(root)
        else:
            folder = root / 'recovery'
            native, mapping, *_ = (observed_openmm(folder) if engine == 'openmm' else recorded_run(folder, engine))
            if engine != 'openmm':
                native['commands'] = [{**row, 'command': argv, **extra} for row in native['commands'][1:]]
                bind_result(folder, native, mapping)
        receipt_path = folder / 'recovery-receipt.json'
        receipt = json.loads(receipt_path.read_text())
        native = json.loads((folder / 'output-00.artifact').read_text())
        mapping = json.loads((folder / 'native-files.json').read_text())
        receipt['operation_id'] = native['operation_id'] = f'op-retained-{index}'
        receipt_path.write_text(json.dumps(receipt))
        bind_result(folder, native, mapping)
        originals.update({str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()})
        steps.append({'id': f'analysis-{index}', 'kind': 'analysis', 'method': 'native-md-timing',
                      'arguments': {'manifest_file': str(folder / 'native-files.json')}})
        sections.append({'title': f'Retained result {index}', 'format': 'native-md',
                         'file': {'step': f'analysis-{index}', 'file': 'native-timing-report.json'}})
    steps.append({'id': 'assembly', 'kind': 'analysis', 'method': 'report',
                  'arguments': {'title': 'Retained MD results', 'sections': sections}})
    prepared = {'schema': study.SCHEMA, 'title': 'Analysis only', 'steps': steps,
        'deliverables': [{'name': 'Combined report', 'role': 'report',
                          'source': {'step': 'assembly', 'file': 'report.md'}}]}
    started = study.submit(prepared, mounted / 'study')
    assert len(view.public_workflow(started)['registered_phases']) == 7
    # The submitted plan owns every phase even after the caller exits.
    async def no_model(*args):
        pytest.fail('Retained result reporting must not submit/recover/download science')
    for _ in range(8):
        result = asyncio.run(study.advance(started['id'], model_runner=no_model))
    assert result['state'] == 'completed', result.get('failure')
    public = view.read_workflow(str(mounted / 'study'))
    assert public['continuation_state'] == 'completed' and public['operations'] == []
    aggregate = next(s for s in public['completion_summaries'] if s['source_step'] == 'assembly')
    assert aggregate['state'] == 'verified'
    assert {f'op-retained-{i}' for i in range(6)} <= set(re.findall(r'op-retained-\d', aggregate['text']))
    assert '| Last reported temperature (K) | 297.25 |' in aggregate['text']
    assert '| Last reported temperature (K) | unknown |' in aggregate['text']
    for url in re.findall(r'\]\(([^)]+)\)', aggregate['text']):
        assert '…' not in url and '...' not in url
        query = parse_qs(urlsplit(url).query)
        assert url.startswith('/demos?') and (mounted / query['file'][0]).is_file()
    assert all(Path(p).read_bytes() == data for p, data in originals.items())
