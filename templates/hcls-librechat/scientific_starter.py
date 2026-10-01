"""Resolve a selected installed MD recipe without changing its native protocol.

Only file selection/validation lives here. The existing batch client owns live
schema checks, authorized admission, polling and verified result publication.
"""
import hashlib
import json
from pathlib import Path
import shlex


def resolve(case_directory, model, output, workspace, python, client):
    workspace = Path(workspace).resolve()
    case = (workspace / case_directory).resolve()
    output = (workspace / output).resolve()
    if not case.is_relative_to(workspace) or not output.is_relative_to(workspace):
        raise ValueError('Input and output paths must be inside the mounted workspace.')
    if not case.is_dir() or model not in {'gromacs', 'namd', 'amber', 'lammps'}:
        raise ValueError('Select an existing installed MD example and one of its supported engines.')
    # Both the case folder shown in the catalog and its explicit engine folder
    # identify the same recipe. Normalize only this unambiguous direct child;
    # never search arbitrary parents for a different protocol.
    if case.name == model and not (case / 'recipes.json').exists() and (case.parent / 'recipes.json').is_file():
        case = case.parent
    pack = next((p for p in [case, *case.parents] if p.is_relative_to(workspace) and
                 (p / 'manifest.json').is_file() and
                 json.loads((p / 'manifest.json').read_text()).get('schema') ==
                 'fs2-serve.nebius.ai/customer-starter-pack/v1'), None)
    if pack is None:
        raise ValueError('No starter-pack manifest found; arbitrary inputs use the native workflow tools.')
    manifest = json.loads((pack / 'manifest.json').read_text())
    if output.is_relative_to(pack):
        raise ValueError('Preserve the starter pack; choose an output directory outside it.')
    objects = {row['path']: row for row in manifest['objects']}
    verified = {}

    def checked(relative):
        path = (pack / relative).resolve()
        if not path.is_relative_to(pack) or relative not in objects:
            raise ValueError('Recipe file is outside the recorded pack: ' + str(relative))
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        row = objects[relative]
        if len(data) != row['size_bytes'] or sha != row['sha256']:
            raise ValueError('Starter file differs from its manifest: ' + relative)
        verified[relative] = sha
        return path, data

    case_id = case.relative_to(pack).as_posix()
    _, recipe_bytes = checked(case_id + '/recipes.json')
    recipes = json.loads(recipe_bytes)
    candidates = [r for r in recipes['recipes'] if r.get('model_id') == model]
    if len(candidates) != 1:
        raise ValueError('The selected case does not have exactly one recipe for this engine.')
    recipe, = candidates
    arguments = recipe['arguments']
    if arguments['operation'] != 'run-workflow':
        raise ValueError('This launcher supports native MD run-workflow recipes only.')
    _, template_bytes = checked(arguments['input_manifest']['$manifest'])
    template = json.loads(template_bytes)
    if len(template['entries']) != 1:
        raise ValueError('Multi-artifact examples require their explicit workflow, not guessed inputs.')
    entry, = template['entries']
    artifact = entry['artifact']
    source, _ = checked(artifact['$file'])
    parameters, parameter_bytes = checked(case_id + '/' + model + '/parameters.json')
    if json.loads(parameter_bytes) != arguments['parameters']:
        raise ValueError('Native parameters differ from the selected recipe; nothing submitted.')
    binding = {'case': str(case), 'model': model, 'output': str(output), 'files': verified,
               'pack_version': manifest['version']}
    identity = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    command = [python, client, '--model', model, '--tool', recipe['tool_name'],
               '--operation', arguments['operation'], '--source', str(source),
               '--parameters', str(parameters), '--entry-name', entry['name'],
               '--semantic-type', entry['semantic_type'], '--media-type', artifact['media_type'],
               '--compression', artifact.get('compression', 'none'), '--output', str(output),
               '--idempotency-key', 'starter-' + identity,
               '--display-name', arguments.get('client_context', {}).get('display_name', case_id + ' / ' + model)]
    if arguments.get('service_class'):
        command += ['--service-class', arguments['service_class']]
    return {'identity': identity, 'command': shlex.join(command), 'provenance': binding,
            'output_directory': str(output), 'sampling_limitations': recipes['expected']['description']}
