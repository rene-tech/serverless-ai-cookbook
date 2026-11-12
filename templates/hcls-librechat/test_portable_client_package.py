"""The downloadable client is the existing transport, runnable outside the image."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

CLIENT = Path(__file__).parent
ROOT = CLIENT.parents[1]
spec = importlib.util.spec_from_file_location('client_package', CLIENT / 'scripts/package-scientific-client.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def test_package_is_reproducible_exact_source_and_runs_outside_checkout(tmp_path):
    first = packager.package(tmp_path / 'one')
    second = packager.package(tmp_path / 'two')
    assert first['sha256'] == second['sha256']
    with pytest.raises(FileExistsError):
        packager.package(tmp_path / 'one')
    with tarfile.open(first['archive']) as archive:
        archive.extractall(tmp_path / 'unpacked', filter='data')
    client = tmp_path / 'unpacked/scientific-ai-client'
    for name, source in packager.FILES.items():
        assert (client / name).read_bytes() == (ROOT / source).read_bytes()
    for line in (client / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((client / name).read_bytes()).hexdigest() == expected
    assert json.loads((client / 'source-files.json').read_text()) == first['source_files']
    # No /opt helper, repository import path, live endpoint or key is supplied.
    for script, options in [
        ('upload-artifact.py', []),
        ('invoke-native.py', []),
        ('invoke-scientific-batch.py', []),
        ('invoke-scientific-batch.py', ['--recover-operation-id', 'op-example']),
        ('invoke-scientific-batch.py', ['--observe-output', 'unused']),
        ('invoke-scientific-campaign.py', []),
        ('invoke-scientific-campaign.py', ['plan']),
        ('invoke-scientific-campaign.py', ['observe']),
    ]:
        result = subprocess.run([sys.executable, str(client / script), *options, '--help'],
                                cwd=tmp_path, capture_output=True, text=True,
                                env={'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path)}, check=True)
        assert 'usage:' in result.stdout and not result.stderr


def test_client_dependencies_and_skill_requirements_are_explicit():
    docker = (CLIENT / 'Dockerfile').read_text()
    for line in (CLIENT / 'scientific-client-requirements.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            assert line in docker
    manifest = json.loads((ROOT / 'skills/scientific-ai/manifest.json').read_text())
    assert set(manifest['client_requirements']) == set(manifest['skills'])
    assert set(manifest['client_requirements'].values()) <= set(manifest['client_requirement_types'])
    assert manifest['client_requirements']['scientific-batch'] == 'hosted-mcp-with-workbench-sections'
    assert manifest['client_requirements']['mindeval-workflows'] == 'workbench-runtime'
    assert manifest['client_requirements']['clawbio-catalog'] == 'workbench-runtime'
