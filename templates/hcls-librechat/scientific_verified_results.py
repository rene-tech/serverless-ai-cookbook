"""Factual result cards from existing files, not model-authored measurements.

No inference, simulation, parameter substitution or artifact transport occurs
here. Native MD publication receipts are retained; only the small files used
to calculate this summary are rehashed (not multi-GB trajectories on each view).
"""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def within(path, root):
    path = (root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Result path must remain inside the mounted workspace.')
    return path


def verify(path, expected):
    size = expected.get('size_bytes', expected.get('bytes'))
    if not path.is_file() or path.stat().st_size != size or digest(path) != expected.get('sha256'):
        raise ValueError('Result bytes differ from their saved manifest: ' + path.name)
    return path


def link(path, root, directory=False):
    relative = path.relative_to(root)
    query = {'tab': 'workspace', 'path': str(relative if directory else relative.parent)}
    if not directory:
        query['file'] = str(relative)
    return '/demos?' + urlencode(query)


def cell(value):
    return str(value).replace('\\', '\\\\').replace('|', '\\|').replace('\n', ' ').replace('`', "'")


def openff_card(folder, root):
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest.get('schema') != 'scientific-openff-files/v1':
        raise ValueError('Not an OpenFF preparation manifest.')
    files = manifest.get('files', {})
    if not {'ligand.top', 'ligand.gro', 'preparation.json', 'charges.json'}.issubset(files):
        raise ValueError('OpenFF preparation is incomplete.')
    for name, expected in files.items():
        verify(within(name, folder), expected)
    data = json.loads((folder / 'preparation.json').read_text())
    if data.get('schema') != 'scientific-openff-preparation/v1':
        raise ValueError('Missing supported OpenFF measurement provenance.')
    charges = data['partial_charges_e']
    if len(charges) != data['atom_count'] or not all(math.isfinite(v) for v in charges):
        raise ValueError('Invalid saved charge/atom inventory.')
    if abs(sum(charges) - data['formal_charge_e']) > 1e-5 or abs(sum(charges) - data['charge_sum_e']) > 1e-8:
        raise ValueError('Saved charge totals disagree.')
    rows = [('Atoms', data['atom_count']), ('Force field', data['force_field']),
            ('Charge method', data['charge_method']), ('Formal charge (e)', data['formal_charge_e']),
            ('Partial-charge sum (e)', f"{data['charge_sum_e']:.8g}"),
            ('CPU reference energy (kJ/mol)', f"{data['cpu_reference_energy_kj_mol']:.8g}"),
            ('Charge assignment (s)', f"{data['charge_seconds']:.2f}"),
            ('Preparation (s)', f"{data['elapsed_seconds']:.2f}")]
    text = ['### Standalone ligand prepared', '', f"Input SMILES: `{cell(data['input_smiles'])}`.", '',
            '| Measured or recorded field | Value |', '|---|---|']
    text += [f'| {label} | {cell(value)} |' for label, value in rows]
    text += ['', 'Versions: ' + ', '.join(f'{cell(k)} {cell(v)}' for k, v in data['versions'].items()) + '.', '',
             'All listed preparation files were checked against their saved SHA-256 hashes.', '']
    text += [f'- [{cell(name)}]({link(folder / name, root)})' for name in sorted(files)]
    text += ['', 'Scope: a standalone ligand in an artificial empty export box—not a solvated protein/membrane system. '
             'Finite CPU energy and charge checks do not establish force-field accuracy. '
             'GROMACS preprocessing and matched-engine energy equivalence have not been validated by this helper.']
    return '\n'.join(text)


def mmcif_card(path, root):
    helper = os.environ.get('SCIENTIFIC_MMCIF_HELPER', '/opt/bionemo/inspect-mmcif.py')
    python = os.environ.get('SCIENTIFIC_CLIENT_PYTHON', '/opt/scientific-client/bin/python')
    completed = subprocess.run([python, helper, str(path), '--format', 'markdown'],
                               capture_output=True, text=True, timeout=20)
    if completed.returncode:
        raise ValueError('Structure inventory failed: ' + completed.stderr[-1500:])
    return completed.stdout.strip() + f'\n\n[Source file]({link(path, root)})'


def md_card(folder, root):
    receipt = json.loads((folder / 'receipt.json').read_text())
    if receipt.get('state') != 'verified' or not receipt.get('operation_id'):
        raise ValueError('MD operation does not have a verified completed-result receipt.')
    manifest = json.loads((folder / 'native-files.json').read_text())
    if manifest.get('schema') != 'scientific-ai/native-md-files/v1' or not manifest.get('results'):
        raise ValueError('Native MD files are not materialized. Recover the existing operation first.')
    artifacts = receipt.get('verified_artifacts', [])
    texts = []
    for index, native in enumerate(manifest['results']):
        source = next((a for a in artifacts if a.get('sha256') == native['source_result_sha256']), None)
        if not source:
            raise ValueError('Native engine result has no matching publication receipt.')
        source_path = within(source['path'], root)
        result = json.loads(verify(source_path, source).read_text())
        engine = native['engine']
        if (result.get('status') != 'succeeded' or result.get('operation_id') != receipt['operation_id'] or
                result.get('schema') != f'fs2-serve.nebius.ai/{engine}-workflow-result/v1'):
            raise ValueError('Engine result does not match the completed operation.')
        expected = {v['path']: v for v in result['files']}
        files = {}
        native_root = folder / 'native' / f'result-{index:02d}'
        for item in native['files']:
            path = within(item['path'], native_root)
            original = expected.get(item['native_path'], {})
            if (item['sha256'], item['size_bytes']) != (original.get('sha256'), original.get('size_bytes')):
                raise ValueError('Native file mapping disagrees with engine result.')
            if not path.is_file() or path.stat().st_size != item['size_bytes']:
                raise ValueError('Published native file is missing or changed: ' + item['native_path'])
            files[item['native_path']] = (path, item)
        text = [f'### {cell(engine.upper())}: completed engine operation', '',
                f"Operation: `{receipt['operation_id']}`.",
                f"Completed steps: {', '.join(cell(v) for v in result['completed_steps'])}.",
                f"GPU snapshot used: {result.get('gpu_snapshot_used', 'not recorded')}.",
                f"Native checkpoint generation: {result.get('native_checkpoint_generation', 'not recorded')}."]
        if engine == 'gromacs':
            if 'system.gro' in files:
                path, entry = files['system.gro']
                verify(path, entry)
                with path.open() as stream:
                    next(stream)
                    count = int(next(stream).strip())
                text += [f'Input particle count: {count} (system.gro).']
            text += ['', 'Saved configuration (duration is configured, not a convergence claim):', '',
                     '| File | Integrator | Steps | dt (ps) | Configured duration (ps) | Pressure coupling |',
                     '|---|---|---:|---:|---:|---|']
            for name, (path, entry) in sorted(files.items()):
                if not name.endswith('.mdp'):
                    continue
                verify(path, entry)
                params = {}
                for line in path.read_text().splitlines():
                    line = line.split(';', 1)[0]
                    if '=' in line:
                        key, value = line.split('=', 1)
                        params[key.strip().lower().replace('_', '-')] = value.strip()
                dynamics = params.get('integrator') in ('md', 'md-vv', 'md-vv-avek', 'sd', 'bd')
                duration = 'not a dynamics phase'
                if dynamics:
                    steps, dt = int(params['nsteps']), float(params['dt'])
                    duration = f'{steps * dt:g}' if steps >= 0 else 'unbounded'
                text += [f"| [{cell(name)}]({link(path, root)}) | {cell(params.get('integrator', 'not recorded'))} | "
                         f"{cell(params.get('nsteps', 'not recorded'))} | {cell(params.get('dt', 'not recorded'))} | "
                         f"{duration} | {cell(params.get('pcoupl', 'not explicitly set'))} |"]
        performances = [c for c in result.get('commands', []) if c.get('performance_ns_per_day') is not None]
        if performances:
            text += ['', '| Engine command | ns/day (engine-reported) | Wall time (s) |', '|---|---:|---:|']
            text += [f"| {cell(c['step_id'])}, segment {c.get('segment', '?')} | {c['performance_ns_per_day']:.3f} | {c['wall_seconds']:.3f} |"
                     for c in performances]
        text += ['', f'[All native inputs, logs and trajectories]({link(native_root, root, directory=True)}) · '
                 f'[Publication receipt]({link(folder / "receipt.json", root)}) · '
                 f'[Native file manifest]({link(folder / "native-files.json", root)})', '',
                 'The engine completed; scientific equivalence, equilibration and convergence are not established by this receipt. '
                 'Temperature, pressure and density statistics require analysis of the saved trajectory/energy data; none are invented here. '
                 'Report-source files were rehashed; large trajectory hashes are from the original verified publication.']
        texts.append('\n'.join(text))
    return '\n\n'.join(texts)


def deliver(args, workspace):
    root = Path(workspace).resolve()
    results = args.get('results')
    if not isinstance(results, list) or not results:
        raise ValueError('Supply existing result references, not model-authored numbers or prose.')
    cards = []
    for item in results:
        if not isinstance(item, dict) or set(item) != {'kind', 'path'}:
            raise ValueError('Each result needs exactly kind and path.')
        handler = {'mmcif': mmcif_card, 'openff': openff_card, 'native-md': md_card}.get(item['kind'])
        if handler is None:
            raise ValueError('Unsupported verified result kind.')
        cards.append(handler(within(item['path'], root), root))
    return {'schema': 'scientific-verified-delivery/v1', 'status': 'completed',
            'report_markdown': '\n\n---\n\n'.join(cards), 'result_count': len(cards),
            'inference_submitted': False}
