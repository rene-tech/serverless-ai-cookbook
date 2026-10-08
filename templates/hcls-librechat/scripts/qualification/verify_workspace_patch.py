"""Compare a UI hotfix export to the immutable release image's final OCI layer."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--layer', type=Path, required=True)
parser.add_argument('--patch-root', type=Path, required=True)
args = parser.parse_args()
compared = []
with tarfile.open(args.layer) as layer:
    for member in layer:
        relative = Path(member.name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unexpected layer path')
        target = args.patch_root / relative
        if member.isfile() and target.is_file():
            with layer.extractfile(member) as source:
                expected = hashlib.file_digest(source, 'sha256').hexdigest()
            with target.open('rb') as source:
                actual = hashlib.file_digest(source, 'sha256').hexdigest()
            if actual != expected:
                raise ValueError(f'Patch/image mismatch: {relative}')
            compared.append(str(relative))
required = {'app/client/dist/index.html', 'app/client/src/components/WorkspaceFilePicker.tsx',
            'app/client/src/components/SidePanel/Files/PanelTable.tsx',
            'app/api/server/routes/scientific-demos.js', 'opt/hcls-librechat/demos/service.cjs',
            'opt/hcls-librechat/verify-workspace-installed.mjs'}
if not required.issubset(compared) or not any(p.startswith('app/client/dist/assets/') for p in compared):
    raise ValueError('Not every required patch surface appears in the image layer')
print(json.dumps({'patch_matches_immutable_image': True, 'compared_files': len(compared),
                  'required_surfaces': sorted(required)}))
