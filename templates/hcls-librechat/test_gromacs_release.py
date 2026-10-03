"""Offline candidate composition/provenance tests; not image or live acceptance."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
BASE = 'cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:873be148673dec6dc191ba30d2933c01acee4622fd3fa14888388378539f13d3'
spec = importlib.util.spec_from_file_location(
    'gromacs_release_provenance', ROOT / 'scripts/write-gromacs-release-provenance.py')
provenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provenance)


def overlay(tmp_path):
    files = {
        'app/skill/manifest.json': '{"version":"2026.10.03.3"}\n',
        'app/skill/files.sha256.json': '{}\n',
        'app/skill/gromacs/references/mpi-contract-source.json': '{"source_commit":"' + 'c' * 40 + '"}\n',
        'opt/bionemo/invoke-scientific-batch.py': '# helper test fixture\n',
        'opt/bionemo/native_md_artifacts.py': '# bridge test fixture\n',
        'opt/bionemo/scientific_verified_results.py': '# delivery test fixture\n',
        'opt/bionemo/report-native-md.py': '# deterministic reporter test fixture\n',
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return tmp_path


def test_provenance_binds_actual_helper_bridge_bundle_and_base(tmp_path):
    stage = overlay(tmp_path)
    target = provenance.record(stage, 'a' * 40, BASE)
    value = json.loads(target.read_text())
    assert value['source_revision'] == 'a' * 40
    assert value['base_image'] == BASE
    assert value['skills_version'] == '2026.10.03.3'
    assert len(value['files_sha256']) == 6
    for name, expected in value['files_sha256'].items():
        assert expected == hashlib.sha256((stage / name).read_bytes()).hexdigest()
    assert value['backend_contract']['source_commit'] == 'c' * 40
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        provenance.record(stage, 'b' * 40, BASE)
    assert target.read_bytes() == before


@pytest.mark.parametrize('revision,base', [
    ('unknown', BASE), ('a' * 39, BASE), ('a' * 40, 'registry/image:latest'),
])
def test_provenance_requires_real_revision_and_immutable_base(tmp_path, revision, base):
    with pytest.raises(ValueError):
        provenance.record(tmp_path, revision, base)
    assert not list(tmp_path.iterdir())


def test_candidate_preserves_current_workbench_without_dependency_rebuild():
    source = (ROOT / 'Dockerfile.gromacs-mpi-release').read_text()
    assembly = source.split('FROM ${WORKBENCH_BASE}', 2)[1]
    final_stage = source.rsplit('FROM ${WORKBENCH_BASE}', 1)[1]
    assert f'ARG WORKBENCH_BASE={BASE}' in source
    assert 'native_md_artifacts.py /release/opt/bionemo/native_md_artifacts.py' in source
    assert 'scientific_verified_results.py /release/opt/bionemo/scientific_verified_results.py' in source
    assert 'native_md_report.py /release/opt/bionemo/report-native-md.py' in source
    assert 'test-skills-installed.cjs' in source
    assert 'COPY ' not in assembly
    assert assembly.count('\nRUN ') == 1
    assert 'source=skills/scientific-ai,target=/tmp/source-skills,readonly' in assembly
    assert final_stage.count('COPY ') == 1
    for forbidden in ('RUN ', '\nENTRYPOINT ', '\nCMD ', '\nENV '):
        assert forbidden not in final_stage
    assert 'micromamba create' not in source
    assert 'pip install' not in source
    manifest = json.loads((ROOT.parents[1] / 'skills/scientific-ai/manifest.json').read_text())
    assert f'ai.nebius.scientific.skills.version="{manifest["version"]}"' in source
