import importlib.util
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('state_supervisor', Path(__file__).with_name('state-supervisor.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_container_local_state_is_not_persistent(tmp_path):
    mounts = tmp_path / 'mountinfo'
    mounts.write_text('1 0 0:1 / / rw - overlay overlay rw\n')
    with pytest.raises(RuntimeError, match='dedicated persistent'):
        module.mount_type(tmp_path, mounts)


def test_mounted_state_type_is_detected(tmp_path):
    mounts = tmp_path / 'mountinfo'
    mounts.write_text(f'1 0 0:1 / {tmp_path} rw - virtiofs state rw\n')
    assert module.mount_type(tmp_path, mounts) == 'virtiofs'


def test_upload_link_keeps_files_and_is_idempotent(tmp_path):
    source, target = tmp_path / 'uploads', tmp_path / 'state-uploads'
    source.mkdir()
    (source / 'paper.pdf').write_bytes(b'customer attachment')
    module.link_directory(source, target)
    module.link_directory(source, target)
    assert source.is_symlink()
    assert (source / 'paper.pdf').read_bytes() == b'customer attachment'


def test_conflicting_customer_files_are_never_overwritten(tmp_path):
    source, target = tmp_path / 'uploads', tmp_path / 'state-uploads'
    source.mkdir(); target.mkdir()
    (source / 'paper.pdf').write_bytes(b'new')
    (target / 'paper.pdf').write_bytes(b'old')
    with pytest.raises(RuntimeError, match='Conflicting'):
        module.link_directory(source, target)
    assert (target / 'paper.pdf').read_bytes() == b'old'


def test_snapshot_keeps_keys_db_and_uploads_excludes_itself(tmp_path):
    for directory, filename in [('db', 'WiredTiger'), ('hcls-librechat', 'runtime-secrets.env'),
                                ('hcls-librechat/uploads', 'paper.pdf')]:
        path = tmp_path / directory / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
    (tmp_path / '.instance.lock').touch()
    first = module.snapshot(tmp_path, 'upgrade-01')
    assert module.snapshot(tmp_path, 'upgrade-01') == first
    with tarfile.open(first) as archive:
        names = archive.getnames()
        assert 'db/WiredTiger' in names
        assert 'hcls-librechat/runtime-secrets.env' in names
        assert 'hcls-librechat/uploads/paper.pdf' in names
        assert not any(name.startswith('snapshots') or name == '.instance.lock' for name in names)
    assert first.stat().st_mode & 0o777 == 0o600


def test_snapshot_refuses_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        module.snapshot(tmp_path, '../escape')


def test_restore_preserves_displaced_data(tmp_path):
    data = tmp_path / 'db'
    data.mkdir()
    (data / 'WiredTiger').write_bytes(b'original')
    module.snapshot(tmp_path, 'operation-1')
    (data / 'WiredTiger').write_bytes(b'changed')
    module.restore(tmp_path, 'operation-1')
    assert (data / 'WiredTiger').read_bytes() == b'original'
    displaced = list((tmp_path / 'snapshots').glob('displaced-operation-1-*/db/WiredTiger'))
    assert len(displaced) == 1 and displaced[0].read_bytes() == b'changed'
    (data / 'WiredTiger').write_bytes(b'new customer data after recovery')
    module.restore(tmp_path, 'operation-1')
    assert (data / 'WiredTiger').read_bytes() == b'new customer data after recovery'
