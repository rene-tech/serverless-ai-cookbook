"""Exercise real deploy.sh against a local fake CLI; never contacts Nebius."""
import json
import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).parent / 'scripts/deploy.sh'


def command(tmp_path, public_ip=None, ssh=False, s3_profile=None, reasoning_effort=None,
            image_override=True, dry_run=False, model_deadline=None):
    executable = tmp_path / 'nebius'
    executable.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    executable.chmod(0o700)
    environment = {key: value for key, value in os.environ.items()
                   if key not in {'SERVERLESS_PUBLIC_IP', 'SSH_PUBLIC_KEY_FILE', 'NEBIUS_PROFILE',
                                  'SCIENTIFIC_CHAT_REASONING_EFFORT', 'NEBIUS_CLI',
                                  'SCIENTIFIC_AGENT_MODEL_DEADLINE_MS', 'SCIENTIFIC_AGENT_MODEL_TIME_MS',
                                  'SCIENTIFIC_AGENT_REPEAT_ROUNDS',
                                  'SERVERLESS_DRY_RUN', 'IMAGE'}}
    environment.update(PATH=str(tmp_path) + os.pathsep + os.environ['PATH'],
        NEBIUS_PROJECT_ID='project-fixture', NEBIUS_SUBNET_ID='subnet-fixture',
        SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR='secret-fixture',
        TOKEN_FACTORY_SECRET_SELECTOR='secret-fixture', TAVILY_SECRET_SELECTOR='secret-fixture',
        S3_CREDENTIAL_SECRET_SELECTOR='secret-fixture', USER_PASSWORD_SECRET_SELECTOR='secret-fixture',
        SCIENTIFIC_STUDY_OWNER_MODE='first-instance',
        SEED_DEFAULT_USER_EMAIL='fixture@example.invalid', TEAM_BUCKET_NAME='fixture-bucket', TEAM_ID='fixture')
    if image_override:
        environment['IMAGE'] = 'example.invalid/image:fixture'
    if dry_run:
        environment['SERVERLESS_DRY_RUN'] = 'true'
    if public_ip is not None:
        environment['SERVERLESS_PUBLIC_IP'] = public_ip
    if s3_profile is not None:
        environment['S3_AWS_PROFILE'] = s3_profile
    if reasoning_effort is not None:
        environment['SCIENTIFIC_CHAT_REASONING_EFFORT'] = reasoning_effort
    if model_deadline is not None:
        environment['SCIENTIFIC_AGENT_MODEL_DEADLINE_MS'] = model_deadline
    if ssh:
        key = tmp_path / 'fixture.pub'
        key.write_text('ssh-ed25519 public-fixture test-only\n')
        environment['SSH_PUBLIC_KEY_FILE'] = str(key)
    return subprocess.run(['bash', str(SCRIPT)], env=environment, capture_output=True, text=True, check=False)


@pytest.mark.parametrize('value', [None, 'true'])
def test_default_and_explicit_public_remain_compatible(tmp_path, value):
    result = command(tmp_path, value)
    assert result.returncode == 0
    arguments = json.loads(result.stdout)
    assert arguments.count('--public') == 1 and '--public=false' not in arguments
    assert '--ssh-key' not in arguments


def test_private_without_ssh_retains_application_and_volume_settings(tmp_path):
    result = command(tmp_path, 'false')
    assert result.returncode == 0 and result.stderr == ''
    arguments = json.loads(result.stdout)
    assert '--public' not in arguments and arguments.count('--public=false') == 1
    assert '--ssh-key' not in arguments
    assert arguments[arguments.index('--container-port') + 1] == '3080'
    assert arguments[arguments.index('--volume') + 1] == 's3://fixture-bucket:/workspace:rw:default@secret-fixture'


def test_storage_profile_is_configurable(tmp_path):
    result = command(tmp_path, 'false', s3_profile='eu-north1-recording')
    assert result.returncode == 0 and result.stderr == ''
    arguments = json.loads(result.stdout)
    assert arguments[arguments.index('--volume') + 1] == (
        's3://fixture-bucket:/workspace:rw:eu-north1-recording@secret-fixture'
    )


def test_recording_completion_budget_is_explicit(tmp_path):
    result = command(tmp_path, 'false')
    assert result.returncode == 0 and result.stderr == ''
    arguments = json.loads(result.stdout)
    assert 'SCIENTIFIC_CHAT_MAX_OUTPUT_TOKENS=16384' in arguments


@pytest.mark.parametrize('deadline', [None, '60000'])
def test_reasoning_time_budgets_are_forwarded_without_changing_model(tmp_path, deadline):
    result = command(tmp_path, model_deadline=deadline)
    assert result.returncode == 0
    arguments = json.loads(result.stdout)
    assert f'SCIENTIFIC_AGENT_MODEL_DEADLINE_MS={deadline or "90000"}' in arguments
    assert 'SCIENTIFIC_AGENT_MODEL_TIME_MS=300000' in arguments
    assert 'SCIENTIFIC_AGENT_REPEAT_ROUNDS=2' in arguments
    assert 'SCIENTIFIC_CHAT_MODEL=moonshotai/Kimi-K3' in arguments
    assert 'SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS=131072' in arguments


@pytest.mark.parametrize('override,expected', [(None, 'high'), ('low', 'low')])
def test_reasoning_default_and_explicit_override(tmp_path, override, expected):
    result = command(tmp_path, 'false', reasoning_effort=override)
    assert result.returncode == 0
    assert 'SCIENTIFIC_CHAT_REASONING_EFFORT=' + expected in json.loads(result.stdout)


def test_new_installation_uses_shared_release_without_image_override(tmp_path):
    result = command(tmp_path, image_override=False)
    assert result.returncode == 0
    arguments = json.loads(result.stdout)
    release = SCRIPT.with_name('release-image.sh').read_text()
    selected = next(line.split('=', 1)[1].strip("'") for line in release.splitlines()
                    if line.startswith('SCIENTIFIC_AI_RELEASE_IMAGE='))
    assert arguments[arguments.index('--image') + 1] == selected
    assert ':general-kimi-' in selected


def test_dry_run_uses_the_same_deployment_path(tmp_path):
    result = command(tmp_path, dry_run=True)
    assert result.returncode == 0
    assert json.loads(result.stdout).count('--dry-run') == 1


def test_explicit_preview_study_namespace_is_forwarded(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER', 'owner-preview-fixture')
    result = command(tmp_path, dry_run=True)
    assert result.returncode == 0
    arguments = json.loads(result.stdout)
    assert 'SCIENTIFIC_STUDY_OWNER=owner-preview-fixture' in arguments
    assert 'TEAM_ID=fixture' in arguments
    assert 'SCIENTIFIC_STUDY_OWNER_MODE=first-instance' in arguments


def test_private_explicit_ssh_is_not_silently_removed(tmp_path):
    result = command(tmp_path, 'false', ssh=True)
    assert result.returncode == 0
    arguments = json.loads(result.stdout)
    assert '--public=false' in arguments
    assert arguments[arguments.index('--ssh-key') + 1] == 'ssh-ed25519 public-fixture test-only'
    assert 'SSH access can allocate a public IP' in result.stderr
    assert 'Unset SSH_PUBLIC_KEY_FILE' in result.stderr


@pytest.mark.parametrize('value', ['yes', '0', 'FALSE'])
def test_invalid_public_ip_setting_fails_before_cli(tmp_path, value):
    result = command(tmp_path, value)
    assert result.returncode == 2 and result.stdout == ''
    assert 'must be true or false' in result.stderr
