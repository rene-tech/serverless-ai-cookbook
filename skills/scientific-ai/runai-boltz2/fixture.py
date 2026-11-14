"""Prepare the public 1UBQ control in caller storage; no credentials or submission."""
import argparse
import gzip
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

SEQUENCE = 'MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG'
ATTRIBUTION = '''MSA: OpenProteinSet, managed by OpenFold, accessed 13 November 2026.
Gustaf Ahdritz et al., OpenProteinSet: Training data for structural biology at scale (2023).
https://arxiv.org/abs/2308.05326
Dataset: https://registry.opendata.aws/openfold/
Unchanged source: https://openfold.s3.amazonaws.com/pdb/1aar_A/a3m/bfd_uniclust_hits.a3m
License: Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/
The exact source LICENSE is retained alongside this attribution.
The source MSA has not been edited; its query is identical to the 76-residue PDB 1UBQ chain A.
Reference structure PDB 1UBQ is from the wwPDB archive under CC0; used only for independent scoring.
The reference coordinates and PDB70 template hits are not prediction inputs.
'''


def fetch(url, digest, limit):
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Public reference size or SHA-256 changed: ' + url)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', required=True, help='New input object key in your bound bucket')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    members = {
        'prediction.yaml': ('version: 1\nsequences:\n  - protein:\n      id: A\n'
                            '      sequence: ' + SEQUENCE + '\n      msa: bfd_uniclust_hits.a3m\n').encode(),
        'bfd_uniclust_hits.a3m': fetch(
            'https://openfold.s3.amazonaws.com/pdb/1aar_A/a3m/bfd_uniclust_hits.a3m',
            '730ed12e119d7170ddb184629be1303b015b0060bb4c0a977c9bbc432d68dd0b', 200000),
        'settings.json': b'{}\n',
        'ATTRIBUTION.txt': ATTRIBUTION.encode(),
        'LICENSE': fetch('https://openfold.s3.amazonaws.com/LICENSE',
                         '9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411', 30000),
    }
    reference = fetch('https://files.rcsb.org/download/1UBQ.cif',
                      '056f98710cb2b36f633c45e41902a02eb446e82871da21ff2dd44f74a56ca0f6', 150000)
    # Reference coordinates stay outside the input archive: this is template-free prediction.
    (args.output / 'reference-1UBQ.cif').write_bytes(reference)
    archive = args.output / 'input.tar.gz'
    with archive.open('xb') as raw, gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for name, data in members.items():
                member = tarfile.TarInfo(name)
                member.size, member.mode, member.mtime = len(data), 0o644, 0
                tar.addfile(member, io.BytesIO(data))
    ref = {'name': 'input.tar.gz', 'key': args.key,
           'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'size_bytes': archive.stat().st_size}
    request = {'model': 'boltz2', 'workflow': 'predict', 'version': '2.2.1',
               'region': 'eu-north1', 'gpu': 'h100', 'pvc_gib': 32,
               'parameters': {'seed': 42, 'no_kernels': False}, 'inputs': [ref]}
    (args.output / 'request.json').write_text(json.dumps(request, indent=2) + '\n')
    print(json.dumps({'input': ref, 'request': str(args.output / 'request.json')}))


if __name__ == '__main__':
    main()
