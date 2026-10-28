import asyncio
import copy
import io
import json
from pathlib import Path
import tarfile
from unittest.mock import AsyncMock

import nibabel as nib
import numpy as np
import pytest

import scientific_app as app
import scientific_preview as preview
import scientific_study as study
from scientific_receipts import save


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_STUDY_ROOT', str(tmp_path / 'state'))
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER', 'fixture-owner')
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://fixture.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'fixture-key')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    schema = {'type': 'object', 'properties': {
        'operation': {'enum': ['simulate']}, 'service_class': {'enum': ['customer-batch']},
        'parameters': {'type': 'object', 'properties': {'episodes': {'type': 'integer', 'minimum': 1}}, 'required': ['episodes']}}}
    discovery = {'contracts': [{'protocol': 'scientific-batch-v1', 'tool_name': 'submit_isaac_healthcare', 'input_schema': schema}],
        'input_artifact_contract': {'entries': [{'name': 'scenarios', 'media_type': 'application/json',
            'semantic_type': 'isaac-healthcare-scenarios/v1', 'compression': 'none', 'required': True}],
            'scenarios_schema': {'type': 'object', 'required': ['scenarios'], 'properties': {
                'scenarios': {'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'required': ['name'], 'properties': {'name': {'type': 'string'}}}}}}}}
    monkeypatch.setattr(app, 'discover', AsyncMock(return_value=discovery))
    source = tmp_path / 'scenarios.json'
    source.write_text('{"scenarios":[{"name":"retained"}]}')
    body = {'request_id': '12345678-1234-1234-1234-123456789abc', 'source': str(source), 'operation': 'simulate',
        'service_class': 'customer-batch', 'entry_name': 'scenarios', 'compression': 'none', 'parameters': {'episodes': 1}}
    return tmp_path, body, discovery


def call(action, body, model='isaac-healthcare'):
    return asyncio.run(app.handle(action, model, body))


def test_invalid_preflight_never_submits(setup, monkeypatch):
    _, body, _ = setup
    submitted = []
    monkeypatch.setattr(study, 'submit', lambda *args: submitted.append(args))
    body['parameters']['episodes'] = 0
    with pytest.raises(ValueError, match='episodes'):
        call('preflight', body)
    assert submitted == []
    assert call('draft', body)['draft'] is None


def test_saved_request_resume_and_changed_input(setup, monkeypatch):
    root, body, _ = setup
    checked = call('preflight', body)['draft']
    assert checked['parameters'] == body['parameters']
    with pytest.raises(ValueError, match='another App'):
        call('preflight', body, 'monai-spleen-ct')
    payload = {'request_id': body['request_id'], 'preflight_sha256': checked['preflight_sha256']}
    submissions = []
    original = study.submit
    def interrupted(plan, output):
        result = original(plan, output)
        submissions.append(result)
        raise ConnectionError('lost acknowledgement')
    monkeypatch.setattr(study, 'submit', interrupted)
    with pytest.raises(ConnectionError):
        call('submit', payload)
    saved = call('draft', payload)
    assert saved['intent'] is True
    assert saved['workflow']['operation_admission'] == 'not_admitted'
    assert saved['workflow']['state'] == 'queued'
    again = call('submit', payload)
    assert again['progress_url'] == saved['workflow']['progress_url']
    assert len(submissions) == 1
    with pytest.raises(ValueError, match='already has'):
        call('preflight', body)


def test_crash_before_study_binding_can_resume_same_identity(setup, monkeypatch):
    _, body, _ = setup
    draft = call('preflight', body)['draft']
    root = app.draft_directory(body['request_id'])
    save(root / 'submit-intent.json', {'preflight_sha256': draft['preflight_sha256']})
    result = call('submit', {**body, 'preflight_sha256': draft['preflight_sha256']})
    assert result['state'] == 'queued'
    assert len(study.list_studies()) == 1


def test_source_contract_and_owner_changes_refuse_admission(setup, monkeypatch):
    _, body, discovery = setup
    checked = call('preflight', body)['draft']
    payload = {**body, 'preflight_sha256': checked['preflight_sha256']}
    original = Path(body['source']).read_bytes()
    Path(body['source']).write_text('{}')
    with pytest.raises(ValueError, match='Input changed'):
        call('submit', payload)
    Path(body['source']).write_bytes(original)
    changed = copy.deepcopy(discovery); changed['runtime_revision'] = 'new'
    monkeypatch.setattr(app, 'discover', AsyncMock(return_value=changed))
    with pytest.raises(ValueError, match='contract changed'):
        call('submit', payload)
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'different-key')
    with pytest.raises(ValueError, match='owner/key changed'):
        call('draft', payload)
    assert not (app.draft_directory(body['request_id']) / 'submit-intent.json').exists()


def write_volume(path, values, affine=None):
    image = nib.Nifti1Image(values, np.eye(4) if affine is None else affine)
    image.header.set_xyzt_units('mm')
    nib.save(image, path)


def test_ct_preflight_and_overlay_geometry(setup):
    root, _, _ = setup
    ct, mask = root / 'ct.nii.gz', root / 'mask.nii.gz'
    write_volume(ct, np.zeros((16, 12, 4), dtype=np.float32))
    write_volume(mask, np.ones((16, 12, 4), dtype=np.uint8))
    assert app.check_source('monai-spleen-ct', ct, {}, {}, {})
    result = preview.ct({'path': str(ct), 'mask': str(mask), 'index': 1})
    assert result['shape'] == [16, 12, 4]
    assert result['image'].startswith('data:image/png;base64,')
    write_volume(mask, np.ones((16, 12, 4), dtype=np.uint8), np.diag([2, 1, 1, 1]))
    with pytest.raises(ValueError, match='Overlay refused'):
        preview.ct({'path': str(ct), 'mask': str(mask)})
    values = np.zeros((16, 12, 4), dtype=np.float32); values[1, 1, 1] = np.nan
    write_volume(ct, values)
    with pytest.raises(ValueError, match='non-finite'):
        app.check_source('monai-spleen-ct', ct, {}, {}, {})


def test_archive_paths_and_missing_video(setup):
    root, _, _ = setup
    source = root / 'input.tar'
    for name, message in [('video.mp4', 'video_file is absent'), ('../escape', 'ordinary relative')]:
        with tarfile.open(source, 'w') as archive:
            info = tarfile.TarInfo(name); info.size = 1
            archive.addfile(info, io.BytesIO(b'x'))
        with pytest.raises(ValueError, match=message):
            app.check_source('holoscan-endoscopy', source, {'video_file': 'missing.mp4'}, {}, {'media_type': 'application/x-tar'})


def test_episode_dynamic_camera_and_external_dataset_rejection(setup):
    h5py = pytest.importorskip('h5py')
    root, _, _ = setup
    path = root / 'demos.hdf5'
    with h5py.File(path, 'w') as file:
        demo = file.create_group('data/demo_7')
        demo.attrs.update(num_samples=3, success=False)
        demo['actions'] = np.zeros((3, 2))
        demo['obs/joint_pos'] = np.ones((3, 5))
        demo['obs/custom_camera'] = np.zeros((3, 8, 12, 3), dtype=np.uint8)
    result = preview.episode({'path': str(path), 'index': 2})
    assert result['cameras'] == ['custom_camera'] and result['task_success'] is False
    assert result['actions'] == [0, 0] and len(result['obs/joint_pos']) == 5
    with pytest.raises(ValueError, match='index between'):
        preview.episode({'path': str(path), 'index': 3})
    with h5py.File(path, 'a') as file:
        file['data/demo_7/obs/external'] = h5py.ExternalLink('/etc/passwd', '/secret')
    with pytest.raises(ValueError, match='without soft/external'):
        preview.episode({'path': str(path)})


def test_preview_bounds_and_workspace_escape(setup):
    root, _, _ = setup
    with pytest.raises(ValueError, match='mounted workspace'):
        preview.source_file('/etc/passwd')
    source = root / 'annotated.mp4'
    with source.open('wb') as file:
        file.truncate(33 * 1024 * 1024)
    with pytest.raises(ValueError, match='32 MiB'):
        preview.preview('holoscan-endoscopy', {'path': str(source)})
    with pytest.raises(ValueError, match='2048'):
        preview.png(np.zeros((2049, 2), dtype=np.uint8))


def test_interrupted_binding_before_receipt_is_recoverable(setup, monkeypatch):
    _, body, _ = setup
    checked = call('preflight', body)['draft']
    original = study.save
    def interrupted(path, value):
        if path.name == 'receipt.json':
            raise OSError('interrupted before receipt')
        return original(path, value)
    monkeypatch.setattr(study, 'save', interrupted)
    payload = {**body, 'preflight_sha256': checked['preflight_sha256']}
    with pytest.raises(OSError):
        call('submit', payload)
    assert call('draft', payload)['workflow'] is None
    monkeypatch.setattr(study, 'save', original)
    assert call('submit', payload)['state'] == 'queued'
    assert len(study.list_studies()) == 1


def test_video_header_preflight_reports_out_of_bounds_start(setup, monkeypatch):
    from types import SimpleNamespace
    root, _, _ = setup
    source = root / 'video.tar'
    with tarfile.open(source, 'w') as archive:
        info = tarfile.TarInfo('clip.mp4'); info.size = 3
        archive.addfile(info, io.BytesIO(b'raw'))
    monkeypatch.setattr(app.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=b'{"streams":[{"width":640,"height":480,"nb_frames":"20"}]}'))
    with pytest.raises(ValueError, match='outside the 20 declared'):
        app.check_source('holoscan-endoscopy', source, {'video_file': 'clip.mp4', 'start_frame': 20}, {}, {'media_type': 'application/x-tar'})
    assert 'header checked' in app.check_source('holoscan-endoscopy', source, {'video_file': 'clip.mp4'}, {}, {'media_type': 'application/x-tar'})[0]


def test_preflight_does_not_replace_a_concurrently_locked_request(setup):
    _, body, _ = setup
    checked = call('preflight', body)
    with app.receipt_lock(app.draft_directory(body['request_id'])):
        with pytest.raises(BlockingIOError):
            call('preflight', {**body, 'parameters': {'episodes': 2}})
    assert call('draft', body)['draft'] == checked['draft']


def test_form_dereferences_parameters_without_changing_validation_schema(setup):
    _, _, discovery = setup
    schema = discovery['contracts'][0]['input_schema']
    schema['$defs'] = {'parameters': schema['properties']['parameters']}
    schema['properties']['parameters'] = {'$ref': '#/$defs/parameters'}
    original = copy.deepcopy(discovery)
    view = app.contract_view(discovery)
    assert view['parameters']['properties']['episodes']['minimum'] == 1
    assert view['schema'] == schema and discovery == original
