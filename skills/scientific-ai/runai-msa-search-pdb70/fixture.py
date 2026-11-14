#!/usr/bin/env python3
"""Create the small public ubiquitin PDB70 search fixture using the standard library."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

SEQUENCE = 'MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG'
VERSION = 'mmseqs2-8cc5ce36-pdb70-220313'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', required=True, help='An unused object key in your approved bound bucket')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not args.key or args.key.startswith('/') or any(v in {'.', '..'} for v in args.key.split('/')):
        parser.error('Use a nonempty relative owner-bucket key, without dot path components')
    output = Path(args.output)
    output.mkdir(exist_ok=False, parents=True)
    payload = (json.dumps({'sequence': SEQUENCE}, separators=(',', ':')) + '\n').encode()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        member = tarfile.TarInfo('query.json')
        member.size, member.mode = len(payload), 0o600
        archive.addfile(member, io.BytesIO(payload))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0, compresslevel=9) as stream:
        stream.write(raw.getvalue())
    archive_bytes = compressed.getvalue()
    digest = hashlib.sha256(archive_bytes).hexdigest()
    # This exact archive is also the published workflow's scientific fixture.
    assert len(archive_bytes) == 185 and digest == '1194b45bdf06a6483c514f37f0f360ba9c437e8a79b245558c851dc616d8e056'
    (output / 'input.tar.gz').write_bytes(archive_bytes)
    reference = {'name': 'input.tar.gz', 'key': args.key, 'sha256': digest, 'size_bytes': len(archive_bytes)}
    for name, value in [('input-reference.json', reference), ('parameters.json', {})]:
        (output / name).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'archive_sha256': digest, 'size_bytes': len(archive_bytes), 'scientific_version': VERSION}))

if __name__ == '__main__':
    main()
