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
from pathlib import Path
import re
import shlex

from scientific_verified_results import cell, link, verified_md_inputs, verify, within

FIELDS = ('engine', 'job_id', 'step_id', 'segment', 'exit_code', 'requested_steps',
          'executed_steps', 'durably_completed_steps', 'checkpoint_step',
          'performance_ns_per_day', 'wall_seconds', 'finished_at', 'command',
          'log_file', 'log_sha256', 'source_result_file', 'source_result_sha256')


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
        return command.get('kind') == 'pmemd'
    if engine == 'lammps':
        return bool(arguments)  # Each recorded command is a native input script.
    return bool(arguments) and Path(arguments[0]).name.lower().startswith('namd')


def positive(value):
    return type(value) in (float, int) and math.isfinite(value) and value > 0


def measured(value):
    return value if type(value) in (float, int) and math.isfinite(value) and value >= 0 else None


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
        if executed is not None and values['timestep_ps'] is not None else None)
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
            for field in ('performance_ns_per_day', 'wall_seconds'):
                if not positive(command.get(field)):
                    gaps.append(f'{result.get("job_id")}/{step}: {field} unknown or invalid')
            if command.get('exit_code') != 0:
                gaps.append(f'{result.get("job_id")}/{step}: command did not exit successfully')
            native_log = command.get('log')
            path, entry = files.get(native_log, (None, None))
            if path is None:
                gaps.append(f'{result.get("job_id")}/{step}: source log not materialized')
            else:
                verify(path, entry)
            rows.append({'engine': engine, 'job_id': result.get('job_id'), 'step_id': step,
                'segment': command.get('segment'), 'exit_code': command.get('exit_code'),
                'requested_steps': requested_steps(engine, command, previous),
                'executed_steps': command.get('executed_steps'),
                'durably_completed_steps': command.get('durably_completed_steps'),
                'checkpoint_step': command.get('checkpoint_step'),
                'performance_ns_per_day': command.get('performance_ns_per_day') if positive(command.get('performance_ns_per_day')) else None,
                'wall_seconds': command.get('wall_seconds') if positive(command.get('wall_seconds')) else None,
                'finished_at': command.get('finished_at'),
                'command': command.get('command', command.get('argv')), 'log_file': str(path) if path else None,
                'log_sha256': entry['sha256'] if entry else None,
                'source_result_file': source['path'], 'source_result_sha256': source['sha256']})
            science.append(observations(engine, command, files))
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
            ('Observed atom count (native particle count)', observed['atom_count']),
            ('Completed segment steps (recorded executed steps)', row['executed_steps']),
            ('Durably completed segment steps', row['durably_completed_steps']),
            ('Initial step', observed['initial_step']), ('Final step', observed['final_step']),
            ('Segment physical time (ps)', observed['segment_physical_time_ps']),
            ('Final simulation clock (ps; may include earlier segments)', observed['simulation_time_ps']),
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
        parts.append('</dl>')
        if observed['temperature_file']:
            parts.append(f'<p>Temperature source: <a href="{escape(link(Path(observed["temperature_file"]), workspace))}">'
                         f'verified state CSV</a>; SHA-256 <code>{observed["temperature_sha256"]}</code>. '
                         'This is a sampled observation, not an ensemble mean; it is final only when its step matches the final step.</p>')
    parts += ['<h2>Timing boundaries and unavailable evidence</h2>',
              '<p>Queue time: unknown. Worker startup time: unknown. Checkpoint/export time: unknown. '
              'Total operation elapsed time: unknown. These intervals are not measured by this native report. '
              'Command wall time includes setup and I/O; engine setup and integration are separately recorded intervals. '
              'Do not add them to command wall time or treat command time as total operation elapsed time.</p>',
              '<p>Unknown values are missing measurements, not zero. The simulation clock is cumulative; '
              'segment physical time uses recorded executed steps × timestep. Do not sum cumulative clocks or count resumed segments as independent replicas.</p>',
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
