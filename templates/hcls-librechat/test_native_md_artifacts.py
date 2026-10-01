"""Native names are bound to actual bytes, including shuffled/aliased files."""
import hashlib
import json
from pathlib import Path

import pytest

from native_md_artifacts import materialize_native_outputs, workspace_url


def artifact(root, name, data, semantic):
    path = root / name
    path.write_bytes(data)
    return {'artifact_id': name, 'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
            'size_bytes': len(data), 'semantic_type': semantic}


def fixture(tmp_path, engine='gromacs'):
    a = artifact(tmp_path, 'output-01.artifact', b'binary trajectory', f'{engine}-file/v1')
    b = artifact(tmp_path, 'output-02.artifact', b'text energy', f'{engine}-file/v1')
    # The native result order intentionally differs from transport order.
    files = [{'path': name, 'sha256': ref['sha256'], 'size_bytes': ref['size_bytes']}
             for name, ref in [('production-energy.xvg', b), ('trajectory.xtc', a), ('copy/alias.xtc', a)]]
    result = {'schema': f'fs2-serve.nebius.ai/{engine}-workflow-result/v1',
              'status': 'succeeded', 'files': files}
    r = artifact(tmp_path, 'output-00.artifact', json.dumps(result).encode(), f'{engine}-workflow-result/v1')
    return [r, a, b], result


@pytest.mark.parametrize('engine', ['gromacs', 'namd', 'amber', 'lammps'])
def test_shuffled_native_files_and_equal_byte_aliases(tmp_path, engine):
    artifacts, result = fixture(tmp_path, engine)
    copied = materialize_native_outputs(tmp_path, artifacts)['native_outputs']
    assert copied['file_count'] == 3
    assert (tmp_path / 'native/result-00/production-energy.xvg').read_bytes() == b'text energy'
    assert (tmp_path / 'native/result-00/trajectory.xtc').read_bytes() == b'binary trajectory'
    assert (tmp_path / 'native/result-00/copy/alias.xtc').read_bytes() == b'binary trajectory'
    assert materialize_native_outputs(tmp_path, artifacts)['native_outputs']['file_count'] == 3
    manifest = json.loads((tmp_path / 'native-files.json').read_text())
    assert [a['native_path'] for a in manifest['results'][0]['files']] == [f['path'] for f in result['files']]
    (tmp_path / 'native/result-00/trajectory.xtc').write_bytes(b'edited native file')
    assert Path(artifacts[1]['path']).read_bytes() == b'binary trajectory'


def test_non_md_outputs_are_not_reinterpreted(tmp_path):
    assert materialize_native_outputs(tmp_path, [{'semantic_type': 'protein-structure/v1'}]) == {}
    assert not list(tmp_path.iterdir())


def test_changed_raw_bytes_do_not_publish_names(tmp_path):
    artifacts, _ = fixture(tmp_path)
    Path(artifacts[2]['path']).write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='differ'):
        materialize_native_outputs(tmp_path, artifacts)
    assert not (tmp_path / 'native').exists()


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'bad\\name', '.', 'trajectory.xtc'])
def test_invalid_or_duplicate_names_fail_before_publication(tmp_path, name):
    artifacts, result = fixture(tmp_path)
    result['files'][0]['path'] = name
    artifacts[0] = artifact(tmp_path, 'output-00.artifact', json.dumps(result).encode(), 'gromacs-workflow-result/v1')
    with pytest.raises(ValueError, match='filename'):
        materialize_native_outputs(tmp_path, artifacts)
    assert not (tmp_path / 'native').exists()


def test_absent_exact_hash_is_not_replaced_by_same_position(tmp_path):
    artifacts, result = fixture(tmp_path)
    result['files'][0]['sha256'] = 'a' * 64
    artifacts[0] = artifact(tmp_path, 'output-00.artifact', json.dumps(result).encode(), 'gromacs-workflow-result/v1')
    with pytest.raises(ValueError, match='no matching'):
        materialize_native_outputs(tmp_path, artifacts)
    assert not (tmp_path / 'native').exists()


def test_existing_named_file_conflict_preserves_both_versions(tmp_path):
    artifacts, _ = fixture(tmp_path)
    target = tmp_path / 'native/result-00/production-energy.xvg'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'customer file')
    with pytest.raises(RuntimeError, match='differ'):
        materialize_native_outputs(tmp_path, artifacts)
    assert target.read_bytes() == b'customer file'
    assert Path(artifacts[2]['path']).read_bytes() == b'text energy'


def test_links_use_the_existing_workspace_query_not_base64():
    from urllib.parse import parse_qs, urlparse
    value = workspace_url(Path('/workspace/study A/native/energy.xvg'))
    assert parse_qs(urlparse(value).query) == {'tab': ['workspace'],
        'path': ['study A/native'], 'file': ['study A/native/energy.xvg']}
    assert workspace_url(Path('/tmp/local-file')) is None
