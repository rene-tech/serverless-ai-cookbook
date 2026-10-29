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
import re
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
    # Backslashes are chemical stereo syntax and literal inside a code span.
    # Markdown table escaping here would silently alter the displayed molecule.
    smiles = str(data['input_smiles'])
    fence = '`' * (max((len(part) for part in re.findall(r'`+', smiles)), default=0) + 1)
    text = ['### Standalone ligand prepared', '', f"Input SMILES: {fence}{smiles}{fence}.", '',
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


def file_card(path, root):
    if not path.is_file():
        raise ValueError('Requested output file does not exist: ' + path.name)
    return (f'[{cell(path.name)}]({link(path, root)}) — {path.stat().st_size} bytes; '
            f'SHA-256 `{digest(path)}`.\n\n'
            'File existence and bytes verified; this is not a scientific validation of its contents.')


def failure_card(folder, root):
    receipt_path = folder / 'receipt.json'
    if not receipt_path.exists():
        receipt_path = folder / 'recovery-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    status = json.loads((folder / 'status.json').read_text())
    if not isinstance(receipt, dict) or not isinstance(status, dict):
        raise ValueError('Invalid retained failure evidence.')
    operation = status.get('operation', {})
    identity = receipt.get('identity', {})
    operation_id, state = receipt.get('operation_id'), receipt.get('state')
    model = status.get('model_id')
    if (not isinstance(operation_id, str)
            or not re.fullmatch(r'op-[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?', operation_id)
            or state not in ('failed', 'cancelled', 'timed_out', 'export_failed', 'preempted')
            or not isinstance(operation, dict) or not isinstance(identity, dict)
            or not isinstance(model, str) or not model or identity.get('model_id', model) != model
            or identity.get('operation_id', operation_id) != operation_id
            or status.get('operation_id') != operation_id or operation.get('operation_id') != operation_id
            or status.get('status') != state.upper() or operation.get('status') != state
            or any(row.get('id', operation_id) != operation_id for row in (status, operation))):
        raise ValueError('Failure status does not match the retained operation receipt.')
    error = status.get('error') or {}
    if not isinstance(error, dict):
        raise ValueError('Invalid retained failure details.')
    rows = [('Model', model), ('Recorded state', state),
            ('Failed stage', error.get('stage_id')), ('Error code', error.get('code'))]
    message = error.get('message')
    if any(value is not None and not isinstance(value, str) for _, value in rows) or (
            message is not None and (not isinstance(message, str) or len(message) > 8192)):
        raise ValueError('Invalid retained failure details.')
    message = message or 'not retained'
    fence = '`' * max(3, max((len(part) for part in re.findall(r'`+', message)), default=0) + 1)
    text = ['### Scientific operation did not succeed', '', f'Operation: `{operation_id}`.', '',
            '| Recorded field | Value |', '|---|---|']
    text += [f'| {label} | {cell(value) if value is not None else "not retained"} |' for label, value in rows]
    text += ['', 'Recorded platform message:', fence + 'text', message, fence, '',
             'Root cause: not established by this status. Missing details mean not retained, not zero. '
             'A different successful workflow does not establish the cause of this failure.', '',
             f'[Retained status]({link(folder / "status.json", root)})',
             f'[Operation receipt]({link(receipt_path, root)})']
    return '\n'.join(text)


def publication_card(folder, root):
    manifest = json.loads((folder / 'manifest.json').read_text())
    operation = manifest.get('operation_id', '')
    files = manifest.get('files')
    if (manifest.get('schema') != 'scientific-ai/customer-publication/v1'
            or not isinstance(operation, str)
            or not re.fullmatch(r'op-[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?', operation)
            or not isinstance(files, list) or not files):
        raise ValueError('Missing operation publication identity or files.')
    text = ['### Published operation files', '', f'Operation: `{operation}`.', '',
            '| File | Bytes | SHA-256 |', '|---|---:|---|']
    seen = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError('Invalid publication file metadata.')
        name, sha, size = entry.get('path'), entry.get('sha256'), entry.get('size_bytes')
        if (not isinstance(name, str) or not name or Path(name).is_absolute()
                or not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha)
                or type(size) is not int or size < 0):
            raise ValueError('Invalid publication file metadata.')
        path = within(name, folder)
        if path in seen:
            raise ValueError('Duplicate publication file.')
        seen.add(path)
        verify(path, entry)
        label = cell(name).replace('[', '\\[').replace(']', '\\]')
        text.append(f'| [{label}]({link(path, root)}) | {size} | `{sha}` |')
    text += ['', 'Every listed file matches its saved publication size and full SHA-256. '
             'This verifies delivered bytes, not the scientific validity of their contents.']
    return '\n'.join(text)


def verified_md_inputs(folder, root):
    """Resolve native results once, sharing receipt/hash checks with reporters."""
    # Read-only recovery deliberately keeps a separate receipt; it must not
    # overwrite an earlier submission receipt just to render a result card.
    receipt_path = folder / 'receipt.json'
    if not receipt_path.exists():
        receipt_path = folder / 'recovery-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('state') != 'verified' or not receipt.get('operation_id'):
        raise ValueError('MD operation does not have a verified completed-result receipt.')
    manifest = json.loads((folder / 'native-files.json').read_text())
    if manifest.get('schema') != 'scientific-ai/native-md-files/v1' or not manifest.get('results'):
        raise ValueError('Native MD files are not materialized. Recover the existing operation first.')
    artifacts = receipt.get('verified_artifacts', [])
    documents = []
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
        documents.append({'engine': engine, 'result': result, 'files': files,
                          'native_root': native_root, 'source': {**source, 'path': str(source_path)}})
    return receipt_path, receipt, documents


def md_card(folder, root):
    receipt_path, receipt, documents = verified_md_inputs(folder, root)
    texts = []
    for document in documents:
        engine, result, files = document['engine'], document['result'], document['files']
        native_root = document['native_root']
        text = [f'### {cell(engine.upper())}: completed engine operation', '',
                f"Operation: `{receipt['operation_id']}`.",
                f"Completed steps: {', '.join(cell(v) for v in result['completed_steps'])}.",
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
                 f'[Publication receipt]({link(receipt_path, root)}) · '
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
        handler = {'mmcif': mmcif_card, 'openff': openff_card,
                   'native-md': md_card, 'file': file_card,
                   'publication': publication_card, 'failure': failure_card}.get(item['kind'])
        if handler is None:
            raise ValueError('Unsupported verified result kind.')
        cards.append(handler(within(item['path'], root), root))
    return {'schema': 'scientific-verified-delivery/v1', 'status': 'completed',
            'report_markdown': '\n\n---\n\n'.join(cards), 'result_count': len(cards),
            'inference_submitted': False}
