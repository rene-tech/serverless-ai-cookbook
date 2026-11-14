#!/usr/bin/env python3
"""Make BioEmu2 portable molecular example inputs; Python standard library only."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

UBIQUITIN = 'MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG'
GCN4 = 'RMKQLEDKVEELLSKNYHLENEVARLKKLVGER'
OPERATIONS = ['predict-structure', 'sample-equilibrium', 'propagate', 'simulate-trajectory']
INITIAL_SHA256 = 'd6e59854c4400a4ca786e5d27152ecf0b61e58ed4741c434b89452fe4e241625'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', choices=OPERATIONS, default='predict-structure')
    parser.add_argument('--output', type=Path, default=Path('input.tar.gz'))
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite ' + str(args.output))
    prediction = args.operation == 'predict-structure'
    sequence = UBIQUITIN if prediction else GCN4
    chains = ['A'] if prediction else ['A', 'B']
    system = ('entities:\n  - entity_type: protein\n    sequence: ' + sequence + '\n    asym_ids: ['
              + ', '.join(chains) + ']\n').encode()
    if not prediction:
        system = b'# Public upstream documentation: GCN4 leucine zipper, PDB 2ZTA.\n' + system
    members = {'system.yaml': system}
    if not prediction:
        for chain in chains:
            members['msa/' + chain + '.a3m'] = ('>query\n' + sequence + '\n').encode()
    if args.operation in ['propagate', 'simulate-trajectory']:
        initial = Path(__file__).with_name('gcn4-initial.cif').read_bytes()
        if hashlib.sha256(initial).hexdigest() != INITIAL_SHA256:
            raise SystemExit('Bundled starting-coordinate checksum differs; download companions from the same skill revision')
        members['initial.cif'] = initial
    with args.output.open('xb') as output:
        with gzip.GzipFile(fileobj=output, mode='wb', mtime=0, filename='') as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as archive:
                for name, raw in sorted(members.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(raw), 0o644, 0
                    archive.addfile(info, io.BytesIO(raw))
    parameters = {'num_samples': 3 if prediction else 2, 'batch_size': 1, 'seed': 42,
                  'msa_mode': 'single_sequence' if prediction else 'provided'}
    if args.operation in ['propagate', 'simulate-trajectory']:
        parameters['lag_time_ns'] = 1.0
    if args.operation == 'simulate-trajectory':
        parameters['trajectory_steps'] = 2
    print(json.dumps({'file': str(args.output), 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                     'size_bytes': args.output.stat().st_size, 'members': sorted(members),
                     'workflow': args.operation, 'parameters': parameters}, indent=2))


if __name__ == '__main__':
    main()
