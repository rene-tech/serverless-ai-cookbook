"""Apply a qualified file-UI archive inside an existing workbench container.

Run as its operator, after checking idle chats. This keeps the endpoint and its
data; it does not restart the application. Restart the *container*, not the
Serverless endpoint, once this command and verify-workspace-installed.mjs pass.
The backup and receipt remain on /data. A later Serverless VM recreation must
use the qualified default image or explicitly reapply this retained patch.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

ALLOWED_ROOTS = ('app/client/dist/', 'app/client/src/')
ALLOWED_FILES = {'app/api/server/routes/scientific-demos.js',
                 'opt/hcls-librechat/demos/service.cjs',
                 'opt/hcls-librechat/verify-workspace-installed.mjs'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--release', required=True)
    args = parser.parse_args()
    if not args.release or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.release):
        parser.error('Use a lowercase release identifier')
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != args.sha256:
        raise ValueError('Archive digest mismatch; no files changed')
    receipt_dir = Path('/data/workbench-hotfixes') / args.release
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / 'receipt.json'
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['archive_sha256'] != args.sha256:
            raise ValueError('A different hotfix already uses this release identifier')
        if all(hashlib.sha256(Path('/' + row['path']).read_bytes()).hexdigest() == row['sha256'] for row in receipt['files']):
            print(json.dumps({'already_applied': True, 'files': len(receipt['files'])}))
            return
        raise RuntimeError('Installed hotfix drifted; inspect it before retrying')
    with tarfile.open(args.archive) as archive, tempfile.TemporaryDirectory(prefix='workspace-hotfix-') as staging:
        members = archive.getmembers()
        files = []
        for member in members:
            name = member.name.removeprefix('./')
            if not name or name == '.':
                continue
            if Path(name).is_absolute() or '..' in Path(name).parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsupported archive entry; no files changed')
            if member.isfile():
                if name not in ALLOWED_FILES and not name.startswith(ALLOWED_ROOTS):
                    raise ValueError('Archive contains a file outside the UI/file-route patch')
                files.append(name)
        archive.extractall(staging, members=members)
        backup = receipt_dir / 'before.tar.gz'
        # Never overwrite rollback evidence. Keep all old assets for open tabs.
        if backup.exists():
            raise RuntimeError('Prior patch attempt has a backup; inspect before continuing')
        with tarfile.open(backup, 'w:gz') as old:
            for name in files:
                target = Path('/' + name)
                if target.is_file():
                    old.add(target, arcname=name, recursive=False)
        shutil.copy2(args.archive, receipt_dir / 'patch.tar.gz')
        records = []
        for name in sorted(files, key=lambda name: name == 'app/client/dist/index.html'):
            source, target = Path(staging) / name, Path('/' + name)
            if target.is_symlink():
                raise ValueError('Refusing to replace a symlink; restore backup if needed')
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='.workspace-hotfix-', dir=target.parent)
            os.close(fd)
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
            records.append({'path': name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        receipt_path.write_text(json.dumps({'release': args.release, 'archive_sha256': args.sha256,
                                           'files': records}, indent=2))
        print(json.dumps({'applied': True, 'files': len(records), 'rollback': str(backup)}))


if __name__ == '__main__':
    main()
