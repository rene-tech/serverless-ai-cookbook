"""General project-backed Isaac for Healthcare batch execution and provenance."""

import argparse
from contextlib import contextmanager
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from .contract import (ASSET_GENERATION, MODEL_ID, OPERATIONS, SOURCE, checked,
                       digest, json_loads, parameters, scenarios, schema)
from .project import apply_project_defaults, prepare_project, relative_path
from .validate import validate_recording

ROOT = Path('/opt/i4h')
PYTHON = ROOT / 'arena/.venv/bin/python'
ASSET_MANIFEST = Path('/opt/i4h-assets/v0.9.0-7cf86a1/manifest.json')
PATCH_MANIFEST = Path('/opt/isaac-healthcare/upstream-patches.json')
TRAINING_ENTRY = Path('/opt/isaac-healthcare/training/run.py')


def command(values, scenario, directory, *, context_path=None, headless=True):
    argv = [str(PYTHON), '-I', '-m', 'isaac_healthcare_runtime.launch']
    if context_path is not None:
        argv.extend(['--context', str(context_path)])
    argv.extend(['--workflow', values['workflow']])
    if headless:
        argv.extend(['--headless', '--no-sensor-view'])
    argv.extend([
                 '--envs', str(values['envs']), '--episodes', str(values['episodes']),
                 '--attempts', str(values['attempts']), '--spacing', str(values['spacing']),
                 '--idle-seconds', str(values['idle_seconds']),
                 '--record', str(directory / 'demos.hdf5'), '--record-failures'])
    flags = {'mode': '--mode', 'episode_steps': '--episode-steps', 'physics': '--presets',
             'checkpoint': '--checkpoint', 'dataset': '--dataset', 'patient_twin': '--patient-twin',
             'prompt': '--prompt', 'fluoro_backend': '--fluoro-backend', 'fluoro_device': '--fluoro-device'}
    for key, flag in flags.items():
        if values.get(key) is not None:
            argv.extend([flag, str(values[key])])
    if values['mode'] == 'replay':
        argv.extend(['--episode', ','.join(map(str, values['replay_episodes']))])
    seed = scenario.get('seed', values['seed'])
    if seed is not None:
        argv.extend(['--seed', str(seed)])
    if not values['cameras']:
        argv.append('--no-cameras')
    return argv


def execution_environment(directory, context=None):
    env = dict(os.environ)
    for name, relative in {'HOME': 'home', 'XDG_CACHE_HOME': 'cache', 'CUDA_CACHE_PATH': 'cuda',
                           'TMPDIR': 'tmp', 'I4H_PID_DIR': 'pids', 'ISAAC_HEALTHCARE_KIT_ROOT': 'kit'}.items():
        path = directory / '.runtime' / relative
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env.update({'PYTHONDONTWRITEBYTECODE': '1', 'I4H_WORKFLOWS': str(ROOT), 'UV_OFFLINE': '1',
                'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
    if context is not None:
        env['I4H_WORKFLOWS'] = context['effective_root']
        env['I4H_PROJECT_ROOT'] = context['project_dir']
        if context.get('asset_root'):
            env['I4H_ASSET_PATH'] = context['asset_root']
    # Same official headless consent as upstream run.sh, conditional on explicit
    # caller EULA acceptance checked before any simulator/trainer execution.
    if env.get('ACCEPT_EULA') == 'Y' or env.get('ISAACSIM_ACCEPT_EULA') == 'Y':
        env['OMNI_KIT_ACCEPT_EULA'] = 'YES'
    privacy = Path(env['HOME']) / '.nvidia-omniverse/config/privacy.toml'
    privacy.parent.mkdir(parents=True, exist_ok=True)
    if not privacy.exists():
        privacy.write_text('[privacy]\nperformance = false\npersonalization = false\nusage = false\n')
    return env


def execute(argv, directory, *, context=None, extra_env=None):
    env = execution_environment(directory, context)
    env.update(extra_env or {})
    operator = directory.parent.parent / '.operator'
    operator.mkdir(exist_ok=True)
    raw_log = operator / (directory.name + '.log')
    with raw_log.open('x', encoding='utf-8') as log:
        process = subprocess.Popen(argv, cwd=context['effective_root'] if context else ROOT,
                                   env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True,
                                   text=True, encoding='utf-8', errors='replace', bufsize=1)
        previous = {}

        def stop(signum, frame):
            if process.poll() is None:
                os.killpg(process.pid, signum)

        try:
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous[signum] = signal.signal(signum, stop)
            for line in process.stdout:
                log.write(line)
                log.flush()
                sys.stdout.write(line)
                sys.stdout.flush()
            return process.wait(), raw_log
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def policy_bus_directory():
    """Use the operator's short session-owned IPC root when one is supplied."""
    root = Path(os.environ.get('I4H_BUS_ROOT', '/tmp'))
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('I4H_BUS_ROOT must be an existing absolute directory')
    return tempfile.TemporaryDirectory(prefix='i4h-bus-', dir=root)


@contextmanager
def policy_backends(selected, values, context, context_path, directory):
    """Start only graph-declared policy services in their own installed envs.

    The readiness message and 600-second budget match upstream run.sh. All
    started process groups belong to this invocation and are always joined.
    No dependency/checkpoint installation is attempted during a customer job.
    """
    backends = selected['backends']
    if not backends:
        yield {}
        return
    processes, logs = [], []
    operator = directory.parent.parent / '.operator'
    operator.mkdir(exist_ok=True)
    env = execution_environment(directory, context)
    # Unix transport keeps policy IPC functional under the exact offline
    # socket filter without opening network ports. A short private path avoids
    # AF_UNIX's 108-byte path limit for arbitrarily deep customer output paths.
    bus_dir = policy_bus_directory()
    address = 'unixsock-stream/' + bus_dir.name + '/bus.sock'
    configs = {}
    for role in ('router', 'client'):
        path = directory / '.runtime' / (role + '.json5')
        path.write_text(json.dumps({'mode': role,
                        'scouting': {'multicast': {'enabled': False}, 'gossip': {'enabled': False}},
                        'listen': {'endpoints': [address] if role == 'router' else []},
                        'connect': {'endpoints': [address] if role == 'client' else []}}))
        configs[role] = str(path)
    env['CUDA_VISIBLE_DEVICES'] = os.environ.get('CUDA_VISIBLE_DEVICES', '0')
    namespace = 'isaac/' + directory.name
    previous = {}

    def stop(signum, frame):
        for process, path in processes:
            if process.poll() is None:
                os.killpg(process.pid, signum)
        raise SystemExit(128 + signum)

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, stop)
        for index, backend in enumerate(backends):
            project = Path(context['effective_root']).joinpath(*relative_path(backend['project']).parts)
            python = project / '.venv/bin/python'
            if not python.is_file():
                raise RuntimeError(f"Policy backend environment {backend['project']} is not installed; build its pinned uv environment before execution")
            argv = [str(python), '-I', str(Path(__file__).with_name('serve_backend.py')),
                    '--context', str(context_path), '--entry', backend['entry'], '--',
                    '--namespace', namespace, '--preload', backend['preload']]
            if values['checkpoint'] is not None:
                argv.extend(['--checkpoint', values['checkpoint']])
            local_env = dict(env)
            local_env['ZENOH_CONFIG'] = configs['router' if index == 0 else 'client']
            local_env['I4H_ZENOH_LISTEN'] = ''
            local_env['I4H_ZENOH_CONNECT'] = ''
            path = operator / f'{directory.name}-backend-{index}.log'
            log = path.open('x')
            logs.append(log)
            process = subprocess.Popen(argv, cwd=project, env=local_env, stdout=log,
                                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       start_new_session=True)
            processes.append((process, path))
            # The first service owns the local router; wait for it before
            # starting additional clients so transport readiness is explicit.
            started = time.monotonic()
            while True:
                content = path.read_text(errors='replace')
                if 'ready for specs' in content:
                    break
                if process.poll() is not None or 'Traceback' in content or 'Error:' in content:
                    raise RuntimeError(f'Policy backend failed before readiness; inspect operator log {path.name}')
                if time.monotonic() - started >= 600:
                    raise RuntimeError(f'Policy backend readiness exceeded upstream 600-second budget; inspect {path.name}')
                time.sleep(1)
        yield {'ZENOH_CONFIG': configs['client'], 'I4H_ZENOH_CONNECT': '',
               'I4H_ZENOH_LISTEN': '', 'ISAAC_HEALTHCARE_NAMESPACE': namespace}
    finally:
        for process, path in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process, path in processes:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            # Retain actionable backend diagnostics in the operator channel.
            sys.stdout.write(path.read_text(errors='replace'))
        for log in logs:
            log.close()
        bus_dir.cleanup()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


@contextmanager
def interactive_command(values, scenario, directory, *, context, selected, kit_arguments=()):
    """Share batch project/controller resolution with the session owner.

    The caller starts and joins the Kit child while holding this context. This
    helper neither allocates a session nor changes mode, physics, duration or
    recording settings. Authentication/media/session leases belong to the
    interactive owner.
    """
    if selected is None or not selected.get('lint', {}).get('ok'):
        raise ValueError('Interactive launch requires a resolved, linted project workflow')
    values = {**values, 'mode': selected['mode']}
    directory.mkdir(parents=True, exist_ok=True)
    env = execution_environment(directory, context)
    local_context = directory / '.runtime/interactive-context.json'
    _write(local_context, {'project': context, 'parameters': values,
                           'kit_arguments': list(kit_arguments)})
    argv = command(values, scenario, directory, context_path=local_context, headless=False)
    with policy_backends(selected, values, context, local_context, directory) as backend_env:
        env.update(backend_env)
        if backend_env.get('ISAAC_HEALTHCARE_NAMESPACE'):
            argv.extend(['--namespace', backend_env['ISAAC_HEALTHCARE_NAMESPACE']])
        yield argv, env


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def _terminal_summary(log, selected):
    pattern = (re.escape(selected['workflow']) + r' \[' + re.escape(selected['mode']) +
               r'\] run=\S+: (\d+)/(\d+) episodes succeeded \((\d+) attempts\); (\d+) new demonstrations saved')
    matches = re.findall(pattern, log.read_text(errors='replace'))
    if not matches:
        raise RuntimeError('Simulator did not publish its normal terminal run summary; inspect operator diagnostics')
    success, requested, attempts, saved = map(int, matches[-1])
    return {'successful_episodes': success, 'requested_episodes': requested,
            'attempts': attempts, 'saved_demonstrations': saved, 'task_complete': success == requested}


def _archive(root, destination):
    inventory = {}
    with tarfile.open(destination, 'w') as archive:
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise RuntimeError('Scientific output contains an unexpected symlink')
            if path.is_file():
                name = path.relative_to(root).as_posix()
                inventory[name] = {'sha256': digest(path), 'size_bytes': path.stat().st_size}
                archive.add(path, arcname=name, recursive=False)
    return inventory


def curate_training(directory, operator, operation):
    """Retain diagnostic originals and rebuild inventory from delivered files."""
    source = directory / 'training-result.json'
    raw = json_loads(source.read_bytes())
    if (raw.get('operation') != operation or raw.get('status') != 'succeeded'
            or raw.get('scientific_execution') is not True or raw.get('engine_exit_code') != 0
            or raw.get('validation', {}).get('status') != 'validated'):
        raise RuntimeError('Training result is not a validated completed scientific execution')
    operator.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, operator / 'training-result.original.json')
    for name in raw.get('operator_diagnostics', []):
        relative = relative_path(name)
        path = directory.joinpath(*relative.parts)
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f'Declared training diagnostic is missing or invalid: {name}')
        destination = operator.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == '.log':
            with path.open(errors='replace') as log:
                for line in log:
                    sys.stdout.write(line)
            sys.stdout.flush()
        shutil.move(str(path), str(destination))
    scratch = directory / '.runtime'
    if scratch.exists():
        shutil.move(str(scratch), str(operator / 'runtime'))
    result = {key: value for key, value in raw.items() if key not in ('files', 'operator_diagnostics')}
    inventory = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Training scientific output contains a symlink')
        if path.is_file() and path != source:
            inventory[path.relative_to(directory).as_posix()] = {'sha256': digest(path), 'size_bytes': path.stat().st_size}
    result['files'] = inventory
    _write(source, result)
    return result


def run(input_path, parameter_values, output, *, operation='simulate', project_path=None):
    if operation not in OPERATIONS:
        raise ValueError(f'Unknown Isaac operation: {operation}')
    if input_path is None and project_path is None and operation != 'inspect':
        raise ValueError('Provide scenarios or a project archive for this operation')
    values = parameters(parameter_values)
    cases = scenarios(json_loads(input_path.read_bytes()), values['seed']) if input_path else [{'name': 'default', 'seed': values['seed']}]
    output.mkdir(parents=True, exist_ok=True)
    root, work = output / 'simulation', output / '.project'
    root.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    context = prepare_project(project_path, work, ROOT)
    resolved = apply_project_defaults(values, context)
    if operation in ('dataset-inspect', 'dataset-convert'):
        # Dataset tools do not create a simulator scene; an unrelated project
        # default workflow must not become a dependency of data preparation.
        resolved['workflow'] = None
    if operation == 'replay':
        if values['mode'] not in (None, 'replay'):
            raise ValueError('Replay operation requires the authored replay mode')
        resolved['mode'] = 'replay'
        if resolved['dataset'] is None:
            raise ValueError('Replay requires parameters.dataset relative to the project archive')
    if operation not in ('inspect', 'dataset-inspect', 'dataset-convert') and resolved['workflow'] is None:
        raise ValueError('Select workflow explicitly or set project.json default_workflow')
    context_path = work / 'context.json'
    _write(context_path, {'project': context, 'parameters': resolved})
    _write(root / 'request.json', {'operation': operation, 'parameters': values, 'scenarios': cases,
                                 'project_manifest': context['manifest']})
    if input_path is not None:
        # Retain the exact caller bytes, including whitespace, so completed
        # output recovery can independently reconstruct every requested case.
        (root / 'request').mkdir()
        shutil.copyfile(input_path, root / 'request/scenarios.json')
    provenance = {'project_files': context['inventory'], 'asset_generation': ASSET_GENERATION,
                  'base_sdk_revision': SOURCE, 'isaac_sim': '6.0.1'}
    for source, name in ((ASSET_MANIFEST, 'assets.json'), (PATCH_MANIFEST, 'upstream-patches.json')):
        if source.is_file():
            shutil.copyfile(source, root / name)
            provenance[name] = {'sha256': digest(source), 'size_bytes': source.stat().st_size}
    started = time.monotonic()
    inspect_dir = root / 'inspection'
    inspect_dir.mkdir()
    code, log = execute([str(PYTHON), '-I', '-m', 'isaac_healthcare_runtime.inspection',
                         '--context', str(context_path), '--output', str(inspect_dir / 'registry.json')],
                        inspect_dir, context=context)
    if code != 0:
        raise RuntimeError('Project discovery failed; inspect the full operator error for source or dependency details')
    discovery = json_loads((inspect_dir / 'registry.json').read_bytes())
    shutil.rmtree(inspect_dir / '.runtime')
    selected = discovery['selected']
    replay_mode = selected is not None and selected['mode'] == 'replay'
    if selected is not None:
        resolved['mode'] = selected['mode']
    if operation in ('simulate', 'replay') and replay_mode:
        # Batch cases retain separate artifacts for each selected recording.
        cases = [{**case, 'replay_episode': index} for case in cases for index in values['replay_episodes']]
        _write(root / 'request.json', {'operation': operation, 'parameters': values, 'scenarios': cases,
                                     'project_manifest': context['manifest']})
    provenance['resolved_sources'] = discovery['sources']
    provenance['selected_workflow'] = selected
    reports = []
    training = None
    if operation in ('simulate', 'replay'):
        if os.environ.get('ACCEPT_EULA') != 'Y' and os.environ.get('ISAACSIM_ACCEPT_EULA') != 'Y':
            raise ValueError('Set ACCEPT_EULA=Y only after accepting the NVIDIA Isaac Sim license')
        if selected is None or not all(key in selected for key in ('scene', 'mode', 'scene_step_cap', 'control_hz', 'sources', 'controller_modules')):
            raise RuntimeError('Upstream did not resolve the required scene/controller provenance')
        if not selected['lint']['ok']:
            raise ValueError('Upstream workflow lint failed; inspect simulation/inspection/registry.json')
        for index, case in enumerate(cases):
            directory = root / f'scenario-{index:06d}'
            directory.mkdir()
            case_values = dict(resolved)
            case_context = context_path
            if replay_mode:
                case_values['replay_episodes'] = [case['replay_episode']]
                case_context = work / f'context-{index:06d}.json'
                _write(case_context, {'project': context, 'parameters': case_values})
            argv = command(case_values, case, directory, context_path=case_context)
            begin = time.monotonic()
            with policy_backends(selected, case_values, context, case_context, directory) as backend_env:
                if backend_env.get('ISAAC_HEALTHCARE_NAMESPACE'):
                    argv.extend(['--namespace', backend_env['ISAAC_HEALTHCARE_NAMESPACE']])
                returncode, raw_log = execute(argv, directory, context=context, extra_env=backend_env)
            if returncode not in (0, 1):
                raise RuntimeError(f'Isaac scenario {index} exited {returncode}; full diagnostics are in the operator logs')
            terminal = _terminal_summary(raw_log, selected)
            recording = directory / 'demos.hdf5'
            if not recording.is_file():
                raise RuntimeError('Upstream did not close the requested HDF5 recording')
            checked_recording = validate_recording(recording, resolved, directory / 'previews', scene=selected)
            if (terminal['requested_episodes'] != resolved['episodes'] or
                    terminal['saved_demonstrations'] != len(checked_recording['episodes']) or
                    terminal['attempts'] > resolved['episodes'] * resolved['attempts'] or
                    checked_recording['successful_episodes'] > terminal['successful_episodes'] or
                    terminal['task_complete'] != (returncode == 0)):
                raise RuntimeError('Upstream terminal outcome and recording disagree')
            # Upstream can finish an immediate task without recording any step;
            # the terminal summary remains authoritative for those attempts.
            scientific = {'scenario': case, 'resolved': selected, 'terminal': terminal,
                          'recording': f'scenario-{index:06d}/demos.hdf5',
                          'simulation_seconds': time.monotonic() - begin,
                          **checked_recording, 'task_complete': terminal['task_complete']}
            _write(directory / 'workflow.json', scientific)
            reports.append(scientific)
            shutil.rmtree(directory / '.runtime')
    elif operation not in ('inspect', 'lint'):
        if operation in ('train', 'evaluate', 'export') and os.environ.get('ACCEPT_EULA') != 'Y' and os.environ.get('ISAACSIM_ACCEPT_EULA') != 'Y':
            raise ValueError('Set ACCEPT_EULA=Y only after accepting the NVIDIA Isaac Sim license')
        training_dir = root / 'training'
        training_dir.mkdir()
        request = work / 'training-parameters.json'
        _write(request, {**values, 'workflow': resolved['workflow'], 'mode': resolved['mode']})
        argv = [str(PYTHON), '-I', str(TRAINING_ENTRY), '--operation', operation,
                '--input-dir', context['project_dir'], '--sdk-root', context['effective_root'],
                '--output-dir', str(training_dir), '--parameters-file', str(request)]
        if resolved['workflow']:
            argv.extend(['--workflow', resolved['workflow']])
        for path in context['python_paths']:
            argv.extend(['--python-path', path])
        # The upstream tool inventories its output before returning. Keep Kit
        # caches/sockets outside that directory from the outset, not just when
        # curating the final customer archive.
        process_dir = output / '.operator/training-process'
        code, log = execute(argv, process_dir, context=context)
        if code != 0:
            diagnostic = training_dir / 'training-execution.log'
            if diagnostic.is_file():
                with diagnostic.open(errors='replace') as full_log:
                    for line in full_log:
                        sys.stdout.write(line)
                sys.stdout.flush()
            raise RuntimeError(f'Upstream {operation} failed; inspect full operator diagnostics')
        training = curate_training(training_dir, output / '.operator/training', operation)
    if operation == 'lint' and not selected['lint']['ok']:
        raise ValueError('Upstream workflow lint failed; inspect simulation/inspection/registry.json')
    elapsed = time.monotonic() - started
    task_complete = all(row['task_complete'] for row in reports) if reports else None
    sample_count = sum(row['samples'] for row in reports)
    _write(root / 'provenance.json', provenance)
    archive_path = output / 'simulation.tar'
    provenance['artifact_files'] = _archive(root, archive_path)
    result = {'schema': 'isaac-healthcare-result/v2', 'model_id': MODEL_ID, 'operation': operation,
              'parameters': values, 'input_sha256': digest(input_path) if input_path else None,
              'project_sha256': digest(project_path) if project_path else None,
              'source_revision': SOURCE, 'provenance': provenance, 'scenarios': reports,
              'task_complete': task_complete,
              'scientific_validation': 'not_applicable' if operation in ('inspect', 'lint') else 'passed',
              'capabilities': {'registry': discovery, 'qualification': 'Per-workload and operation; discovery is not simulation qualification'},
              'files': {'simulation.tar': {'sha256': digest(archive_path), 'size_bytes': archive_path.stat().st_size}},
              'runtime_metrics': {'elapsed_seconds': elapsed, 'samples_completed': sample_count,
                                  'samples_per_second': sample_count / elapsed if elapsed else None},
              'recording_semantics': 'Pinned upstream v1 records environment 0, omits the termination/reset sample, and may omit empty attempts. Scene and mode declare sensors/caps; task success is upstream predicate/terminal summary.'}
    if training is not None:
        result['training'] = training
    checked(result, schema('result'), 'result')
    _write(output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', required=True, choices=OPERATIONS)
    parser.add_argument('--input', type=Path, help='Optional scenarios JSON')
    parser.add_argument('--project', type=Path, help='Optional project TAR')
    parser.add_argument('--parameters-json', default='{}')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.input, json_loads(args.parameters_json), args.output_dir.resolve(),
                     operation=args.operation, project_path=args.project)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'Isaac healthcare {args.operation} failed: {error}\n')
    print(json.dumps({'result': str(args.output_dir / 'result.json'),
                      'operation': args.operation, 'task_complete': result['task_complete']}))


if __name__ == '__main__':
    main()
