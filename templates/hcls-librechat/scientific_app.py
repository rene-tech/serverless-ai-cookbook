"""Guided App requests use the existing durable study and batch clients."""
import argparse
import asyncio
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import subprocess
import tempfile
import shutil

from jsonschema import Draft202012Validator, ValidationError
import scientific_study as study
from scientific_receipts import receipt_lock, save, load
from scientific_workflow_view import read_workflow

APPS = {'monai-spleen-ct', 'holoscan-endoscopy', 'isaac-healthcare'}


def batch_client():
    return study.workflow_module().batch


async def discover(model):
    batch = batch_client()
    endpoint = os.environ['SCIENTIFIC_MODELS_MCP_URL']
    headers = {'Authorization': 'Bearer ' + os.environ['SCIENTIFIC_MODELS_API_KEY']}
    async with batch.httpx2.AsyncClient(headers=headers, timeout=30, trust_env=False) as http:
        async with batch.Client(batch.streamable_http_client(endpoint, http_client=http)) as client:
            return await batch.call(client, 'get_model_schema', {'model_id': model,
                                    'protocol': 'scientific-batch-v1'})


def field_schema(root, field):
    seen = set()
    while isinstance(field, dict) and '$ref' in field:
        reference = field['$ref']
        if not reference.startswith('#/') or reference in seen:
            return field
        seen.add(reference)
        resolved = root
        for part in reference[2:].split('/'):
            resolved = resolved.get(part.replace('~1', '/').replace('~0', '~'), {})
        field = {**resolved, **{key: value for key, value in field.items() if key != '$ref'}}
    return field


def contract_view(discovery):
    batch = batch_client()
    contract = batch.scientific_contract(discovery)
    schema = contract.get('input_schema') or discovery.get('mcp_input_schema')
    if not isinstance(schema, dict):
        raise ValueError('This deployment has no typed submission schema for this App.')
    _, request = batch.submission_contract(schema)
    policy = contract.get('input_artifact_contract', {})
    entries = policy.get('entries', [policy['entry']] if 'entry' in policy else [])
    if not entries:
        raise ValueError('This App needs a source selector not supported by this form. Use its live chat contract.')
    parameters = field_schema(schema, request['properties']['parameters'])
    parameters = {**parameters, 'properties': {key: field_schema(schema, value)
        for key, value in parameters.get('properties', {}).items()}}
    return {'tool': contract.get('tool_name') or discovery.get('tool_name'),
            'schema': schema, 'parameters': parameters,
            'operations': request['properties']['operation'].get('enum', discovery.get('operations', [])),
            'service_classes': request['properties']['service_class'].get('enum', []),
            'entries': entries, 'revision': discovery.get('runtime_revision'),
            'contract_sha256': batch.digest(batch.canonical(discovery))}


def check_source(model, source, parameters, contract, entry):
    if source.stat().st_size > 512 * 1024 * 1024:
        raise ValueError('This form checks inputs up to 512 MiB. Use the batch file client for larger inputs.')
    if model == 'monai-spleen-ct':
        import nibabel as nib
        import numpy as np
        try:
            image = nib.load(source, keep_file_open=True)
        except nib.filebasedimages.ImageFileError as error:
            raise ValueError('Input is not a readable NIfTI CT. Select the original .nii or .nii.gz file.') from error
        if len(image.shape) != 3 or any(n < 1 for n in image.shape):
            raise ValueError('Select one 3D CT NIfTI volume.')
        if np.prod(image.shape, dtype=object) > 32 * 1024 * 1024:
            raise ValueError('CT exceeds the 32 million voxel preflight limit. Use the batch file client.')
        if not np.isfinite(image.affine).all() or abs(np.linalg.det(image.affine[:3, :3])) < 1e-12:
            raise ValueError('The CT affine is invalid. Supply the original valid image geometry.')
        if parameters.get('spatial_units', 'header') == 'header' and image.header.get_xyzt_units()[0] == 'unknown':
            raise ValueError('Spatial units are absent. Select the actual acquisition units; the image is unchanged.')
        for z in range(image.shape[2]):
            if not np.isfinite(np.asanyarray(image.dataobj[:, :, z])).all():
                raise ValueError('CT contains non-finite voxels. Repair the source data before submitting.')
        return ['3D geometry and finite voxels checked. Confirm that the CT values are in Hounsfield units.']
    policy = contract.get('input_artifact_contract', {})
    if entry['media_type'] == 'application/json':
        if source.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('Scenarios JSON exceeds the 8 MiB form limit.')
        document = json.loads(source.read_bytes())
        if policy.get('scenarios_schema'):
            Draft202012Validator(policy['scenarios_schema']).validate(document)
        names = [item['name'] for item in document.get('scenarios', [])]
        if len(names) != len(set(names)):
            raise ValueError('Scenario names must be unique.')
        return ['Scenarios checked against the deployed schema. Runtime assets are checked by the App.']
    try:
        archive = tarfile.open(source, mode='r:*')
    except tarfile.ReadError as error:
        raise ValueError('Input is not a readable TAR archive. Use an encoding supported by both the live contract and the batch file client.') from error
    with archive:
        names = set()
        unpacked = 0
        for count, member in enumerate(archive):
            name = PurePosixPath(member.name)
            unpacked += member.size
            if unpacked > 512 * 1024 * 1024:
                raise ValueError('Archive expands beyond the 512 MiB preflight limit. Use the batch file client.')
            if count >= 10000 or name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Archive must contain at most 10,000 ordinary relative files/directories, without links.')
            if str(name) in names:
                raise ValueError('Archive contains duplicate paths.')
            names.add(str(name))
        if model == 'holoscan-endoscopy':
            video = parameters.get('video_file')
            if video not in names:
                raise ValueError('video_file is absent from this archive. Choose its exact relative path.')
            member = next(item for item in archive.getmembers() if str(PurePosixPath(item.name)) == video)
            if not member.isfile() or member.size > 512 * 1024 * 1024:
                raise ValueError('Select an ordinary video file up to 512 MiB.')
            with tempfile.TemporaryDirectory() as scratch:
                target = Path(scratch) / 'video'
                with archive.extractfile(member) as source_file, target.open('wb') as output:
                    shutil.copyfileobj(source_file, output)
                probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file',
                    '-format_whitelist', 'mov,matroska,avi,mpegts,mpegvideo,h264,hevc', '-select_streams', 'v:0',
                    '-show_entries', 'stream=codec_name,width,height,nb_frames:stream_tags=rotate',
                    '-of', 'json', str(target)], capture_output=True, timeout=30)
                streams = json.loads(probe.stdout or '{}').get('streams', [])
                if probe.returncode or not streams or not streams[0].get('width'):
                    raise ValueError('Video header is unreadable. Supply a decodable video in the archive.')
                count = streams[0].get('nb_frames')
                if count and count.isdigit() and parameters.get('start_frame', 0) >= int(count):
                    raise ValueError(f'start_frame is outside the {count} declared source frames.')
            return ['Archive and video header checked. Full decoding and runtime assets are checked by the App.']
    return ['Archive paths checked. Video decoding, model assets and runtime compatibility are checked by the App.']


def draft_directory(request_id):
    if not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9-]{36}', request_id):
        raise ValueError('A stable form request ID is required.')
    return study.workspace() / '.scientific-apps' / study.owner_identity() / request_id


def draft_status(root):
    draft = load(root / 'draft.json')
    if not draft:
        return {'draft': None}
    study.verify_owner(draft)
    output = root / 'output'
    workflow = None
    if (output / 'study-binding.json').exists():
        try:
            workflow = read_workflow(str(output))
        except ValueError as error:
            if str(error) != 'Unknown study for this dedicated user.':
                raise
    return {'draft': draft, 'intent': (root / 'submit-intent.json').exists(), 'workflow': workflow}


def plan_for(draft, root):
    args = draft['arguments']
    return {'schema': 'scientific-workflow/v2', 'title': draft['model'], 'steps': [
        {'id': 'run', 'kind': 'batch', **args, 'parameters': str(root / 'parameters.json'),
         'idempotency_key': root.name, 'display_name': draft['model']},
        {'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {
            'title': draft['model'] + ' execution report', 'sections': [
                {'title': 'Recorded operation fields', 'file': {'step': 'run', 'file': 'result.json'},
                 'format': 'operation-timing'}]}}], 'deliverables': [
        {'name': 'report.md', 'role': 'report', 'source': {'step': 'report', 'file': 'report.md'}},
        {'name': 'result.json', 'role': 'data', 'source': {'step': 'run', 'file': 'result.json'}},
        {'name': 'output-manifest.json', 'role': 'provenance', 'source': {'step': 'run', 'file': 'output-manifest.json'}}]}


async def handle(action, model, body):
    if model not in APPS:
        raise ValueError('This form supports MONAI, Holoscan and Isaac only.')
    if action == 'preview':
        from scientific_preview import preview
        return preview(model, body)
    if action == 'contract':
        return contract_view(await discover(model))
    root = draft_directory(body.get('request_id'))
    if action == 'draft':
        saved = draft_status(root)
        if saved['draft'] and saved['draft']['model'] != model:
            raise ValueError('This saved request belongs to another App. Reopen its original form.')
        return saved
    root.mkdir(parents=True, exist_ok=True)
    with receipt_lock(root):
        previous = draft_status(root)
        if previous['draft'] and previous['draft']['model'] != model:
            raise ValueError('This saved request belongs to another App. Reopen its original form.')
        if action == 'submit':
            draft = previous['draft']
            if not draft or draft['model'] != model or draft['preflight_sha256'] != body.get('preflight_sha256'):
                raise ValueError('Preflight this exact request before submitting.')
            if previous.get('workflow'):
                return previous['workflow']
            batch = batch_client()
            source = Path(draft['arguments']['source'])
            if source.stat().st_size != draft['size_bytes']:
                raise ValueError('Input changed after preflight. Check the new input before submitting.')
            actual = batch.FileSource(source)
            if actual.sha256 != draft['source_sha256']:
                raise ValueError('Input changed after preflight. Check the new input before submitting.')
            if contract_view(await discover(model))['contract_sha256'] != draft['contract_sha256']:
                raise ValueError('The deployed contract changed. Review a new preflight before submitting.')
            save(root / 'submit-intent.json', {'preflight_sha256': draft['preflight_sha256']})
            save(root / 'parameters.json', draft['parameters'])
            study.submit(plan_for(draft, root), root / 'output')
            return read_workflow(str(root / 'output'))
        if action != 'preflight':
            raise ValueError('Unsupported form action.')
        if previous.get('workflow') or (root / 'submit-intent.json').exists():
            raise ValueError('This request already has a saved workflow. Open Runs; do not replace it.')
        discovery = await discover(model)
        view = contract_view(discovery)
        batch = batch_client()
        contract = batch.scientific_contract(discovery)
        parameters = body.get('parameters')
        if not isinstance(parameters, dict):
            raise ValueError('Parameters must be an object.')
        source = study.path_in_workspace(body.get('source'))
        if not source.is_file():
            raise ValueError('Select an existing workspace input file.')
        if source.stat().st_size > 512 * 1024 * 1024:
            raise ValueError('Input exceeds the 512 MiB form limit. Use the batch file client.')
        entries = [item for item in view['entries'] if item.get('name') == body.get('entry_name')]
        if len(entries) != 1:
            raise ValueError('Choose one published input role.')
        entry = entries[0]
        args = argparse.Namespace(model=model, tool=view['tool'], operation=body.get('operation'),
            service_class=body.get('service_class'), source=str(source), entry_name=entry['name'],
            media_type=entry['media_type'], semantic_type=entry['semantic_type'], compression=body.get('compression'))
        if args.operation not in view['operations'] or args.service_class not in view['service_classes']:
            raise ValueError('Choose an operation and service class from the current contract.')
        measured = batch.FileSource(source)
        args, _ = batch.resolve_source_compression(contract, parameters, args, measured)
        batch.preflight_source(contract, parameters, args, len(measured))
        batch.preflight_parameters(view['schema'], parameters, measured, args)
        checks = check_source(model, source, parameters, contract, entry)
        if batch.FileSource(source).sha256 != measured.sha256:
            raise ValueError('Input changed during preflight. Check it again.')
        draft = {'model': model, 'owner': study.owner_identity(), 'caller_fingerprint': study.caller_fingerprint(),
                 'arguments': vars(args), 'parameters': parameters, 'source_sha256': measured.sha256,
                 'size_bytes': len(measured), 'contract_sha256': view['contract_sha256'], 'checks': checks}
        draft['preflight_sha256'] = batch.digest(batch.canonical(draft))
        save(root / 'parameters.json', parameters)
        save(root / 'draft.json', draft)
        return {'draft': draft}


def main():
    action, model = sys.argv[1:3]
    try:
        result = asyncio.run(handle(action, model, json.load(sys.stdin)))
    except ValidationError as error:
        result = {'error': '/'.join(map(str, error.absolute_path)) + ': ' + error.message[:800]}
    except BlockingIOError:
        result = {'error': 'Another request holds this saved request lock. Reconnect after it finishes; do not create a replacement.'}
    except (ValueError, OSError) as error:
        result = {'error': str(error)[:1000]}
    except Exception:
        result = {'error': 'App request could not be completed. Check the saved request in Runs before retrying.'}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
