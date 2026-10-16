"""Prepare one new, already specified TPR run using the existing study executor.

No molecular parameter changes, inference, new scheduler or checkpoint resume.
The caller must resolve the optional precheck and any scientific decisions first.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from scientific_receipts import file_measurement, persist_local_file, receipt_lock
from scientific_study import path_in_workspace
from scientific_workflow_draft import compose

BUNDLER = Path('/app/skill/gromacs/scripts/make-input-bundle.py')
RENDERER = Path('/opt/bionemo/native_md_preview.py')


def tpr_protocol(path):
    # GROMACS dumps coordinates too; keep that potentially large output out of
    # memory and the chat. Only exact input-record fields are needed here.
    with tempfile.TemporaryFile(mode='w+b') as dump:
        subprocess.run(['gmx', 'dump', '-s', str(path)], stdout=dump,
                       stderr=subprocess.PIPE, check=True, timeout=90)
        dump.seek(0)
        header = dump.read(128 * 1024).decode('utf-8')
    values = {}
    for key in ('dt', 'nsteps', 'init-step', 'integrator'):
        matches = re.findall(r'^\s*' + re.escape(key) + r'\s*=\s*(\S+)\s*$', header, re.M)
        if len(matches) != 1:
            raise ValueError('Cannot establish the exact TPR input field: ' + key)
        values[key] = matches[0]
    dt, steps, initial = float(values['dt']), int(values['nsteps']), int(values['init-step'])
    if not math.isfinite(dt) or dt <= 0 or steps <= 0 or initial != 0:
        raise ValueError('This helper requires a finite new run starting at step zero; use the existing resume workflow for continuation.')
    if values['integrator'] not in {'md', 'md-vv', 'md-vv-avek', 'sd', 'bd'}:
        raise ValueError('This helper prepares dynamics, not minimization or a different protocol.')
    return {'dt_ps': dt, 'requested_steps': steps, 'duration_ns': steps * dt / 1000,
            'initial_step': initial, 'integrator': values['integrator']}


def prepare(source, tpr, duration_ns, output, title='GROMACS simulation and results'):
    source, output = path_in_workspace(str(source)), path_in_workspace(str(output))
    if not source.is_dir() or output == source or source in output.parents:
        raise ValueError('Use an input directory and a separate output directory outside it.')
    relative = Path(tpr)
    if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.tpr':
        raise ValueError('Select the exact relative .tpr filename inside the input directory.')
    selected = (source / relative).resolve(strict=True)
    if source not in selected.parents or not selected.is_file():
        raise ValueError('The selected TPR must remain inside the input directory.')
    if not math.isfinite(duration_ns) or duration_ns <= 0:
        raise ValueError('duration_ns must be a finite positive number.')
    tpr_identity = file_measurement(selected)
    protocol = tpr_protocol(selected)
    if not math.isclose(protocol['duration_ns'], duration_ns, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(f"TPR encodes {protocol['duration_ns']} ns, not {duration_ns} ns. Make and validate a duration-only copy first; no study was submitted.")
    renderer = RENDERER
    spec = importlib.util.spec_from_file_location('native_input_bundle', BUNDLER)
    bundler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundler)
    with receipt_lock(output), tempfile.TemporaryDirectory(prefix='gromacs-plan-') as temporary:
        local = Path(temporary)
        archive = local / 'inputs.tar.gz'
        bundled = bundler.build(source, archive)
        if file_measurement(selected) != tpr_identity:
            raise ValueError('Source TPR changed during preparation; no study was submitted.')
        # The existing publisher verifies retained bytes; replay never silently
        # overwrites another source archive, renderer or parameter document.
        persist_local_file(archive, output / archive.name)
        persist_local_file(renderer, output / renderer.name)
        parameters = {'jobs': [{'id': 'production', 'steps': [{
            'id': 'production', 'command': 'mdrun',
            'args': ['-s', relative.as_posix(), '-deffnm', 'md', '-c', 'final.gro', '-cpo', 'state.cpt'],
            'expected_outputs': ['final.gro', 'state.cpt']}]}]}
        parameter_file = local / 'parameters.json'
        parameter_file.write_text(json.dumps(parameters, indent=2) + '\n')
        persist_local_file(parameter_file, output / parameter_file.name)
        outputs = ['native-timing-report.json', 'native-timings.csv', 'native-timing-report.md',
                   'md-structure-preview.html', 'md-structure-preview.json', 'final-structure-1.pdb']
        steps = [{'id': 'simulate', 'kind': 'batch', 'model': 'gromacs',
                  'tool': 'submit_gromacs_workflow', 'operation': 'run-workflow',
                  'source': str(output / archive.name), 'parameters': str(output / parameter_file.name),
                  'entry_name': 'gromacs-inputs', 'semantic_type': 'gromacs-input-bundle/v1',
                  'media_type': 'application/x-tar', 'compression': 'gzip',
                  'idempotency_key': 'gromacs-' + str(uuid.uuid5(uuid.NAMESPACE_URL, str(output))),
                  'display_name': title},
                 {'id': 'results', 'kind': 'analysis', 'method': 'python-script', 'arguments': {
                     'script': str(output / renderer.name),
                     'inputs': [{'name': 'native_manifest', 'file': {'step': 'simulate', 'file': 'native-files.json'}}],
                     'parameters': {'expected_repeats': 1, 'structure_preview': True}, 'outputs': outputs}}]
        names = ['Measured MD results', 'Native timing rows', 'Native timing report',
                 'Interactive final structure', 'Preview provenance', 'Final structure coordinates']
        deliverables = [{'name': name, 'role': 'report' if file.endswith(('.html', '.md', '-report.json')) else 'support',
                         'source': {'step': 'results', 'file': file}} for name, file in zip(names, outputs)]
        deliverables += [{'name': 'Native file mapping', 'role': 'provenance',
                          'source': {'step': 'simulate', 'file': 'native-files.json'}},
                         {'name': 'Output artifact manifest', 'role': 'provenance',
                          'source': {'step': 'simulate', 'file': 'output-manifest.json'}}]
        draft = compose({'draft_directory': str(output / 'draft'), 'title': title,
                         'steps': steps, 'deliverables': deliverables, 'finalize': True})
        if not draft['finalized']:
            raise ValueError('Prepared study did not validate: ' + str(draft['validation_error']))
    return {**draft, 'output_directory': str(output / 'run'), 'protocol': protocol,
            'source_tpr_sha256': tpr_identity[1],
            'input_bundle_sha256': bundled['sha256'], 'scientific_settings_changed': False,
            'next_call': {'tool': 'run_scientific_workflow', 'arguments': {
                'plan_file': draft['plan_file'], 'output_directory': str(output / 'run')}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--tpr', required=True, help='Exact relative TPR file; not a checkpoint.')
    parser.add_argument('--duration-ns', type=float, required=True, help='Validate the already encoded duration; never change it.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--title', default='GROMACS simulation and results')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.tpr, args.duration_ns, args.output, args.title)))
