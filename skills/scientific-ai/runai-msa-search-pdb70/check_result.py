#!/usr/bin/env python3
"""Check the exact default public ubiquitin/PDB70 fixture after full artifact-hash verification."""
import argparse
import hashlib
import json
from pathlib import Path

SEQUENCE = 'MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG'
VERSION = 'mmseqs2-8cc5ce36-pdb70-220313'
ENGINE = '8cc5ce367b5638c4306c2d7cfc652dd099a4643f'
ALIGNMENT_SHA = '246fb558eb3c2be0eb8817db12a822ee4c38f1d6cb320e0d45ab3fa4fec9c976'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-dir', required=True)
    args = parser.parse_args()
    root = Path(args.result_dir) / 'data/outputs/search'
    alignment = (root / 'alignment.a3m').read_bytes()
    result = json.loads((root / 'result.json').read_text())
    science_bytes = (root / 'science.json').read_bytes()
    science = json.loads(science_bytes)
    assert hashlib.sha256(alignment).hexdigest() == ALIGNMENT_SHA == result['alignment_sha256'] == science['alignment_sha256']
    assert result['model'] == 'msa-search-pdb70' and result['model_version'] == science['model_version'] == VERSION
    assert result['engine'] == 'MMseqs2' and result['engine_version'] == ENGINE
    assert result['database'] == 'pdb70_220313' and result['format'] == 'a3m'
    assert result['query_residues'] == 76 and result['query_sha256'] == hashlib.sha256(SEQUENCE.encode()).hexdigest()
    assert result['requested_max_sequences'] == 500 and result['sequence_count'] == 141
    assert result['delivered_scientific_units'] == 1 and result['unit'] == 'protein_query'
    assert science['work_is_CPU_only'] is True
    assert hashlib.sha256((root / 'result.json').read_bytes()).hexdigest() == science['result_sha256']
    lines = alignment.decode().splitlines()
    assert lines[:2] == ['>query', SEQUENCE] and sum(line.startswith('>') for line in lines) == 141
    print(json.dumps({'status': 'PASS_PUBLIC_UBIQUITIN_PDB70_FIXTURE', 'sequence_count': 141, 'scientific_version': VERSION}))

if __name__ == '__main__':
    main()
