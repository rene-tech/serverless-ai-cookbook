import copy
import httpx
import pytest

import workspace_preview as preview


def source(tmp_path):
    folder = tmp_path / 'preview'
    folder.mkdir()
    (folder / 'README.md').write_bytes(b'public report')
    (folder / 'video.mp4').write_bytes(b'synthetic video fixture')
    return folder, preview.inventory(folder)


def test_local_inventory_refuses_links_empty_and_requested_size_overflow(tmp_path, monkeypatch):
    folder, rows = source(tmp_path)
    assert sum(row['size_bytes'] for row in rows) < preview.MAX_BYTES
    (folder / 'link').symlink_to(folder / 'README.md')
    with pytest.raises(ValueError, match='links'):
        preview.inventory(folder)
    (folder / 'link').unlink()
    monkeypatch.setattr(preview, 'MAX_BYTES', 10)
    with pytest.raises(ValueError, match='100 MB'):
        preview.inventory(folder)


def fixture_client(folder, objects, calls, *, raced=False):
    def request(req):
        assert req.url.path in {'/api/scientific-demos/workspace', '/api/scientific-demos/workspace/file'}
        calls.append(req.method)
        if req.method == 'GET':
            path = req.url.params['path']
            return httpx.Response(200, content=objects[path]) if path in objects else httpx.Response(404)
        assert req.method == 'POST'
        # These small synthetic inputs exercise multipart transfer, not an MD job.
        body = req.read()
        row = next(path for path in folder.iterdir() if path.name.encode() in body
                   and path.read_bytes() in body)
        key = preview.PREFIX + '/' + row.name
        assert key not in objects, 'Publisher must never replace an existing object'
        objects[key] = row.read_bytes()
        return httpx.Response(409 if raced else 201, json={})
    return httpx.Client(base_url='https://synthetic.example', transport=httpx.MockTransport(request))


def test_dry_run_checks_all_files_and_space_without_any_upload(tmp_path):
    folder, rows = source(tmp_path)
    calls, progress, objects = [], {}, {}
    with fixture_client(folder, objects, calls) as client:
        preview.publish_files(client, folder, rows, publish=False,
                              capacity=lambda: {'headroom_bytes': 1000}, progress=progress)
    assert calls == ['GET', 'GET'] and not objects
    assert progress['new_bytes'] == sum(row['size_bytes'] for row in rows)


@pytest.mark.parametrize('raced', [False, True])
def test_exclusive_publication_verifies_and_resumes_without_overwrite(tmp_path, raced):
    folder, rows = source(tmp_path)
    calls, progress = [], {}
    objects = {preview.PREFIX + '/README.md': (folder / 'README.md').read_bytes()}
    with fixture_client(folder, objects, calls, raced=raced) as client:
        preview.publish_files(client, folder, rows, publish=True,
                              capacity=lambda: {'headroom_bytes': 1000}, progress=progress)
        assert calls == ['GET', 'GET', 'POST', 'GET']
        assert progress['reused_files'] == 1 and progress['verified_uploaded'] == ['video.mp4']
        preview.publish_files(client, folder, rows, publish=True,
                              capacity=lambda: {'headroom_bytes': 0}, progress=progress)
    assert calls.count('POST') == 1 and progress['new_bytes'] == 0


def test_conflict_anywhere_is_rejected_before_first_upload(tmp_path):
    folder, rows = source(tmp_path)
    calls = []
    objects = {preview.PREFIX + '/video.mp4': b'not the same file'}
    with fixture_client(folder, objects, calls) as client:
        with pytest.raises(ValueError, match='no overwrite'):
            preview.publish_files(client, folder, rows, publish=True,
                                  capacity=lambda: {'headroom_bytes': 1000}, progress={})
    assert 'POST' not in calls and len(objects) == 1


def test_insufficient_headroom_never_changes_objects(tmp_path):
    folder, rows = source(tmp_path)
    calls, objects = [], {}
    with fixture_client(folder, objects, calls) as client:
        with pytest.raises(ValueError, match='Insufficient'):
            preview.publish_files(client, folder, rows, publish=True,
                                  capacity=lambda: {'headroom_bytes': 1}, progress={})
    assert 'POST' not in calls and not objects


def test_headroom_accounts_for_inflight_and_noncurrent_objects():
    provider = {'spec': {'max_size_bytes': '500'}, 'status': {'state': 'ACTIVE',
        'suspension_state': 'NOT_SUSPENDED', 'counters': [{'counters': {
            'simple_objects_size': '100', 'multipart_objects_size': '200', 'inflight_parts_size': '10'},
            'non_current_counters': {'simple_objects_size': '20', 'multipart_objects_size': '30'}}]}}
    assert preview.headroom({'quota_bytes': 500}, provider)['headroom_bytes'] == 140
    with pytest.raises(ValueError, match='quotas differ'):
        preview.headroom({'quota_bytes': 600}, provider)


@pytest.mark.parametrize('change', ['predecessor', 'image', 'bucket', 'key'])
def test_replacement_binding_is_checked_before_publication(change):
    variables = [{'name': name, 'value': 'synthetic-' + name} for name in
                 ('SCIENTIFIC_MODELS_API_KEY', 'SCIENTIFIC_MODELS_API_BASE_URL',
                  'SEED_DEFAULT_USER_EMAIL', 'SEED_DEFAULT_USER_PASSWORD')]
    backup = {'metadata': {'id': 'old'}, 'spec': {'environment_variables': variables,
        'volumes': [{'container_path': '/workspace', 'source': 's3://synthetic', 'mode': 'READ_WRITE'}]}}
    live = copy.deepcopy(backup)
    live.update(metadata={'id': 'replacement'}, status={'state': 'RUNNING'})
    live['spec']['image'] = 'exact-image'
    storage = {'state': 'ready', 'bucket_name': 'synthetic'}
    preview.binding(live, backup, storage, 'exact-image')
    if change == 'predecessor': live['metadata']['id'] = 'old'
    if change == 'image': live['spec']['image'] = 'different'
    if change == 'bucket': storage['bucket_name'] = 'someone-else'
    if change == 'key': live['spec']['environment_variables'][0]['value'] = 'another'
    with pytest.raises(ValueError):
        preview.binding(live, backup, storage, 'exact-image')
