#!/usr/bin/env python3
"""Package the existing file clients for laptops without the LibreChat runtime.

Run from a pinned cookbook checkout. The output contains exact source bytes,
dependency pins and checksums; it does not install, authenticate or submit work.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[3]
FILES = {
    'LICENSE': 'LICENSE',
    'upload-artifact.py': 'templates/hcls-librechat/upload-artifact.py',
    'invoke-native.py': 'templates/hcls-librechat/invoke-native.py',
    'invoke-scientific-batch.py': 'templates/hcls-librechat/scripts/scientific-batch-acceptance.py',
    'invoke-scientific-campaign.py': 'templates/hcls-librechat/scripts/scientific-campaign.py',
    'scientific_receipts.py': 'templates/hcls-librechat/scientific_receipts.py',
    'native_md_artifacts.py': 'templates/hcls-librechat/native_md_artifacts.py',
    'requirements.txt': 'templates/hcls-librechat/scientific-client-requirements.txt',
    'README.md': 'skills/scientific-ai/scientific-gateway/references/portable-client.md',
    'worked-example.md': 'skills/scientific-ai/scientific-gateway/references/portable-rfdiffusion.md',
    'bindcraft2-example.md': 'skills/scientific-ai/scientific-gateway/references/portable-bindcraft2.md',
    'campaign-example.md': 'skills/scientific-ai/scientific-gateway/references/portable-campaign.md',
    'bucket-access.md': 'skills/scientific-ai/scientific-gateway/references/bucket-access.md',
}


def package(output, root=ROOT):
    output = Path(output).resolve()
    root = Path(root).resolve()
    if output == root or root in output.parents:
        raise ValueError('Release output must be outside the source checkout.')
    version = json.loads((root / 'skills/scientific-ai/manifest.json').read_text())['version']
    # Allowlisted, ordinary source files only; no environments or private receipts.
    payload = {}
    for name, source in FILES.items():
        path = root / source
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Expected a regular source file: {source}')
        payload[name] = path.read_bytes()
    source_map = {name: {'source': FILES[name], 'sha256': hashlib.sha256(raw).hexdigest()}
                  for name, raw in sorted(payload.items())}
    payload['source-files.json'] = (json.dumps(source_map, indent=2) + '\n').encode()
    payload['SHA256SUMS'] = ''.join(
        f'{hashlib.sha256(raw).hexdigest()}  {name}\n' for name, raw in sorted(payload.items())
    ).encode()
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'scientific-ai-client-{version}.tar.gz'
    checksums = output / (target.name + '.sha256')
    if target.exists() or checksums.exists():
        raise FileExistsError('Release already exists; use a fresh output directory.')
    with target.open('xb') as handle:
        with gzip.GzipFile(fileobj=handle, mode='wb', filename='', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as archive:
                for name, raw in sorted(payload.items()):
                    info = tarfile.TarInfo('scientific-ai-client/' + name)
                    info.size, info.mode, info.mtime = len(raw), 0o644, 0
                    archive.addfile(info, io.BytesIO(raw))
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    with checksums.open('x') as handle:
        handle.write(f'{checksum}  {target.name}\n')
    return {'archive': str(target), 'sha256': checksum, 'files': len(payload),
            'version': version, 'source_files': source_map}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.output)))


if __name__ == '__main__':
    main()
