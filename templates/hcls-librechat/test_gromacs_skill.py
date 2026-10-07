import importlib.util
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import tarfile

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2] / 'skills/scientific-ai/gromacs'
spec = importlib.util.spec_from_file_location('gromacs_bundle', ROOT / 'scripts/make-input-bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)
MPI_SCHEMA = json.loads((ROOT / 'references/mpi-request.schema.json').read_text())
MPI_VALIDATOR = Draft202012Validator(MPI_SCHEMA)


def test_bundle_preserves_native_inputs_and_is_reproducible(tmp_path):
    source = tmp_path / 'inputs'
    (source / 'includes').mkdir(parents=True)
    (source / 'includes/ligand.itp').write_text('actual topology bytes\n')
    (source / 'simulation.tpr').write_bytes(b'native fixture')
    first = bundle.build(source, tmp_path / 'first.tar.gz')
    second = bundle.build(source, tmp_path / 'second.tar.gz')
    assert first['sha256'] == second['sha256']
    with tarfile.open(first['path']) as archive:
        assert archive.extractfile('simulation.tpr').read() == b'native fixture'
        assert archive.getnames() == ['includes/ligand.itp', 'simulation.tpr']
    with pytest.raises(FileExistsError):
        bundle.build(source, tmp_path / 'first.tar.gz')


def test_bundle_rejects_output_within_source_and_links(tmp_path):
    source = tmp_path / 'inputs'
    source.mkdir()
    (source / 'input').write_bytes(b'a')
    with pytest.raises(ValueError, match='outside'):
        bundle.build(source, source / 'output.tar.gz')
    (source / 'alias').symlink_to(source / 'input')
    with pytest.raises(ValueError, match='symlinks'):
        bundle.build(source, tmp_path / 'output.tar.gz')


def test_mpi_schema_fixture_has_committed_byte_identity():
    source = json.loads((ROOT / 'references/mpi-contract-source.json').read_text())
    assert source['source_commit'] == '0aecab6bdca3346a74426cea24a4753cd4f54270'
    assert hashlib.sha256((ROOT / 'references/mpi-request.schema.json').read_bytes()).hexdigest() == source['sha256']
    assert hashlib.sha256((ROOT / 'references/scientific-run-request.schema.json').read_bytes()).hexdigest() == source['rest_envelope']['sha256']
    Draft202012Validator.check_schema(MPI_SCHEMA)


@pytest.mark.parametrize('name,nodes,gpus', [
    ('prepared-tpr-mpi.json', 2, 1),
    ('prepared-tpr-mpi-8gpu.json', 1, 8),
    ('prepared-tpr-mpi-16gpu.json', 2, 8),
])
def test_mpi_parameter_examples_match_committed_runtime(name, nodes, gpus):
    value = json.loads((ROOT / 'examples' / name).read_text())
    MPI_VALIDATOR.validate(value)
    assert value['nodes'] == nodes
    assert value.get('gpus_per_node', 1) == gpus
    legacy = json.loads((ROOT / 'examples/prepared-tpr-mpi.json').read_text())
    # The larger placement examples do not silently alter TPRs, seeds, offload,
    # requested integration duration or the output/analysis protocol.
    assert value['jobs'] == legacy['jobs']
    assert value['threads'] == legacy['threads'] == 8


@pytest.mark.parametrize('nodes,gpus', list(itertools.product(range(1, 9), (1, 2, 4, 8))))
def test_customer_shapes_follow_contract_not_legacy_one_gpu_assumption(nodes, gpus):
    value = json.loads((ROOT / 'examples/prepared-tpr-mpi.json').read_text())
    value.update(nodes=nodes, gpus_per_node=gpus)
    if nodes * gpus <= 16:
        MPI_VALIDATOR.validate(value)
    else:
        with pytest.raises(ValidationError):
            MPI_VALIDATOR.validate(value)


@pytest.mark.parametrize('field,value', [
    ('nodes', 0), ('nodes', 9), ('nodes', True), ('gpus_per_node', 3),
    ('gpus_per_node', 16), ('gpus_per_node', False), ('threads', 0),
    ('threads', 9), ('transport', 'rdma'), ('gpu_snapshot', True),
    ('max_output_bytes', 48 * 1024**3 + 1),
])
def test_invalid_or_operator_only_options_are_not_published_as_customer_fields(field, value):
    request = json.loads((ROOT / 'examples/prepared-tpr-mpi.json').read_text())
    request[field] = value
    with pytest.raises(ValidationError):
        MPI_VALIDATOR.validate(request)


def test_output_budget_examples_fit_real_runtime_bounds():
    for name in ('prepared-tpr-mpi-8gpu.json', 'prepared-tpr-mpi-16gpu.json'):
        value = json.loads((ROOT / 'examples' / name).read_text())
        assert value['max_output_bytes'] == 32 * 1024**3
        value['max_output_bytes'] = 48 * 1024**3
        MPI_VALIDATOR.validate(value)


def test_benchmark_guidance_requires_native_artifacts_not_outer_envelope():
    skill = (ROOT / 'SKILL.md').read_text()
    reference = (ROOT / 'references/mpi.md').read_text()
    assert 'native_outputs.results[].source_result_file' in skill
    for field in ('completed_steps', 'performance_ns_per_day', 'wall_seconds', 'step_id'):
        assert field in reference
    assert 'empty table' in reference
    assert 'unknown, not zero ns/day' in reference
    assert 'actual completed records' in reference


def test_documented_rest_example_builds_valid_envelope_and_idempotency_header(tmp_path):
    """Execute the published jq/body/header recipe with curl replaced locally.

    No network call, credentials, artifact upload or scientific job is made.
    Both HTTP envelope and inner MPI parameters must match committed contracts.
    """
    reference = (ROOT / 'references/mpi.md').read_text()
    blocks = re.findall(r'```sh\n(.*?)\n```', reference, re.S)
    examples = [block for block in blocks if 'curl --fail-with-body' in block]
    assert len(examples) == 1
    manifest = {'artifact_id': 'offline-fixture-manifest', 'sha256': 'a' * 64,
                'size_bytes': 123, 'media_type': 'application/vnd.fs2.scientific-manifest+json',
                'compression': 'none'}
    (tmp_path / 'manifest-artifact.json').write_text(json.dumps(manifest))
    parameters = json.loads((ROOT / 'examples/prepared-tpr-mpi-8gpu.json').read_text())
    (tmp_path / 'parameters.json').write_text(json.dumps(parameters))
    # Shell function shadows curl and records argv; even the endpoint is a .invalid fixture.
    script = 'set -eu\ncurl() { printf "%s\\0" "$@"; }\n' + examples[0]
    result = subprocess.run(['bash', '-c', script], cwd=tmp_path, check=True,
                            capture_output=True,
                            env={'PATH': '/usr/bin:/bin', 'SCIENTIFIC_AI_API_KEY': 'offline-fixture-only',
                                 'SCIENTIFIC_AI_BASE_URL': 'https://offline.invalid'})
    args = result.stdout.decode().rstrip('\0').split('\0')
    headers = [args[index + 1] for index, token in enumerate(args) if token == '--header']
    assert 'Idempotency-Key: md-scaling-1x8-attempt-01' in headers
    assert 'Content-Type: application/json' in headers
    assert args[-1] == 'https://offline.invalid/v1/models/gromacs-mpi:submit'
    request = json.loads((tmp_path / 'request.json').read_text())
    envelope = json.loads((ROOT / 'references/scientific-run-request.schema.json').read_text())
    Draft202012Validator(envelope).validate(request)
    MPI_VALIDATOR.validate(request['parameters'])
    assert request['input_manifest'] == manifest
    assert request['parameters'] == parameters
    assert 'idempotency_key' not in request
    with pytest.raises(ValidationError):
        Draft202012Validator(envelope).validate({**request, 'idempotency_key': 'wrong-location'})
