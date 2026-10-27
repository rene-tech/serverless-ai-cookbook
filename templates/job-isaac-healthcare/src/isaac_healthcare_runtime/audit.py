"""CPU validation of delivered general-workflow artifacts and their original inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

from .contract import SOURCE, checked, digest, json_loads, parameters, scenarios, schema
from .project import relative_path
from .validate import validate_recording


def validate_delivery(*, operation, input_path, project_path, parameter_values, result_path, archive_path,
                      input_identity=None):
    values = parameters(parameter_values)
    result = checked(json_loads(result_path.read_bytes()), schema('result'), 'result')
    if result['source_revision'] != SOURCE or result['operation'] != operation:
        raise ValueError('Delivered runtime/operation differs from the request')
    if result['parameters'] != values:
        raise ValueError('Delivered scientific parameters differ from the request')
    paths = {'input_sha256': input_path, 'project_sha256': project_path}
    if input_identity is None:
        input_identity = {name: digest(path) if path is not None else None for name, path in paths.items()}
    if (not isinstance(input_identity, dict) or input_identity.keys() != paths.keys() or
            any(value is not None and (not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value))
                for value in input_identity.values())):
        raise ValueError('Audit requires the exact original input/project SHA identity')
    for name, path in paths.items():
        if path is not None and digest(path) != input_identity[name]:
            raise ValueError(f'Original {name} differs from the supplied request identity')
        if result[name] != input_identity[name]:
            raise ValueError(f'Delivered {name} differs from the original input')
    if result['files']['simulation.tar'] != {'sha256': digest(archive_path), 'size_bytes': archive_path.stat().st_size}:
        raise ValueError('Delivered archive differs from its full SHA/size declaration')
    selected = result.get('provenance', {}).get('selected_workflow') or {}
    if operation in ('simulate', 'replay'):
        if not selected.get('workflow') or not selected.get('mode'):
            raise ValueError('Simulation lacks its resolved workflow and mode')
        for name in ('workflow', 'mode'):
            if values[name] is not None and values[name] != selected[name]:
                raise ValueError(f'Delivered {name} differs from the explicit request')
        if operation == 'replay' and selected['mode'] != 'replay':
            raise ValueError('Replay operation did not execute the replay mode')
        if result['scientific_validation'] != 'passed':
            raise ValueError('Scientific integrity validation did not pass')
    elif operation in ('inspect', 'lint'):
        if result['scientific_validation'] != 'not_applicable' or result['task_complete'] is not None or result['scenarios']:
            raise ValueError('Discovery incorrectly claims simulator execution')
    reports = []
    with tarfile.open(archive_path, 'r:') as archive, tempfile.TemporaryDirectory(prefix='isaac-audit-') as temporary:
        inventory = {}
        for member in archive.getmembers():
            name = relative_path(member.name).as_posix()
            if not member.isfile() or name in inventory or name != member.name:
                raise ValueError('Scientific archive must contain unique normalized regular files')
            if (any(part in ('.operator', '.runtime', '.project') for part in Path(name).parts) or
                    Path(name).name == 'simulator.log'):
                raise ValueError('Scientific archive includes private runtime diagnostics')
            checksum = hashlib.sha256()
            with archive.extractfile(member) as source:
                while block := source.read(4 * 1024**2):
                    checksum.update(block)
            inventory[name] = {'sha256': checksum.hexdigest(), 'size_bytes': member.size}
        if inventory != result['provenance']['artifact_files']:
            raise ValueError('Archive full-file inventory differs from reported provenance')
        archive_provenance = json_loads(archive.extractfile('provenance.json').read())
        expected_provenance = {key: value for key, value in result['provenance'].items() if key != 'artifact_files'}
        if archive_provenance != expected_provenance:
            raise ValueError('Archived provenance differs from result provenance')
        original = 'request/scenarios.json'
        if input_identity['input_sha256'] is not None:
            if inventory.get(original, {}).get('sha256') != input_identity['input_sha256']:
                raise ValueError('Archived scenarios differ from the original input SHA')
            cases = scenarios(json_loads(archive.extractfile(original).read()), values['seed'])
        else:
            if original in inventory:
                raise ValueError('Archive contains scenarios absent from the original request')
            cases = [{'name': 'default', 'seed': values['seed']}]
        if operation == 'replay' or (operation == 'simulate' and selected.get('mode') == 'replay'):
            cases = [{**case, 'replay_episode': index} for case in cases for index in values['replay_episodes']]
        if operation in ('simulate', 'replay') and [row['scenario'] for row in result['scenarios']] != cases:
            raise ValueError('Delivered scenarios differ from the original request')
        for index, row in enumerate(result['scenarios']):
            expected = f'scenario-{index:06d}/demos.hdf5'
            if row['recording'] != expected:
                raise ValueError('Scenario recording location is inconsistent')
            recording = Path(temporary) / f'{index}.hdf5'
            with archive.extractfile(expected) as source, recording.open('wb') as target:
                shutil.copyfileobj(source, target)
            if row['resolved'] != selected:
                raise ValueError('Scenario resolved workflow differs from its execution provenance')
            validated = validate_recording(recording, values, scene=selected)
            for key, value in validated.items():
                if key != 'task_complete' and row[key] != value:
                    raise ValueError(f'Scenario {index} recorded {key} differs from its report')
            terminal = row['terminal']
            counts = ('successful_episodes', 'requested_episodes', 'saved_demonstrations', 'attempts')
            if (any(type(terminal.get(name)) is not int or terminal[name] < 0 for name in counts) or
                    type(terminal.get('task_complete')) is not bool or
                    terminal['successful_episodes'] > terminal['requested_episodes'] or
                    not terminal['successful_episodes'] <= terminal['attempts'] <= values['episodes'] * values['attempts'] or
                    terminal['saved_demonstrations'] > terminal['attempts']):
                raise ValueError('Upstream terminal counters are inconsistent')
            if (row['task_complete'] != terminal['task_complete'] or
                    terminal['task_complete'] != (terminal['successful_episodes'] == values['episodes']) or
                    terminal['requested_episodes'] != values['episodes'] or
                    terminal['saved_demonstrations'] != len(validated['episodes']) or
                    terminal['attempts'] > values['episodes'] * values['attempts'] or
                    validated['successful_episodes'] > terminal['successful_episodes']):
                raise ValueError('Upstream terminal task outcome differs from archived evidence')
            scientific = json_loads(archive.extractfile(f'scenario-{index:06d}/workflow.json').read())
            if scientific != row:
                raise ValueError('Archived workflow result differs from public summary')
            reports.append({'scenario': row['scenario'], 'task_complete': row['task_complete'],
                            'samples': validated['samples'], 'episodes': validated['episodes']})
    if reports and result['task_complete'] != all(row['task_complete'] for row in reports):
        raise ValueError('Aggregate task completion differs from individual cases')
    return {'validation': 'passed', 'operation': operation, 'task_complete': result['task_complete'],
            'source_revision': SOURCE, 'input_sha256': result['input_sha256'],
            'project_sha256': result['project_sha256'], 'archive_sha256': digest(archive_path),
            'archive_files': inventory, 'scenarios': reports,
            'note': 'Integrity and recorded sensor structure are distinct from task success and physical realism.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--project', type=Path)
    parser.add_argument('--input-identity', type=Path,
                        help='Trusted original input_sha256/project_sha256 JSON for completed-output recovery')
    for name in ('parameters', 'result', 'archive', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = validate_delivery(operation=args.operation, input_path=args.input, project_path=args.project,
                               parameter_values=json_loads(args.parameters.read_bytes()),
                               result_path=args.result, archive_path=args.archive,
                               input_identity=json_loads(args.input_identity.read_bytes()) if args.input_identity else None)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'validation': 'passed', 'operation': args.operation,
                      'task_complete': report['task_complete'], 'report': str(args.output)}))


if __name__ == '__main__':
    main()
