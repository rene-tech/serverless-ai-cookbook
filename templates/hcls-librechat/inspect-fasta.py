#!/usr/bin/env python3
"""Deterministic FASTA inventory; no model inference or sequence substitution."""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from Bio import SeqIO


def inspect(source, output):
    source, output = Path(source), Path(output)
    rows = []
    with source.open() as handle:
        for record in SeqIO.parse(handle, 'fasta'):
            sequence = str(record.seq).upper()
            valid = sum(sequence.count(base) for base in 'ACGT')
            gc = sequence.count('G') + sequence.count('C')
            rows.append({'sequence_id': record.id, 'length': len(sequence),
                         'valid_acgt_bases': valid, 'gc_bases': gc,
                         'gc_percent': 100.0 * gc / valid if valid else None,
                         'ambiguous_bases': len(sequence) - valid})
    if not rows:
        raise ValueError('No FASTA records; no output written')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {'rows': rows, 'output': str(output),
              'gc_denominator': 'A/C/G/T only; null (empty CSV field) when denominator is zero'}
    if output.is_absolute() and output.is_relative_to('/workspace'):
        relative = output.relative_to('/workspace')
        result['workspace_url'] = '/demos?' + urlencode({
            'tab': 'workspace', 'path': str(relative.parent), 'file': str(relative)})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.input, args.output), allow_nan=False))
