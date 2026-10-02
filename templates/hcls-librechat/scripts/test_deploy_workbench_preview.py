import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('preview', Path(__file__).with_name('deploy-workbench-preview.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_receipt_is_private_json(tmp_path):
    import json
    path = tmp_path / 'receipt.json'
    module.save(path, {'status': 'fixture'})
    assert json.loads(path.read_text()) == {'status': 'fixture'}
    assert path.stat().st_mode & 0o777 == 0o600


def source():
    env = [{'name': 'SEED_DEFAULT_USER_EMAIL', 'value': 'owner@example.invalid'}]
    env += [{'name': name, 'mysterybox_secret': {'secret_id': 'fixture', 'version_id': 'v1'}}
            for name in ('SCIENTIFIC_MODELS_API_KEY', 'NEBIUS_API_KEY', 'TAVILY_API_KEY', 'SEED_DEFAULT_USER_PASSWORD')]
    return {'metadata': {'id': 'old', 'parent_id': 'project'}, 'spec': {
        'image': 'old-image', 'platform': 'cpu-d3', 'preset': '4vcpu-16gb',
        'disk': {'size_bytes': str(100 * 1024**3)}, 'subnet_id': 'subnet',
        'ports': [{'container_port': 3080, 'host_port': 3080, 'protocol': 'HTTP'}],
        'environment_variables': env, 'volumes': [{'source': 's3://owner-bucket',
            'container_path': '/workspace', 'mode': 'READ_WRITE',
            's3_config': {'mysterybox_secret': {'secret_id': 's3-fixture', 'version_id': 'v1'}}}]}}


def test_preview_preserves_source_bindings_without_adopting_old_studies():
    old = source()
    request = module.preview(old, 'preview', 'new-image', 'owner-preview', 'public-key')
    assert old == source()
    assert request['spec']['volumes'] == old['spec']['volumes']
    original = {v['name']: v for v in old['spec']['environment_variables']}
    env = {v['name']: v for v in request['spec']['environment_variables']}
    for name, value in original.items():
        assert env[name] == value
    assert env['SCIENTIFIC_STUDY_OWNER']['value'] == 'owner-preview'
    assert env['SCIENTIFIC_CHAT_MODEL']['value'] == 'moonshotai/Kimi-K3'
    args = module.create_args(request, 'regional')
    assert args[args.index('--volume') + 1] == 's3://owner-bucket:/workspace:rw:regional@s3-fixture@v1'


def test_parallel_same_owner_is_rejected():
    with pytest.raises(ValueError, match='namespace'):
        module.preview(source(), 'preview', 'image', 'owner@example.invalid', 'key')


def test_unhandled_source_setting_is_not_silently_dropped():
    request = module.preview(source(), 'preview', 'image', 'new-owner', 'key')
    request['spec']['unknown-setting'] = True
    with pytest.raises(ValueError, match='explicit handling'):
        module.create_args(request, 'regional')
