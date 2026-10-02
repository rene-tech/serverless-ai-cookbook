"""Own a persistent LibreChat state directory for exactly one runtime.

Object Storage remains /workspace. MongoDB, encryption keys, uploads and local
customizations live on a separate POSIX filesystem mounted at /data. This is
deliberately independent of the platform cluster and works on Serverless.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time


def mount_type(path: Path, mountinfo: Path = Path('/proc/self/mountinfo')) -> str:
    resolved = str(path.resolve())
    for line in mountinfo.read_text().splitlines():
        before, after = line.split(' - ', 1)
        if before.split()[4].replace('\\040', ' ') == resolved:
            return after.split()[0]
    raise RuntimeError(f'{path} must be a dedicated persistent POSIX mount, not container-local storage')


def validate_mount(root: Path) -> None:
    kind = mount_type(root)
    # Object-storage FUSE does not provide MongoDB's locking/fsync semantics.
    if kind not in {'virtiofs', 'nfs', 'nfs4', 'xfs', 'ext4'}:
        raise RuntimeError(f'Unsupported state filesystem {kind}; do not put MongoDB on Object Storage')


def link_directory(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        if source.resolve() != target.resolve():
            raise RuntimeError(f'{source} points to an unexpected location')
        return
    if source.exists():
        # Never merge conflicting files or silently overwrite customer uploads.
        for item in source.iterdir():
            destination = target / item.name
            if destination.exists():
                raise RuntimeError(f'Conflicting persistent data at {destination}; explicit migration required')
            shutil.move(str(item), str(destination))
        source.rmdir()
    source.symlink_to(target, target_is_directory=True)


def snapshot(root: Path, name: str) -> Path:
    if not name or len(name) > 100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        raise ValueError('Snapshot name must be an operation identifier')
    destination = root / 'snapshots' / (name + '.tar.gz')
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    if destination.exists():
        return destination
    # Caller holds the exclusive runtime lock and MongoDB has not started yet.
    # Include the entire state, not just chats: IDs, indexes and encryption keys
    # must stay together. The separate workspace bucket is not copied.
    fd, temporary = tempfile.mkstemp(prefix='.partial-', dir=destination.parent)
    os.close(fd)
    try:
        with tarfile.open(temporary, 'w:gz', compresslevel=1) as archive:
            for path in sorted(root.iterdir()):
                if path.name not in {'snapshots', '.instance.lock'}:
                    archive.add(path, arcname=path.name, recursive=True)
        with open(temporary, 'rb') as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


def restore(root: Path, name: str) -> None:
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        raise ValueError('Invalid snapshot identity')
    source = root / 'snapshots' / (name + '.tar.gz')
    completed = root / 'snapshots' / (name + '.restored')
    if completed.exists():
        return
    if not source.is_file():
        raise RuntimeError('Requested state snapshot is missing; nothing was changed')
    # Restore into a staging directory before moving anything. Keep failed/newer
    # state recoverable; never delete it as a side effect of rollback.
    stage = Path(tempfile.mkdtemp(prefix='.restore-', dir=root))
    with tarfile.open(source) as archive:
        # The retained LibreChat base uses Python 3.11.2, before tarfile's
        # extraction filters. Only ordinary relative files/directories occur in
        # our state snapshots. Validate all entries before extracting any.
        members = archive.getmembers()
        for member in members:
            relative = Path(member.name)
            if relative.is_absolute() or '..' in relative.parts or not (member.isfile() or member.isdir()):
                raise RuntimeError('Snapshot contains an unsupported path or special file; state unchanged')
        archive.extractall(stage, members=members)
    displaced = root / 'snapshots' / f'displaced-{name}-{time.time_ns()}'
    displaced.mkdir(mode=0o700)
    for path in list(root.iterdir()):
        if path not in {stage, root / 'snapshots', root / '.instance.lock'}:
            shutil.move(str(path), str(displaced / path.name))
    for path in stage.iterdir():
        shutil.move(str(path), str(root / path.name))
    stage.rmdir()
    with completed.open('x') as receipt:
        receipt.write('completed\n')
        receipt.flush()
        os.fsync(receipt.fileno())


def supervise(root: Path, command: list[str]) -> int:
    validate_mount(root)
    os.umask(0o077)
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.instance.lock').open('a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another LibreChat runtime owns this filesystem; no second writer started') from exc
        if os.environ.get('SCIENTIFIC_STATE_RESTORE'):
            restore(root, os.environ['SCIENTIFIC_STATE_RESTORE'])
        optional_restore = os.environ.get('SCIENTIFIC_STATE_RESTORE_IF_PRESENT')
        if optional_restore and (root / 'snapshots' / (optional_restore + '.tar.gz')).is_file():
            restore(root, optional_restore)
        if os.environ.get('SCIENTIFIC_STATE_SNAPSHOT'):
            snapshot(root, os.environ['SCIENTIFIC_STATE_SNAPSHOT'])
        data = root / 'hcls-librechat'
        data.mkdir(mode=0o700, exist_ok=True)
        link_directory(Path('/app/uploads'), data / 'uploads')
        # UI-created agents, prompts and settings live in MongoDB. The persistent
        # overrides file supports deployment-owned non-secret config separately.
        environment = {**os.environ, 'LIBRECHAT_DATA_DIR': str(data),
                       'LIBRECHAT_MONGO_DATA_DIR': str(root / 'db')}
        process = subprocess.Popen(command, env=environment, start_new_session=True,
                                   pass_fds=(lock.fileno(),))
        def stop(signum, _frame):
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                pass
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        code = process.wait()
        # mongod normally shuts down with the process group. Do not release the
        # state lock while an orphan could still write to WiredTiger.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/data'))
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('a runtime command is required')
    if os.environ.get('SCIENTIFIC_REQUIRE_PERSISTENT_STATE', 'false').lower() != 'true':
        # Explicit backwards compatibility. Legacy instances are not advertised
        # as restart/replacement-safe and must be exported before migration.
        os.execvpe(command[0], command, os.environ)
    raise SystemExit(supervise(args.root, command))
