#!/usr/bin/env python3
"""Dedicated-user whole-study queue and application supervisor.

This is one worker for one LibreChat instance, not a shared multiuser service or
an agent loop. Only saved typed phases run. Local process locking does not claim
distributed bucket locking; do not run overlapping copies for the same user.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import scientific_study as studies
from scientific_receipts import load, receipt_lock, save


def recovery_step(record):
    """Recover current idempotent batch admissions, not scientific executions."""
    if not record.get('admission_unknown') or (studies.directory(record['id']) / 'cancel-request.json').exists():
        return None
    plan = load(studies.directory(record['id']) / 'plan.json') or {}
    step = next((item for item in plan.get('steps', []) if item['id'] == record.get('current_step')), None)
    if not step or step['kind'] != 'batch':
        return None
    output = Path(record['output_directory']) / 'steps' / step['id'] / 'operation'
    receipt = load(output / 'receipt.json') or {}
    # The worker can die after the child ACK/receipt but before its own write.
    # These local recoveries need no remaining network-admission retry budget.
    can_recover = (receipt.get('operation_id') or load(output / 'admission.json')
                   or studies.workflow_module().batch.recoverable_admission(receipt))
    return step if can_recover else None


async def reconcile(identifier):
    """Use the saved request's ACK to release the existing study executor.

    Keeping this transport transition here preserves scientific_study.py bytes
    pinned by active deterministic analyses. No plan, source or result is edited.
    """
    root = studies.directory(identifier)
    with receipt_lock(root):
        record = load(root / 'receipt.json')
        step = recovery_step(record)
        if step is None:
            return None
        studies.verify_inputs(record)
        plan = load(root / 'plan.json')
        studies.verify_cancellation_identity(record, plan)
        arguments = studies.resolve(step, record)
        arguments = {key: value for key, value in arguments.items() if key not in {'id', 'kind'}}
        arguments.update(output=Path(record['output_directory']) / 'steps' / step['id'] / 'operation',
                         wait_seconds=0, poll_seconds=10, reconcile_only=True)
        for field in ('source', 'parameters', 'source_artifact'):
            if field in arguments:
                arguments[field] = studies.path_in_workspace(arguments[field])
        with receipt_lock(arguments['output']):
            receipt = await studies.workflow_module().batch.run(argparse.Namespace(**arguments))
        record['steps'][step['id']] = {key: receipt[key] for key in ('state', 'operation_id')}
        record.update(state='running', phase='admission_recovered', admission_unknown=False,
                      queue_blocked=False, updated_at=time.time())
        record.pop('finished_at', None)
        if record.get('failure'):
            record.setdefault('recovered_failures', []).append(record.pop('failure'))
        save(root / 'receipt.json', record)
        return studies.view(record)


def next_study(items):
    """Never overlap an unresolved/ambiguous admission with a later study."""
    for item in sorted(items, key=lambda item: item['created_at']):
        if item.get('queue_blocked') and (item.get('admission_unknown') or item.get('cancellation_unknown') or not (studies.directory(item['id']) / 'cancel-request.json').exists()):
            if recovery_step(item):
                return item['id'], None
            return None, item['id']
        if item['state'] not in studies.FINAL or (
                item.get('queue_blocked') and (studies.directory(item['id']) / 'cancel-request.json').exists()):
            return item['id'], None
    return None, None


async def cycle():
    identifier, blocked = next_study(studies.list_studies())
    # Health is non-secret local state. Durable study receipts live in the bucket.
    health = Path(os.environ.get('SCIENTIFIC_EXECUTION_DIR', '/data/hcls-execution')) / 'study-worker.json'
    health.parent.mkdir(parents=True, exist_ok=True)
    save(health, {'updated_at': time.time(), 'pid': os.getpid(), 'current_study': identifier,
                  'process_start': Path('/proc/self/stat').read_text().split()[21],
                  'blocked_by_study': blocked, 'owner_namespace': studies.owner_identity()})
    if identifier:
        record = load(studies.directory(identifier) / 'receipt.json')
        if recovery_step(record):
            return await reconcile(identifier)
        return await studies.advance(identifier)
    return None


def worker():
    while True:
        try:
            # Also excludes duplicate workers caused by MCP/browser reconnect.
            with receipt_lock(studies.registry() / 'queue-worker'):
                asyncio.run(cycle())
        except Exception as error:
            # No phase resubmission here: advance() persists application errors;
            # storage/identity failures stop this observation until accessible.
            print(json.dumps({'event': 'study_worker_observation_failed',
                              'error_type': type(error).__name__}), flush=True)
        time.sleep(2)


def supervise(command):
    """Restart only the receipt worker; API termination remains container exit."""
    stopping = False
    children = []

    def stop(_signal=None, _frame=None):
        nonlocal stopping
        stopping = True
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    api = subprocess.Popen(command, start_new_session=True, preexec_fn=studies.stop_with_parent)
    children.append(api)
    runner = None
    enabled = os.environ.get('SCIENTIFIC_STUDY_OWNER_MODE') in {'first-instance', 'stopped-predecessor'}
    try:
        while not stopping and api.poll() is None:
            if enabled and (runner is None or runner.poll() is not None):
                runner = subprocess.Popen([sys.executable, __file__, '--worker'], start_new_session=True,
                                          preexec_fn=studies.stop_with_parent)
                children.append(runner)
            time.sleep(0.25)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    return api.returncode or 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.worker:
        worker()
    else:
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        if not command:
            parser.error('Provide the existing API command after --.')
        raise SystemExit(supervise(command))
