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

# The saved-study python-script phase freezes a copy in private scratch. Reuse
# the installed verifier/viewer without modifying existing worker processes.
if not (Path(__file__).parent / 'scientific_verified_results.py').is_file():
    sys.path.insert(0, '/opt/bionemo')
from scientific_verified_results import verified_md_inputs, verify, within


def render_report(folder, output, workspace, repeats):
    """Render in private phase scratch; only the study publisher issues links.

    Reuse the native verifier, measurements and report format. Its standalone
    write_report() is workspace-only and cannot publish scratch paths.
    """
    from native_md_report import collect, FIELDS, markdown
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
                'native-timing-report.md': markdown(report, workspace)}
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
    spec.loader.exec_module(viewer)
    entries, provenance, rendered = [], [], {}
    if not 1 <= len(documents) <= 4:
        raise ValueError('Inline final-coordinate preview supports one to four native jobs.')
    for document in documents:
        if document['engine'] != 'gromacs':
            raise ValueError('Final-coordinate preview currently supports GROMACS; other engines retain their timing reports.')
        result = document['result']
        commands = [c for c in result.get('commands', []) if 'mdrun' in c.get('command', [])
                    and c.get('step_id') in result.get('completed_steps', []) and c.get('exit_code') == 0]
        if not commands:
            raise ValueError('No completed GROMACS dynamics command for a final-coordinate preview.')
        last = commands[-1]
        command = last['command']
        default = argument(command, '-deffnm', 'confout') + '.gro'
        name = str(PurePosixPath(last.get('directory', '.')) / argument(command, '-c', default))
        path, record = document['files'].get(name, (None, None))
        if path is None:
            raise ValueError('Final coordinate is absent from the verified native manifest: ' + name)
        verify(path, record)
        with tempfile.TemporaryDirectory(prefix='scientific-md-preview-') as directory:
            pdb = Path(directory) / 'final.pdb'
            subprocess.run(['gmx', 'editconf', '-f', str(path), '-o', str(pdb)],
                           capture_output=True, check=True, timeout=60)
            text = pdb.read_text()
        selection = 'all atoms'
        budget = 3 * 1024**2 // len(documents)
        if len(text.encode()) > budget:
            from Bio.PDB.Polypeptide import is_aa
            text = '\n'.join(line for line in text.splitlines()
                if line.startswith(('ATOM  ', 'HETATM')) and is_aa(line[17:20], standard=False)) + '\nEND\n'
            selection = 'protein atoms only; complete coordinates remain in the native outputs'
        if not any(line.startswith(('ATOM  ', 'HETATM')) for line in text.splitlines()) or len(text.encode()) > budget:
            raise ValueError('No bounded final-coordinate preview; retain full native coordinates for local visualization.')
        filename = f'final-structure-{len(entries) + 1}.pdb'
        rendered[filename] = text
        entries.append({'text': text, 'format': 'pdb', 'label': f"{result['job_id']} · final frame · {selection}"})
        provenance.append({'job_id': result['job_id'], 'source_path': name, 'source_sha256': record['sha256'],
                           'preview_file': filename, 'preview_sha256': hashlib.sha256(text.encode()).hexdigest(),
                           'selection': selection, 'method': 'GROMACS editconf; visualization only'})
    first = entries[0]
    rendered['md-structure-preview.html'] = viewer.viewer_html(first['text'], 'pdb',
        'GROMACS final coordinates · not a trajectory animation', entries)
    if len(rendered['md-structure-preview.html'].encode()) > 8 * 1024**2:
        raise ValueError('Preview exceeds the inline viewer limit; native coordinates are preserved.')
    rendered['md-structure-preview.json'] = json.dumps({'schema': 'scientific-md-preview/v1',
        'frames': provenance, 'scientific_validity_claim': False, 'inference_submitted': False}, indent=2) + '\n'
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
    files = render_report(manifest.parent, args.output_dir, workspace, repeats)
    if options.get('structure_preview', True):
        files += render_preview(manifest.parent, args.output_dir, workspace)
    print(json.dumps({'files': files, 'inference_submitted': False}))


if __name__ == '__main__':
    main()
