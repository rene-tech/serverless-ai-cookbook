"""Write native MD timing reports from verified files, without inference or MD.

Use once after result recovery. Source receipts and artifacts are never changed;
the JSON/CSV/Markdown report has exact native rows, explicit unknowns and links.
"""
import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
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
    if engine == 'gromacs':
        return 'mdrun' in arguments
    if engine == 'amber':
        return command.get('kind') == 'pmemd'
    if engine == 'lammps':
        return bool(arguments)  # Each recorded command is a native input script.
    return bool(arguments) and Path(arguments[0]).name.lower().startswith('namd')


def positive(value):
    return type(value) in (float, int) and math.isfinite(value) and value > 0


def collect(folder, workspace, expected_repeats=None):
    receipt_path, receipt, documents = verified_md_inputs(folder, workspace)
    rows, gaps, sources = [], [], []
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
            previous.append(command)
    repeats = {(row['engine'], row['job_id'], row['step_id']) for row in rows}
    if not rows:
        gaps.append('No native simulation timing commands were recorded.')
    if expected_repeats is not None and len(repeats) != expected_repeats:
        gaps.append(f'Expected {expected_repeats} simulation steps/repeats, found {len(repeats)}.')
    return {'schema': 'scientific-ai/native-md-timing-report/v1',
        'operation_id': receipt['operation_id'], 'receipt_file': str(receipt_path),
        'complete': not gaps, 'expected_repeats': expected_repeats,
        'reported_repeats': len(repeats), 'timing_rows': rows, 'sources': sources, 'gaps': gaps,
        'limitations': [
            'Native command wall time includes process initialization/tuning and I/O; it is not queue time.',
            'Rows are execution segments, not independent scientific replicas; repeats require distinct step IDs.',
            'checkpoint_step is a recorded absolute checkpoint step, not an inferred useful-work count.',
            'Null step counts and other metrics are unknown, never zero. Requested steps are only explicit native settings.',
            'Simulation success and timing observations do not establish scientific equivalence, equilibration or convergence.',
        ]}


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
                'native-timing-report.md': markdown(report, workspace)}
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
