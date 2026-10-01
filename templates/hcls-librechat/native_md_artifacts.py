"""Materialize native MD filenames from verified hashes, never list order.

Uses the existing artifact publisher. No model calls, transport, conversion or
scientific parameter changes occur here; raw artifacts remain untouched.
"""
import json
from pathlib import Path, PurePosixPath
import shutil
from urllib.parse import urlencode

from scientific_receipts import staged_output, save, verify_file

RESULT_TYPES = {f'{engine}-workflow-result/v1': engine
                for engine in ('gromacs', 'namd', 'amber', 'lammps')}


def workspace_url(path: Path, *, directory=False):
    try:
        relative = path.relative_to('/workspace')
    except ValueError:
        return None  # An external/local client is not a hosted workspace.
    query = {'tab': 'workspace', 'path': str(relative if directory else relative.parent)}
    if not directory:
        query['file'] = str(relative)
    return '/demos?' + urlencode(query)


def materialize_native_outputs(output: Path, artifacts: list[dict]) -> dict:
    results = [a for a in artifacts if a.get('semantic_type') in RESULT_TYPES]
    if not results:
        return {}
    by_hash = {}
    for artifact in artifacts:
        by_hash.setdefault((artifact['sha256'], artifact['size_bytes']), artifact)
    plans, documents, directories = [], [], []
    for index, artifact in enumerate(results):
        source = Path(artifact['path'])
        verify_file(source, artifact)
        result = json.loads(source.read_text())
        engine = RESULT_TYPES[artifact['semantic_type']]
        if (result.get('schema') != f'fs2-serve.nebius.ai/{engine}-workflow-result/v1'
                or result.get('status') != 'succeeded' or not isinstance(result.get('files'), list)
                or not result['files']):
            raise ValueError('Native result does not declare a successful, nonempty file inventory.')
        folder = Path(output) / 'native' / f'result-{index:02d}'
        document = {'engine': engine, 'source_result_sha256': artifact['sha256'], 'files': []}
        seen = set()
        for entry in result['files']:
            raw_name = entry.get('path')
            if not isinstance(raw_name, str) or not raw_name or '\\' in raw_name:
                raise ValueError('Native result filename is not a relative POSIX path.')
            name = PurePosixPath(raw_name)
            if name.is_absolute() or '..' in name.parts or str(name) in {'.', ''} or str(name) in seen:
                raise ValueError('Native result filename escapes its directory or is duplicated.')
            seen.add(str(name))
            reference = by_hash.get((entry.get('sha256'), entry.get('size_bytes')))
            if reference is None:
                raise ValueError('Native file has no matching hash-verified artifact; preserve the raw result.')
            source = Path(reference['path'])
            verify_file(source, reference)
            target = folder / str(name)
            if not target.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Native output path leaves its result directory.')
            plans.append((source, target, entry, reference, document))
        documents.append(document)
        directories.append({'path': str(folder), 'workspace_url': workspace_url(folder, directory=True)})
    # Validate every mapping before publishing any named files. Equal bytes may
    # legitimately have multiple native names; hashes, not positions, identify them.
    for source, target, entry, reference, document in plans:
        # Copy to seekable scratch before the publisher: a POSIX hard link to
        # the raw artifact would let later native-file edits alter provenance.
        with staged_output(target) as staged:
            shutil.copyfile(source, staged.path)
        published = staged.receipt
        verify_file(target, entry)
        document['files'].append({**published, 'native_path': entry['path'],
            'artifact_id': reference['artifact_id'], 'workspace_url': workspace_url(target)})
    manifest = Path(output) / 'native-files.json'
    save(manifest, {'schema': 'scientific-ai/native-md-files/v1', 'results': documents,
                    'claim': 'Byte-identical native files; not scientific validity or convergence.'})
    return {'native_outputs': {'manifest_file': str(manifest), 'manifest_url': workspace_url(manifest),
            'file_count': len(plans), 'directories': directories}}
