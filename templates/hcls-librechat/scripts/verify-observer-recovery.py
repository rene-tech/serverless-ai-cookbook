"""Offline installed-image gate; no credentials, customer files or network.

Run with the image's scientific Python. Both build recipes and release checks
must verify installed bytes, not just matching source files in a build context.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


FILES = {
    'scripts/scientific-batch-acceptance.py': 'invoke-scientific-batch.py',
    'scientific-workflow.py': 'scientific-workflow.py',
    'scientific-study-worker.py': 'scientific-study-worker.py',
}


def verify(source, installed=Path('/opt/bionemo')):
    hashes = {}
    for original, target in FILES.items():
        digest = hashlib.sha256((installed / target).read_bytes()).hexdigest()
        if digest != hashlib.sha256((source / original).read_bytes()).hexdigest():
            raise RuntimeError('Installed observer source differs: ' + target)
        hashes[target] = digest
    sys.path.insert(0, str(installed))
    spec = importlib.util.spec_from_file_location('image_observer_worker', installed / 'scientific-study-worker.py')
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    workflow = worker.studies.workflow_module()
    from anyio import EndOfStream
    transient = ExceptionGroup('test disconnect', [EndOfStream()])
    if not workflow.transport_disconnect(transient):
        raise RuntimeError('Nested stream disconnect is not recoverable')
    if workflow.transport_disconnect(ExceptionGroup('invalid result', [EndOfStream(), ValueError('invalid')])):
        raise RuntimeError('Scientific errors must not become transport retries')

    # Real installed selector, synthetic local receipts. A lost observer must
    # neither freeze a new request nor replay inference to recover its identity.
    with tempfile.TemporaryDirectory(prefix='observer-image-') as temporary:
        root = Path(temporary)
        first = dict(id='first', state='needs_attention', current_step='simulate',
                     output_directory=str(root / 'output'), created_at=1,
                     updated_at=10, queue_blocked=True)
        second = dict(id='second', state='queued', created_at=2, updated_at=2)
        records = {
            root / 'first/receipt.json': first,
            root / 'second/receipt.json': second,
            root / 'first/plan.json': {'steps': [{'id': 'simulate', 'kind': 'batch'}]},
            root / 'output/steps/simulate/operation/receipt.json': {
                'operation_id': 'op-image-fixture', 'state': 'running'},
        }
        with patch.object(worker.studies, 'directory', side_effect=lambda identifier: root / identifier), \
             patch.object(worker, 'load', side_effect=lambda path: records.get(path)):
            if worker.observation_step(first) is None:
                raise RuntimeError('Known operation cannot reconnect')
            if worker.next_study([first, second]) != ('second', None):
                raise RuntimeError('Disconnected observer blocks later work')
            first['observation_recovery'] = {'retryable': False}
            if worker.observation_step(first) is not None:
                raise RuntimeError('Permanent observation errors must remain visible')
    return {'files': hashes, 'nested_disconnect': True, 'queue_fairness': True,
            'permanent_error_preserved': True, 'scientific_submissions': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.source)))
