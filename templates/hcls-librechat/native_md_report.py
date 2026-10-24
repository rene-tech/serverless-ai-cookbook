"""Write native MD timing reports from verified files, without inference or MD.

Use once after result recovery. Source receipts and artifacts are never changed;
the JSON/CSV/Markdown report has exact native rows, explicit unknowns and links.
"""
import argparse
import csv
import html
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shlex

from scientific_verified_results import cell, link, verified_md_inputs, verify, within

FIELDS = ('engine', 'job_id', 'step_id', 'segment', 'exit_code', 'requested_steps',
          'executed_steps', 'durably_completed_steps', 'checkpoint_step',
          'performance_ns_per_day', 'wall_seconds', 'finished_at', 'command',
          'log_file', 'log_sha256', 'source_result_file', 'source_result_sha256')
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?'


def option(arguments, name):
    if name not in arguments:
        return None
    index = arguments.index(name) + 1
    return arguments[index] if index < len(arguments) else None


def requested_steps(engine, command, previous):
    """Only explicit native step counts; do not infer TPR settings from filenames."""
    if engine == 'openmm':
        value = command.get('requested_steps')
        return value if type(value) is int and value >= 0 else None
    if engine != 'gromacs':
        return None
    arguments = command['command']
    explicit = option(arguments, '-nsteps')
    if explicit is None:
        source = option(arguments, '-s')
        if source is None:
            return None
        candidates = [row for row in previous if 'convert-tpr' in row.get('command', [])
                      and row.get('directory', '.') == command.get('directory', '.')
                      and option(row['command'], '-o') == source]
        explicit = option(candidates[-1]['command'], '-nsteps') if candidates else None
    if explicit is None:
        return None
    try:
        value = int(explicit)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def is_simulation(engine, command):
    arguments = command.get('command', command.get('argv', []))
    if not isinstance(arguments, list) or not all(isinstance(value, str) for value in arguments):
        raise ValueError('Native command arguments must be recorded as a string list.')
    if engine == 'openmm':
        return command.get('kind') in ('equilibrate', 'production')
    if engine == 'gromacs':
        return 'mdrun' in arguments
    if engine == 'amber':
        completion = (command.get('validation') or {}).get('completion') or {}
        return command.get('kind') == 'pmemd' and completion.get('task') != 'minimize'
    if engine == 'lammps':
        return bool(arguments)  # Each recorded command is a native input script.
    return bool(arguments) and Path(arguments[0]).name.lower().startswith('namd')


def positive(value):
    return type(value) in (float, int) and math.isfinite(value) and value > 0


def measured(value):
    return value if type(value) in (float, int) and math.isfinite(value) and value >= 0 else None


def native_number(value):
    try:
        value = float(value.replace('D', 'E').replace('d', 'e'))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, AttributeError):
        return None


def gromacs_observations(path):
    """Read native samples separately from the later averages section."""
    values, first, last, sample = {}, None, None, None
    averages, starts = False, 0
    with path.open(errors='replace') as lines:
        for line in lines:
            if line.startswith('Started mdrun'):
                starts += 1
            if 'A V E R A G E S' in line or 'R M S' in line:
                averages = True
            if match := re.match(r'^\s*integrator\s*=\s*(\S+)', line):
                values['integrator'] = match[1]
            if match := re.match(rf'^\s*dt\s*=\s*({NUMBER})\s*$', line):
                values['timestep_ps'] = native_number(match[1])
            if match := re.match(r'^\s*nsteps\s*=\s*(\d+)\s*$', line):
                values['requested_steps'] = int(match[1])
            if match := re.match(r'^There are:\s*(\d+)\s+Atoms\s*$', line):
                values['atom_count'] = int(match[1])
            if not averages and re.fullmatch(r'\s*Step\s+Time\s*', line):
                sample = None
                fields = next(lines, '').split()
                if len(fields) == 2 and fields[0].isdigit() and native_number(fields[1]) is not None:
                    sample = int(fields[0]), native_number(fields[1])
                    first = first or sample
                    last = sample
            columns = re.split(r'\s{2,}', line.strip())
            if not averages and sample and 'Temperature' in columns:
                fields = next(lines, '').split()
                for key in ('temperature_k', 'temperature_step', 'temperature_time_ps'):
                    values.pop(key, None)
                if len(fields) == len(columns):
                    temperature = native_number(fields[columns.index('Temperature')])
                    if positive(temperature):
                        values.update(temperature_k=temperature, temperature_step=sample[0],
                                      temperature_time_ps=sample[1])
            if match := re.match(rf'^\s*Time:\s+({NUMBER})\s+({NUMBER})\s+', line):
                values['native_run_seconds'] = measured(native_number(match[2]))
                values['native_run_timing_scope'] = 'GROMACS native Wall t accounting; includes timed I/O, not isolated integration or total operation time.'
    if starts > 1:
        return {}  # An appended log cannot be attributed to one command here.
    if not positive(values.get('timestep_ps')):
        values.pop('timestep_ps', None)
    if first and last and last[0] >= first[0] and last[1] >= first[1]:
        values.update(initial_step=first[0], final_step=last[0], simulation_time_ps=last[1],
                      executed_steps=last[0] - first[0],
                      segment_physical_time_ps=last[1] - first[1])
    return values


def amber_observations(path):
    """PMEMD periodic temperatures and the all-steps performance interval."""
    values, averages, all_steps = {}, False, False
    with path.open(errors='replace') as lines:
        for line in lines:
            if 'A V E R A G E S' in line or 'R M S  F L U C T U A T I O N S' in line:
                averages = True
            if not averages and (match := re.search(
                    rf'NSTEP\s*=\s*(\d+)\s+TIME\(PS\)\s*=\s*({NUMBER})\s+TEMP\(K\)\s*=\s*({NUMBER})', line)):
                temperature, time = native_number(match[3]), native_number(match[2])
                if positive(temperature) and time is not None:
                    values.update(temperature_k=temperature, temperature_step=int(match[1]),
                                  temperature_time_ps=time)
            if 'Average timings for' in line:
                all_steps = 'Average timings for all steps:' in line
            if all_steps and (match := re.search(rf'Elapsed\(s\)\s*=\s*({NUMBER})', line)):
                values['native_run_seconds'] = measured(native_number(match[1]))
                values['native_run_timing_scope'] = 'AMBER Final Performance Info: elapsed for all steps; not an isolated integration timer or total operation time.'
            if all_steps and (match := re.search(rf'ns/day\s*=\s*({NUMBER})', line)):
                values['performance_ns_per_day'] = native_number(match[1])
                all_steps = False
    return values


def lammps_observations(path):
    """Read the native table/multi thermo sample and completed dynamics loops."""
    values, columns, sample, style = {}, None, None, None
    dynamic, seconds, counts = False, [], []
    intervals, timesteps = [], []
    first_time = last_time = start = dt = None
    clock_ambiguous = adaptive = False

    time_units = {'real': .001, 'metal': 1, 'si': 1e12, 'cgs': 1e12,
                  'electron': .001, 'micro': 1e6, 'nano': 1e3}

    def temperature(value, step, time=None):
        # Reduced LJ temperatures have no Kelvin scale supplied by this log.
        if style in ('real', 'metal', 'si', 'cgs', 'electron', 'micro', 'nano') and positive(value):
            values.update(temperature_k=value, temperature_step=step, temperature_time_ps=time)

    with path.open(errors='replace') as lines:
        for line in lines:
            adaptive |= bool(re.search(r'\bdt/reset\b', line))
            if line.startswith('Setting up '):
                dynamic = bool(re.match(r'^Setting up (?:Verlet|rRESPA) run', line))
                columns = sample = style = first_time = last_time = start = dt = None
                clock_ambiguous = False
            if match := re.match(r'\s*Unit style\s*:\s*(\w+)\s*$', line):
                style = match[1]
            if not dynamic:
                continue
            if match := re.match(r'\s*Current step\s*:\s*(\d+)\s*$', line):
                start = int(match[1])
            if match := re.match(rf'\s*Time step\s*:\s*({NUMBER})\s*$', line):
                dt = native_number(match[1])
            fields = line.split()
            if 'Step' in fields and ('Temp' in fields or 'Time' in fields):
                columns = fields
            elif columns and len(fields) == len(columns):
                row = [native_number(field) for field in fields]
                step = row[columns.index('Step')]
                if all(value is not None for value in row) and measured(step) is not None and step.is_integer():
                    time = row[columns.index('Time')] * time_units[style] if 'Time' in columns and style in time_units else None
                    if time is not None:
                        values['simulation_time_ps'] = time
                        clock_ambiguous |= last_time is not None and (step < last_time[0] or time < last_time[1])
                        first_time = first_time or (step, time)
                        last_time = step, time
                    if 'Temp' in columns:
                        temperature(row[columns.index('Temp')], int(step), time)
            if match := re.match(r'^-+\s+Step\s+(\d+)\s+-+\s+CPU\s*=', line):
                sample = int(match[1])
                columns = None
            if sample is not None and (match := re.search(rf'\bTemp\s*=\s*({NUMBER})', line)):
                temperature(native_number(match[1]), sample)
            if match := re.search(rf'Loop time of\s+({NUMBER})\s+on\s+\d+\s+procs for\s+(\d+)\s+steps with\s+(\d+)\s+atoms', line):
                value = measured(native_number(match[1]))
                if value is not None:
                    seconds.append(value)
                count = int(match[2])
                counts.append(count)
                intervals.append(last_time[1] - first_time[1] if first_time and last_time
                    and not clock_ambiguous and last_time[0] - first_time[0] == count
                    and (start is None or first_time[0] == start) else None)
                timesteps.append(dt * time_units[style] if positive(dt) and style in time_units
                                 and not clock_ambiguous else None)
                values['atom_count'] = int(match[3])
                dynamic = False
    if seconds:
        values.update(native_run_seconds=sum(seconds),
                      native_run_timing_scope='LAMMPS completed dynamics Loop times; includes timed I/O, not an isolated integration timer or total operation time.')
    if counts:
        values.update(executed_steps=sum(counts),
                      step_count_scope='Sum of completed native dynamics Loop step counts; no requested target or durability is inferred.')
        if all(value is not None for value in intervals):
            values['segment_physical_time_ps'] = sum(intervals)
        elif not adaptive and None not in timesteps and len(set(timesteps)) == 1:
            values['segment_physical_time_ps'] = sum(counts) * timesteps[0]
    return values


def native_observations(engine, command, files):
    """Project measured result fields, adding only command-associated native logs."""
    values, sources, notes = {}, [], []
    arguments = command.get('command', command.get('argv', []))

    def read(name, parser):
        path, entry = files.get(name, (None, None))
        if path is None:
            return None
        verify(path, entry)
        sources.append({'path': str(path), 'sha256': entry['sha256']})
        parsed = parser(path)
        if parsed.get('temperature_k') is not None:
            parsed.update(temperature_file=str(path), temperature_sha256=entry['sha256'],
                          temperature_source='verified native log')
        return parsed

    if engine == 'gromacs':
        base = PurePosixPath(command.get('directory', '.')) / (option(arguments, '-g') or
            (option(arguments, '-deffnm') or 'md') + '.log')
        if not base.suffix:
            base = base.with_suffix('.log')
        pattern = re.compile(re.escape(base.stem) + r'(?:\.part\d+)?' + re.escape(base.suffix))
        candidates = []
        for name in files:
            path = PurePosixPath(name)
            if path.parent == base.parent and pattern.fullmatch(path.name):
                candidate = read(name, gromacs_observations)
                if candidate and (command.get('checkpoint_step') is None or
                                  candidate.get('final_step') == command['checkpoint_step']):
                    candidates.append(candidate)
        if len(candidates) == 1:
            values.update(candidates[0])
            dynamics = values.pop('integrator', None) in ('md', 'md-vv', 'md-vv-avek', 'sd', 'bd') and '-rerun' not in arguments
            if not dynamics:
                for key in ('executed_steps', 'segment_physical_time_ps'):
                    values.pop(key, None)
            else:
                values['step_count_scope'] = 'Observed native Step/Time interval; requested steps and any work outside that interval are not substituted.'
        else:
            notes.append('No unique command-associated GROMACS observation log; scientific observations remain unknown.')
    elif engine == 'namd':
        dynamics = command.get('observed_dynamics') or {}
        values.update(atom_count=measured(command.get('atoms')),
                      initial_step=measured(dynamics.get('initial_step')),
                      final_step=measured(command.get('last_output_step')),
                      timestep_ps=measured(dynamics.get('timestep_ps')),
                      performance_ns_per_day=measured(dynamics.get('ns_per_day')))
        if values['timestep_ps'] is None and positive(command.get('timestep_fs')):
            values['timestep_ps'] = command['timestep_fs'] / 1000
        first, last, dt = values['initial_step'], values['final_step'], values['timestep_ps']
        if first is not None and last is not None and last >= first:
            values['executed_steps'] = last - first
            values['step_count_scope'] = 'Interval from the native observed dynamics baseline to the final native output step; no requested target or durability is inferred.'
        if last is not None and positive(dt):
            values['simulation_time_ps'] = last * dt
        energy = command.get('last_energy') or {}
        if positive(energy.get('TEMP')) and measured(energy.get('TS')) is not None:
            path, entry = files.get(command.get('log'), (None, None))
            values.update(temperature_k=energy['TEMP'], temperature_step=energy['TS'],
                          temperature_time_ps=energy['TS'] * dt if positive(dt) else None,
                          temperature_file=str(path) if path else None,
                          temperature_sha256=entry['sha256'] if entry else None,
                          temperature_source='native log measurement recorded in the verified result')
        def timing(path):
            found = {}
            with path.open(errors='replace') as lines:
                for line in lines:
                    if match := re.match(rf'^TIMING:\s*(\d+)\s+.*?Wall:\s*({NUMBER}),', line):
                        found = {'native_run_seconds': measured(native_number(match[2])),
                                 'native_run_timing_scope': f'NAMD TIMING Wall counter at step {match[1]}; not an isolated integration timer or total operation time.'}
            return found
        values.update(read(command.get('log'), timing) or {})
    elif engine == 'amber':
        completion = (command.get('validation') or {}).get('completion') or {}
        if completion.get('task') == 'dynamics' and completion.get('native_completion') is True:
            values.update(atom_count=measured(completion.get('natom')),
                          final_step=measured(completion.get('completed_native_steps')),
                          executed_steps=measured(completion.get('completed_native_steps')),
                          requested_steps=measured(completion.get('nstlim')),
                          simulation_time_ps=measured(completion.get('final_time_ps')),
                          timestep_ps=measured(completion.get('dt_ps')),
                          step_count_scope='Completed native PMEMD NSTEP count for this command; the simulation clock may include earlier runs.')
        name = str(PurePosixPath(command.get('directory', '.')) / (option(arguments, '-o') or 'mdout'))
        values.update(read(name, amber_observations) or {})
    elif engine == 'lammps':
        dynamics = command.get('observed_dynamics') or {}
        values.update(initial_step=measured(dynamics.get('initial_step')),
                      final_step=measured(dynamics.get('observed_step')),
                      timestep_ps=measured(dynamics.get('timestep_ps')),
                      performance_ns_per_day=measured(dynamics.get('ns_per_day')))
        values.update(read(command.get('log'), lammps_observations) or {})
        first, last, dt = values['initial_step'], values['final_step'], values['timestep_ps']
        if 'executed_steps' not in values and first is not None and last is not None and last >= first and positive(dt):
            values.update(executed_steps=last - first,
                          step_count_scope='Native observed dynamics interval; no requested target or durability is inferred.')
        # A timestep number alone does not establish the LAMMPS simulation
        # clock: reset_timestep and variable timesteps can offset it.
        notes.append('LAMMPS simulation-clock values use explicit Time fields. Segment duration uses complete per-loop Time intervals or a constant native timestep recorded for every completed loop; the final timestep alone is insufficient.')
    values['measurement_sources'], values['notes'] = sources, notes
    return values


def observations(engine, command, files):
    """Read published segment measurements, never substitute requested targets."""
    validation = command.get('validation') or {}
    scientific = validation.get('scientific') or {}
    values = {key: measured(validation.get(key)) for key in
              ('initial_step', 'final_step', 'simulation_time_ps', 'timestep_ps',
               'integration_seconds', 'setup_seconds')}
    values['atom_count'] = measured(scientific.get('particles'))
    executed = measured(command.get('executed_steps'))
    values['segment_physical_time_ps'] = (executed * values['timestep_ps']
        if engine != 'lammps' and executed is not None and values['timestep_ps'] is not None else None)
    values.update(temperature_k=None, temperature_step=None, temperature_time_ps=None,
                  temperature_file=None, temperature_sha256=None)
    # OpenMM's documented StateDataReporter CSV is an observation at its own
    # cadence. The last sample need not coincide with the final segment step.
    if engine == 'openmm' and type(command.get('segment')) is int:
        name = f"openmm-output/{command['step_id']}/segment-{command['segment']:06d}/state.csv"
        path, entry = files.get(name, (None, None))
        if path is not None:
            verify(path, entry)
            with path.open(newline='') as stream:
                header = next(stream, '').removeprefix('#')
                reader = csv.DictReader(stream, fieldnames=next(csv.reader([header]), []))
                last = None
                for last in reader:
                    pass
            if last:
                try:
                    temperature = float(last['Temperature (K)'])
                    step, time = int(last['Step']), float(last['Time (ps)'])
                    if not positive(temperature) or measured(step) is None or measured(time) is None:
                        raise ValueError('Invalid recorded temperature observation.')
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError('Invalid verified OpenMM state CSV: ' + name) from exc
                values.update(temperature_k=temperature, temperature_step=step,
                              temperature_time_ps=time, temperature_file=str(path),
                              temperature_sha256=entry['sha256'])
    if engine != 'openmm':
        native = native_observations(engine, command, files)
        values.update({key: value for key, value in native.items() if value is not None})
        executed = measured(command.get('executed_steps'))
        if executed is None:
            executed = measured(values.get('executed_steps'))
        if engine != 'lammps' and values.get('segment_physical_time_ps') is None and executed is not None and positive(values['timestep_ps']):
            values['segment_physical_time_ps'] = executed * values['timestep_ps']
    return values


def collect(folder, workspace, expected_repeats=None):
    receipt_path, receipt, documents = verified_md_inputs(folder, workspace)
    rows, gaps, sources, science = [], [], [], []
    for document in documents:
        engine, result, files = document['engine'], document['result'], document['files']
        source = document['source']
        sources.append({'engine': engine, 'job_id': result.get('job_id'),
                        'path': source['path'], 'sha256': source['sha256']})
        if result.get('inventory_complete', True) is not True:
            raise ValueError('Native output inventory is incomplete; preserve its diagnostics.')
        previous = []
        for command in result.get('commands', []):
            if not is_simulation(engine, command):
                previous.append(command)
                continue
            step = command.get('step_id')
            if step not in result.get('completed_steps', []):
                gaps.append(f'{result.get("job_id")}/{step}: not a completed native step')
            if command.get('exit_code') != 0:
                gaps.append(f'{result.get("job_id")}/{step}: command did not exit successfully')
            native_log = command.get('log')
            path, entry = files.get(native_log, (None, None))
            if path is None:
                gaps.append(f'{result.get("job_id")}/{step}: source log not materialized')
            else:
                verify(path, entry)
            observed = observations(engine, command, files)
            performance = command.get('performance_ns_per_day')
            if not positive(performance):
                performance = observed.get('performance_ns_per_day')
            for field, value in [('performance_ns_per_day', performance), ('wall_seconds', command.get('wall_seconds'))]:
                if not positive(value):
                    gaps.append(f'{result.get("job_id")}/{step}: {field} unknown or invalid')
            requested = requested_steps(engine, command, previous)
            executed = measured(command.get('executed_steps'))
            rows.append({'engine': engine, 'job_id': result.get('job_id'), 'step_id': step,
                'segment': command.get('segment'), 'exit_code': command.get('exit_code'),
                'requested_steps': requested if requested is not None else observed.get('requested_steps'),
                'executed_steps': executed if executed is not None else observed.get('executed_steps'),
                'durably_completed_steps': command.get('durably_completed_steps'),
                'checkpoint_step': command.get('checkpoint_step'),
                'performance_ns_per_day': performance if positive(performance) else None,
                'wall_seconds': command.get('wall_seconds') if positive(command.get('wall_seconds')) else None,
                'finished_at': command.get('finished_at'),
                'command': command.get('command', command.get('argv')), 'log_file': str(path) if path else None,
                'log_sha256': entry['sha256'] if entry else None,
                'source_result_file': source['path'], 'source_result_sha256': source['sha256']})
            science.append(observed)
            previous.append(command)
    repeats = {(row['engine'], row['job_id'], row['step_id']) for row in rows}
    if not rows:
        gaps.append('No native simulation timing commands were recorded.')
    if expected_repeats is not None and len(repeats) != expected_repeats:
        gaps.append(f'Expected {expected_repeats} simulation steps/repeats, found {len(repeats)}.')
    return {'schema': 'scientific-ai/native-md-timing-report/v1',
        'operation_id': receipt['operation_id'], 'receipt_file': str(receipt_path),
        'complete': not gaps, 'expected_repeats': expected_repeats,
        'completeness_scope': 'Native timing evidence; not completeness of every requested scientific analysis.',
        'reported_repeats': len(repeats), 'timing_rows': rows, 'observations': science,
        'sources': sources, 'gaps': gaps,
        'limitations': [
            'Native command wall time includes process initialization/tuning and I/O; it is not queue time.',
            'Rows are execution segments, not independent scientific replicas; repeats require distinct step IDs.',
            'checkpoint_step is a recorded absolute checkpoint step, not an inferred useful-work count.',
            'Null step counts and other metrics are unknown, never zero. Requested steps are only explicit native settings.',
            'Simulation success and timing observations do not establish scientific equivalence, equilibration or convergence.',
        ]}


def html_report(report, workspace, structure_html=None):
    """A scientific summary, optionally in the existing interactive viewer page."""
    escape = lambda value: html.escape(str(value), quote=True)
    display = lambda value: 'unknown' if value is None else escape(f'{value:.9g}' if isinstance(value, float) else value)
    title = 'Native MD report — ' + report['operation_id']
    parts = [f'<section id="native-md-summary"><h1>{escape(title)}</h1>',
             '<p>Read-only analysis of hash-verified retained results. No simulation was submitted.</p>',
             '<h2>Observed scientific results</h2>']
    for row, observed in zip(report['timing_rows'], report['observations']):
        parts.append('<h3>' + escape(' / '.join(str(row[key]) for key in
                     ('engine', 'step_id', 'segment'))) + '</h3><dl>')
        for label, value in [
            ('Observed atom count (native particle count)' if row['engine'] == 'openmm' else
             'Native reported atom count', observed['atom_count']),
            ('Observed segment steps (native evidence)' if observed.get('step_count_scope') else
             'Completed segment steps (recorded executed steps)', row['executed_steps']),
            ('Durably completed segment steps', row['durably_completed_steps']),
            ('Initial step', observed['initial_step']),
            ('Final step' if row['engine'] == 'openmm' else 'Last observed step', observed['final_step']),
            ('Segment physical time (ps)', observed['segment_physical_time_ps']),
            ('Final simulation clock (ps; may include earlier segments)' if row['engine'] == 'openmm' else
             'Observed simulation clock (ps; may include earlier segments)', observed['simulation_time_ps']),
            ('Timestep (ps)', observed['timestep_ps']),
            ('Last reported temperature (K)', observed['temperature_k']),
            ('Temperature observation step', observed['temperature_step']),
            ('Temperature observation time (ps)', observed['temperature_time_ps']),
            ('Integration rate (ns/day)' if row['engine'] == 'openmm' else 'Native rate (ns/day)', row['performance_ns_per_day']),
            ('Integration time (s)', observed['integration_seconds']),
            ('Engine setup time (s)', observed['setup_seconds']),
            ('Native command wall time (s)', row['wall_seconds']),
        ]:
            parts.append(f'<dt>{escape(label)}</dt><dd>{display(value)}</dd>')
        if observed.get('native_run_seconds') is not None:
            parts.append(f'<dt>Native reported run time (s)</dt><dd>{display(observed["native_run_seconds"])}</dd>')
        parts.append('</dl>')
        if observed['temperature_file']:
            interpretation = ('This is a sampled observation, not an ensemble mean; it is final only when its step matches the final step.'
                              if row['engine'] == 'openmm' else
                              'This is a sampled observation, not an ensemble mean. Compare its step/time with native completion evidence before treating it as final.')
            parts.append(f'<p>Temperature source: <a href="{escape(link(Path(observed["temperature_file"]), workspace))}">'
                         f'{escape(observed.get("temperature_source", "verified state CSV"))}</a>; SHA-256 <code>{observed["temperature_sha256"]}</code>. '
                         + interpretation + '</p>')
        for key in ('step_count_scope', 'native_run_timing_scope'):
            if observed.get(key):
                parts.append(f'<p>{escape(observed[key])}</p>')
        for source in observed.get('measurement_sources', []):
            parts.append(f'<p><a href="{escape(link(Path(source["path"]), workspace))}">Verified native observation source</a>; '
                         f'SHA-256 <code>{escape(source["sha256"])}</code>.</p>')
        parts.extend(f'<p>{escape(note)}</p>' for note in observed.get('notes', []))
    parts += ['<h2>Timing boundaries and unavailable evidence</h2>',
              '<p>Queue time: unknown. Worker startup time: unknown. Checkpoint/export time: unknown. '
              'Total operation elapsed time: unknown. These intervals are not measured by this native report. '
              'Command wall time includes setup and I/O; engine setup and integration are separately recorded intervals. '
              'Do not add them to command wall time or treat command time as total operation elapsed time.</p>',
              '<p>Unknown values are missing measurements, not zero. The simulation clock is cumulative; '
              + ('segment physical time uses recorded executed steps × timestep. ' if all(row['engine'] == 'openmm' for row in report['timing_rows']) else
                 'segment physical time uses observed segment step/time evidence, not requested targets. ')
              + 'Do not sum cumulative clocks or count resumed segments as independent replicas.</p>',
              '<h2>Provenance and limitations</h2>',
              f'<p>Operation: <code>{escape(report["operation_id"])}</code>. Native timing evidence: '
              f'{"complete" if report["complete"] else "incomplete"}. This is not a claim of equilibration, convergence or completeness of additional requested analyses.</p>',
              f'<p><a href="{escape(link(Path(report["receipt_file"]), workspace))}">Verified recovery/publication receipt</a></p><ul>']
    for source in report['sources']:
        parts.append(f'<li><a href="{escape(link(Path(source["path"]), workspace))}">{escape(source["engine"])} native result</a>; '
                     f'SHA-256 <code>{escape(source["sha256"])}</code></li>')
    parts += ['</ul>', *[f'<p>Missing timing evidence: {escape(gap)}</p>' for gap in report['gaps']],
              '<h2>Structure preview</h2>', '<p>Final coordinates only; not a trajectory movie or proof of scientific validity.</p>'
              if structure_html else '<p>Not included in this report. Request the optional verified final-coordinate preview if needed.</p>', '</section>']
    section = ''.join(parts)
    style = '<style>#native-md-summary{font:15px/1.5 system-ui,sans-serif;padding:20px;color:#14213d;background:#fff;overflow-wrap:anywhere}#native-md-summary h1{font-size:22px}#native-md-summary h2{font-size:18px;margin-top:24px}#native-md-summary dl{display:grid;grid-template-columns:minmax(180px,2fr) minmax(80px,1fr);gap:6px 16px}#native-md-summary dd{margin:0;font-variant-numeric:tabular-nums}</style>'
    if structure_html:
        if '<body>' not in structure_html or '</head>' not in structure_html:
            raise ValueError('Expected the installed complete structure viewer document.')
        document = re.sub(r'<title>.*?</title>', lambda _: f'<title>{escape(title)}</title>', structure_html, count=1, flags=re.S)
        return document.replace('</head>', style + '</head>', 1).replace('<body>', '<body>' + section, 1)
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)}</title>{style}</head><body>{section}</body></html>'


def markdown(report, workspace):
    lines = ['# Native MD timing report', '', f"Operation: `{report['operation_id']}`.",
             f"Timing report: {'complete' if report['complete'] else 'incomplete'}; "
             f"{report['reported_repeats']} simulation steps/repeats, {len(report['timing_rows'])} segments.", '',
             '| Engine / job / step / segment | ns/day | Command wall (s) | Requested steps | Checkpoint step | Source log |',
             '| --- | ---: | ---: | ---: | ---: | --- |']
    def measured(value):
        return 'unknown' if value is None else cell(value)
    for row in report['timing_rows']:
        identity = ' / '.join(measured(row[key]) for key in ('engine', 'job_id', 'step_id', 'segment'))
        source = (f"[{cell(Path(row['log_file']).name)}]({link(Path(row['log_file']), workspace)}) "
                  f"(SHA-256 `{row['log_sha256']}`)") if row['log_file'] else 'unknown'
        lines.append(f"| {identity} | {measured(row['performance_ns_per_day'])} | {measured(row['wall_seconds'])} | "
                     f"{measured(row['requested_steps'])} | {measured(row['checkpoint_step'])} | {source} |")
    lines += ['', '## Exact native commands', '']
    for row in report['timing_rows']:
        lines += [f"### {cell(row['job_id'])} / {cell(row['step_id'])} / segment {cell(row['segment'])}", '',
                  '```text', shlex.join(row['command']), '```', '']
    lines += ['## Provenance and limitations', '',
              f"- [Original publication receipt]({link(Path(report['receipt_file']), workspace)})"]
    for source in report['sources']:
        lines.append(f"- [{cell(source['engine'])} / {cell(source['job_id'])} native result]"
                     f"({link(Path(source['path']), workspace)}), SHA-256 `{source['sha256']}`.")
    lines += ['- ' + note for note in report['limitations']]
    if report['gaps']:
        lines += ['', '## Missing evidence', '', *['- ' + gap for gap in report['gaps']]]
    return '\n'.join(lines) + '\n'


def customer_summary(report, workspace):
    """Project typed observations; never substitute a first sample or mean."""
    lines = [f"Operation: `{cell(report['operation_id'])}`.", '',
        'Verified native observations; missing measurements are unknown. '
        'Last reported temperature is a sample, not an ensemble mean or necessarily the endpoint.', '']
    for row, observed in zip(report['timing_rows'], report['observations']):
        lines += ['### ' + ' / '.join(cell(row[key]) for key in ('engine', 'step_id', 'segment')), '',
                  '| Observation | Value |', '| --- | --- |']
        values = [
            ('Native atom/particle count', observed['atom_count']),
            ('Observed executed segment steps', row['executed_steps']),
            ('Last observed step', observed['final_step']),
            ('Segment physical time (ps)', observed['segment_physical_time_ps']),
            ('Observed simulation clock (ps; cumulative)', observed['simulation_time_ps']),
            ('Last reported temperature (K)', observed['temperature_k']),
            ('Temperature observation step', observed['temperature_step']),
            ('Temperature observation time (ps)', observed['temperature_time_ps']),
            ('Native rate (ns/day)', row['performance_ns_per_day']),
            ('Integration time (s)', observed['integration_seconds']),
            ('Native reported run time (s)', observed.get('native_run_seconds')),
            ('Native command wall time (s; includes setup and I/O)', row['wall_seconds'])]
        lines += [f'| {label} | {cell(value) if value is not None else "unknown"} |' for label, value in values]
        if observed['temperature_file']:
            lines += ['', f"[Temperature evidence]({link(Path(observed['temperature_file']), workspace)}); "
                      f"SHA-256 `{observed['temperature_sha256']}`."]
        lines += ['', *[str(observed[key]) for key in ('step_count_scope', 'native_run_timing_scope')
                       if observed.get(key)], '']
    lines += [f"[Verified publication receipt]({link(Path(report['receipt_file']), workspace)})", '',
              'No mean or total operation elapsed time is derived here. Segment clocks and command times '
              'must not be summed into a run mean or end-to-end time. No new model work was submitted.']
    return {'schema': 'scientific-study-summary/v1', 'kind': 'native-md',
            'operation_id': report['operation_id'], 'text': '\n'.join(lines) + '\n',
            'inference_submitted': False}


def verified_summary(data, workspace):
    """Recheck typed facts against the same receipt and small source files.

    Trajectory hashes remain those of the original verified recovery; no large
    artifact download or repeated full-trajectory hashing is performed here.
    """
    report = json.loads(data)
    if not isinstance(report, dict) or report.get('schema') != 'scientific-ai/native-md-timing-report/v1':
        raise ValueError('Expected a native-md-timing typed report, not a handwritten summary.')
    receipt = within(Path(report['receipt_file']), workspace)
    measured = collect(receipt.parent, workspace, report.get('expected_repeats'))
    if report != measured or not measured['complete']:
        raise ValueError('Typed MD report differs from verified native observations or is incomplete.')
    return customer_summary(measured, workspace)


def write_report(folder, output, workspace, expected_repeats=None, *, publication_directory=None):
    if expected_repeats is not None and expected_repeats < 1:
        raise ValueError('Expected repeats must be positive when supplied.')
    report = collect(folder, workspace, expected_repeats)
    csv_buffer = io.StringIO(newline='')
    writer = csv.DictWriter(csv_buffer, fieldnames=FIELDS)
    writer.writeheader()
    for row in report['timing_rows']:
        writer.writerow({**row, 'command': shlex.join(row['command'])})
    rendered = {'native-timing-report.json': json.dumps(report, indent=2) + '\n',
                'native-timings.csv': csv_buffer.getvalue(),
                'native-timing-report.md': markdown(report, workspace),
                'native-md-report.html': html_report(report, workspace)}
    if report['complete']:
        summary = customer_summary(report, workspace)
        summary['text'] += '\n[Native MD report](' + link((publication_directory or output) / 'native-md-report.html', workspace) + ')\n'
        rendered['customer-summary.json'] = json.dumps(summary, indent=2) + '\n'
    # Reports are deterministic and safely reusable. Never overwrite an earlier
    # report from different source bytes/expectations or touch native receipts.
    for name, value in rendered.items():
        target = output / name
        if target.exists() and target.read_bytes() != value.encode():
            raise ValueError('Existing report differs; choose a new output directory: ' + name)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in rendered.items():
        target = output / name
        if not target.exists():
            with target.open('x') as handle:
                handle.write(value)
    return {'schema': report['schema'], 'complete': report['complete'],
            'operation_id': report['operation_id'], 'reported_repeats': report['reported_repeats'],
            'timing_row_count': len(report['timing_rows']), 'gaps': report['gaps'],
            'files': [{'path': str((publication_directory or output) / name),
                       'workspace_url': link((publication_directory or output) / name, workspace)} for name in rendered],
            'inference_submitted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(os.environ.get('WORKSPACE', '/workspace')))
    parser.add_argument('--receipt-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expected-repeats', type=int,
                        help='Requested simulation-step count, not the number of resumed segments.')
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    result = write_report(within(args.receipt_dir, workspace), within(args.output_dir, workspace),
                          workspace, args.expected_repeats)
    print(json.dumps(result))
    raise SystemExit(0 if result['complete'] else 2)


if __name__ == '__main__':
    main()
