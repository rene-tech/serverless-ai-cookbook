"""Publish measured MD reports and optional final coordinates, without inference."""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import shlex
import sys
import tempfile
from html import escape

# The saved-study python-script phase freezes a copy in private scratch. Reuse
# the installed verifier/viewer without modifying existing worker processes.
if not (Path(__file__).parent / 'scientific_verified_results.py').is_file():
    sys.path.insert(0, '/opt/bionemo')
from scientific_verified_results import verified_md_inputs, verify, within


class PreviewUnavailable(ValueError):
    """Optional presentation cannot be produced; verified measurements remain useful."""


def bounded_coordinates(text, fmt, budget):
    """Keep small originals; derive an explicitly labelled subset for browser use.

    Biopython handles mmCIF quoting/loops and writes selected atom-site rows,
    preserving their recorded coordinate strings and chain/residue identities.
    The size bound applies only to this derived view, never to native inputs.
    """
    if len(text.encode()) <= budget:
        return text, 'all atoms', {}
    from Bio.PDB import MMCIFIO
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict
    from Bio.PDB.Polypeptide import is_aa, is_nucleic
    try:
        if fmt == 'cif':
            parsed = MMCIF2Dict(io.StringIO(text))
            columns = {key: value for key, value in parsed.items() if key.startswith('_atom_site.')}
            count = len(columns['_atom_site.id'])
            if not count or any(not isinstance(v, list) or len(v) != count for v in columns.values()):
                raise ValueError('Inconsistent atom-site rows')
            residues = columns['_atom_site.label_comp_id']
            names = columns['_atom_site.label_atom_id']
            elements = columns['_atom_site.type_symbol']
            for axis in ('x', 'y', 'z'):
                if len(columns['_atom_site.Cartn_' + axis]) != count:
                    raise ValueError('Missing atom coordinates')

            def encode(indices):
                writer = MMCIFIO()
                writer.set_dict({'data_': 'derived_preview', **{key: [values[i] for i in indices] for key, values in columns.items()}})
                stream = io.StringIO()
                writer.save(stream)
                return stream.getvalue()
        else:
            lines = [line for line in text.splitlines() if line.startswith(('ATOM  ', 'HETATM'))]
            count = len(lines)
            residues = [line[17:20].strip() for line in lines]
            names = [line[12:16].strip() for line in lines]
            elements = [line[76:78].strip() or line[12:16].strip(' 0123456789')[:1] for line in lines]

            def encode(indices):
                return '\n'.join(lines[i] for i in indices) + '\nEND\n'

        protein = [is_aa(name, standard=False) for name in residues]
        nucleic = [is_nucleic(f'{name:<3}', standard=False) for name in residues]
        polymer = [i for i in range(count) if protein[i] or nucleic[i]]
        heavy = [i for i in (polymer or range(count)) if elements[i].upper() not in {'H', 'D'}]
        backbone = [i for i in heavy if (protein[i] and names[i] == 'CA') or (nucleic[i] and names[i] == 'P')]
        candidates = [(polymer, 'protein/nucleic-acid atoms only'),
                      (heavy, 'protein/nucleic-acid heavy atoms only' if polymer else 'heavy atoms only'),
                      (backbone, 'protein CA / nucleic-acid P backbone positions only')]
        for indices, label in candidates:
            if indices:
                rendered = encode(indices)
                if len(rendered.encode()) <= budget:
                    return rendered, label + '; complete coordinates remain in native outputs', {
                        'source_atom_count': count, 'preview_atom_count': len(indices), 'derived': True}
        indices = backbone or heavy or list(range(count))
        stride = 2
        while indices:
            selected = indices[::stride]
            rendered = encode(selected)
            if len(rendered.encode()) <= budget:
                label = 'sampled backbone positions' if backbone else 'sampled atom positions'
                return rendered, f'{label} only (every {stride}th selected atom); complete coordinates remain in native outputs', {
                    'source_atom_count': count, 'preview_atom_count': len(selected), 'derived': True, 'stride': stride}
            if len(selected) == 1:
                break
            stride *= 2
    except (ValueError, KeyError, IndexError, TypeError, StopIteration) as exc:
        raise PreviewUnavailable('Coordinate parsing could not produce a bounded derived preview.') from exc
    raise PreviewUnavailable('A bounded derived preview could not be produced; complete native coordinates are unchanged.')


def publish_preview(rendered, output):
    for name, value in rendered.items():
        target = output / name
        if target.exists() and target.read_bytes() != value.encode():
            raise ValueError('Existing preview differs; choose a new output directory: ' + name)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in rendered.items():
        target = output / name
        if not target.exists():
            with target.open('x') as stream:
                stream.write(value)
    return list(rendered)


def unavailable_preview(reason, output):
    document = ('<!doctype html><html><head><meta charset="utf-8"><title>Structure preview unavailable</title></head>'
                '<body><section style="padding:20px;font:16px/1.5 system-ui"><h2>Structure preview unavailable</h2>'
                f'<p>{escape(str(reason))}</p><p>Verified report measurements remain available. '
                'Retained native artifacts are unchanged; use their original files for local visualization.</p></section></body></html>')
    return publish_preview({'md-structure-preview.html': document,
        'md-structure-preview.json': json.dumps({'schema': 'scientific-md-preview/v1', 'status': 'unavailable',
            'reason': str(reason), 'frames': [], 'scientific_validity_claim': False, 'inference_submitted': False}, indent=2) + '\n'}, output)


def render_report(folder, output, workspace, repeats, structure_html=None):
    """Render in private phase scratch; only the study publisher issues links.

    Reuse the native verifier, measurements and report format. Its standalone
    write_report() is workspace-only and cannot publish scratch paths.
    """
    from native_md_report import collect, FIELDS, markdown, html_report
    report = collect(folder, workspace, repeats)
    if not report['complete']:
        raise ValueError('Native timing evidence is incomplete: ' + '; '.join(report['gaps']))
    csv_buffer = io.StringIO(newline='')
    writer = csv.DictWriter(csv_buffer, fieldnames=FIELDS)
    writer.writeheader()
    for row in report['timing_rows']:
        writer.writerow({**row, 'command': shlex.join(row['command'])})
    rendered = {'native-timing-report.json': json.dumps(report, indent=2) + '\n',
                'native-timings.csv': csv_buffer.getvalue(),
                'native-timing-report.md': markdown(report, workspace),
                'native-md-report.html': html_report(report, workspace, structure_html)}
    output.mkdir(parents=True, exist_ok=True)
    for name, value in rendered.items():
        target = output / name
        if target.exists() and target.read_bytes() != value.encode():
            raise ValueError('Existing report differs; choose a new output directory: ' + name)
    for name, value in rendered.items():
        target = output / name
        if not target.exists():
            with target.open('x') as stream:
                stream.write(value)
    return list(rendered)


def argument(command, option, default):
    if option not in command:
        return default
    if command.index(option) + 1 == len(command):
        raise ValueError('Incomplete recorded command option: ' + option)
    return command[command.index(option) + 1]


def render_preview(folder, output, workspace):
    _, _, documents = verified_md_inputs(folder, workspace)
    assets = Path(os.environ.get('BIONEMO_ASSET_ROOT', '/opt/bionemo'))
    spec = importlib.util.spec_from_file_location('md_result_viewer', assets / 'viewer-mcp.py')
    viewer = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(viewer)
    except (ImportError, OSError) as exc:
        raise PreviewUnavailable('The optional coordinate viewer is unavailable.') from exc
    entries, provenance, rendered = [], [], {}
    if not 1 <= len(documents) <= 4:
        raise PreviewUnavailable('Inline final-coordinate preview supports one to four native jobs; measurements remain available for all jobs.')
    for document in documents:
        engine = document['engine']
        if engine not in {'gromacs', 'openmm'}:
            raise PreviewUnavailable('Final-coordinate preview supports GROMACS and OpenMM; other engines retain their timing reports.')
        result = document['result']
        commands = [c for c in result.get('commands', []) if
                    (c.get('kind') in {'equilibrate', 'production'} if engine == 'openmm' else 'mdrun' in c.get('command', []))
                    and c.get('step_id') in result.get('completed_steps', []) and c.get('exit_code') == 0]
        if not commands:
            raise PreviewUnavailable('No completed dynamics command for a final-coordinate preview.')
        last = commands[-1]
        if engine == 'openmm':
            if last.get('validation', {}).get('structure_file') != 'structure.cif':
                raise PreviewUnavailable('OpenMM has no declared final mmCIF coordinate artifact.')
            name = str(PurePosixPath('openmm-output', last['step_id'], f"segment-{last['segment']:06d}", 'structure.cif'))
        else:
            command = last['command']
            default = argument(command, '-deffnm', 'confout') + '.gro'
            name = str(PurePosixPath(last.get('directory', '.')) / argument(command, '-c', default))
        path, record = document['files'].get(name, (None, None))
        if path is None:
            raise PreviewUnavailable('Final coordinate is absent from the verified native manifest: ' + name)
        verify(path, record)
        if engine == 'openmm':
            text, fmt, method = path.read_text(), 'cif', 'Verified OpenMM mmCIF; visualization only'
            if not text.lstrip().startswith('data_') or '_atom_site.' not in text:
                raise PreviewUnavailable('Declared OpenMM final structure is not mmCIF.')
        else:
            with tempfile.TemporaryDirectory(prefix='scientific-md-preview-') as directory:
                pdb = Path(directory) / 'final.pdb'
                try:
                    subprocess.run(['gmx', 'editconf', '-f', str(path), '-o', str(pdb)],
                                   capture_output=True, check=True, timeout=60)
                    text = pdb.read_text()
                except (OSError, subprocess.SubprocessError) as exc:
                    raise PreviewUnavailable('The optional final-coordinate conversion could not complete.') from exc
            fmt, method = 'pdb', 'GROMACS editconf; visualization only'
        budget = 3 * 1024**2 // len(documents)
        text, selection, subset = bounded_coordinates(text, fmt, budget)
        if fmt == 'pdb' and not any(line.startswith(('ATOM  ', 'HETATM')) for line in text.splitlines()):
            raise PreviewUnavailable('No coordinate atoms are available for a preview.')
        filename = f'final-structure-{len(entries) + 1}.{fmt}'
        rendered[filename] = text
        entries.append({'text': text, 'format': fmt, 'label': f"{result['job_id']} · final frame · {selection}"})
        provenance.append({'job_id': result['job_id'], 'source_path': name, 'source_sha256': record['sha256'],
                           'preview_file': filename, 'preview_sha256': hashlib.sha256(text.encode()).hexdigest(),
                           'selection': selection, 'method': method, 'byte_budget': budget, **subset})
    first = entries[0]
    try:
        rendered['md-structure-preview.html'] = viewer.viewer_html(first['text'], first['format'],
            'MD final coordinates · not a trajectory animation', entries)
    except Exception as exc:
        raise PreviewUnavailable('The optional coordinate viewer could not render the derived preview.') from exc
    if '<body>' not in rendered['md-structure-preview.html'] or '</head>' not in rendered['md-structure-preview.html']:
        raise PreviewUnavailable('The optional coordinate viewer returned an incomplete document.')
    if len(rendered['md-structure-preview.html'].encode()) > 8 * 1024**2:
        raise PreviewUnavailable('Preview exceeds the inline viewer limit; native coordinates are preserved.')
    rendered['md-structure-preview.json'] = json.dumps({'schema': 'scientific-md-preview/v1',
        'status': 'available', 'frames': provenance, 'scientific_validity_claim': False, 'inference_submitted': False}, indent=2) + '\n'
    return publish_preview(rendered, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True,
                        help='Saved-study python-script input-bindings.json with native_manifest.')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    bindings = json.loads(args.inputs.read_text())
    if (bindings.get('schema') != 'scientific-python-bindings/v1'
            or set(bindings.get('inputs', {})) != {'native_manifest'}
            or not isinstance(bindings.get('parameters'), dict)
            or set(bindings['parameters']) - {'expected_repeats', 'structure_preview'}):
        raise ValueError('Expected native_manifest plus optional expected_repeats/structure_preview.')
    options = bindings['parameters']
    repeats = options.get('expected_repeats')
    if repeats is not None and (type(repeats) is not int or repeats < 1):
        raise ValueError('expected_repeats must be a positive integer.')
    if type(options.get('structure_preview', True)) is not bool:
        raise ValueError('structure_preview must be boolean.')
    workspace = Path(os.environ.get('WORKSPACE', '/workspace')).resolve()
    manifest = within(Path(bindings['inputs']['native_manifest']), workspace)
    if manifest.name != 'native-files.json':
        raise ValueError('Expected exact native-files.json, not a platform result envelope.')
    files, structure_html = [], None
    if options.get('structure_preview', True):
        try:
            files = render_preview(manifest.parent, args.output_dir, workspace)
        except PreviewUnavailable as exc:
            files = unavailable_preview(exc, args.output_dir)
        structure_html = (args.output_dir / 'md-structure-preview.html').read_text()
    files += render_report(manifest.parent, args.output_dir, workspace, repeats, structure_html)
    report = json.loads((args.output_dir / 'native-timing-report.json').read_text())
    print(json.dumps({'files': files, 'operation_id': report['operation_id'],
                     'report_file': 'native-md-report.html', 'inference_submitted': False}))


if __name__ == '__main__':
    main()
