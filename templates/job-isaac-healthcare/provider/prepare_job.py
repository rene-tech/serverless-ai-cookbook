"""Prepare a portable input archive or private provider request; no network calls."""
import argparse
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent


def positive(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError('Use a positive integer')
    return result


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with path.open('x') as target:
        json.dump(value, target, indent=2, allow_nan=False)
        target.write('\n')


def bundle(args):
    if args.scenarios is None and args.project is None and args.operation != 'inspect':
        raise ValueError('Provide --scenarios or --project for this operation')
    incoming = [('parameters.json', args.parameters)]
    if args.scenarios is not None:
        incoming.append(('scenarios.json', args.scenarios))
    for _, path in incoming:
        if not isinstance(json.loads(path.read_bytes()), dict):
            raise ValueError('Scenario and parameter documents must be JSON objects')
    with tarfile.open(args.output, 'x:') as archive:
        request = json.dumps({'schema': 'isaac-healthcare-bundle/v2', 'operation': args.operation,
                              'scenarios': args.scenarios is not None, 'project': args.project is not None}).encode()
        member = tarfile.TarInfo('request.json')
        member.size, member.mode, member.mtime = len(request), 0o644, 0
        archive.addfile(member, io.BytesIO(request))
        if args.project is not None:
            incoming.append(('project.tar', args.project))
        for name, path in incoming:
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = path.stat().st_size, 0o644, 0
            with path.open('rb') as content:
                archive.addfile(member, content)
    print(json.dumps({'input_archive': str(args.output), 'sha256': sha(args.output),
                      'size_bytes': args.output.stat().st_size}))


def url_file(path):
    value = path.read_text().strip()
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Use a direct scoped HTTPS URL in a private file')
    return value


def pack_support(contents):
    """Pack exact helpers/inventories independently of scientific input or settings."""
    original = dict(contents)
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", "..") for name in original):
        raise ValueError('Support files require plain relative names')
    identity = hashlib.sha256(json.dumps({name: hashlib.sha256(value).hexdigest()
        for name, value in sorted(original.items())}, sort_keys=True).encode()).hexdigest()
    root = '/tmp/isaac-provider-code-' + identity
    command = json.loads(original['command.json'])
    if not isinstance(command, list) or not command or any(not isinstance(v, str) or '\0' in v for v in command):
        raise ValueError('Support command must be a nonempty argv array')
    # Only exact support-file argv elements move; all ordinary CLI options stay exact.
    replacements = {'/opt/isaac-task/' + name: root + '/' + name for name in original}
    contents = dict(original)
    contents['command.json'] = (json.dumps([replacements.get(v, v) for v in command], indent=2) + '\n').encode()
    stream = io.BytesIO()
    files = {}
    with tarfile.open(fileobj=stream, mode='w:', format=tarfile.USTAR_FORMAT) as archive:
        for name, value in sorted(contents.items()):
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(value), 0o600, 0
            archive.addfile(member, io.BytesIO(value))
            files[name] = {'size_bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest(), 'mode': 0o600}
    raw = stream.getvalue()
    packed = gzip.compress(raw, mtime=0)
    manifest = {'schema': 'isaac-provider-support/v1', 'root': root, 'source_identity': identity,
        'files': files, 'archive': {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)},
        'compressed': {'sha256': hashlib.sha256(packed).hexdigest(), 'size_bytes': len(packed)}}
    return contents, packed, manifest


def render(args):
    if not args.accept_eula:
        raise ValueError('Review the simulator/Kit terms and pass --accept-eula')
    if not re.fullmatch(r'[^@\s]+@sha256:[0-9a-f]{64}', args.image):
        raise ValueError('Use a complete immutable image reference; do not truncate the digest')
    if args.timeout_seconds <= args.science_timeout_seconds:
        raise ValueError('Job timeout must leave time after the requested science timeout for delivery')
    if bool(args.diagnostics_public_ip) != bool(args.ssh_public_key):
        raise ValueError('Diagnostic public IP and an existing SSH public key must be selected together')
    inventory = json.loads(args.installation.read_bytes())
    if inventory.get('schema') != 'isaac-healthcare-customer-installation/v1':
        raise ValueError('Run the CPU installation inspector against this image first')
    if inventory['runtime_sources']['portable_image'] != args.image:
        raise ValueError('Installation inventory belongs to another immutable image')
    command = (HERE / 'command.json').read_bytes()
    transfer = {'command_sha256': hashlib.sha256(command).hexdigest(),
        'execution_timeout_s': args.science_timeout_seconds,
        'input': {'url': url_file(args.input_url_file), 'sha256': sha(args.input),
                  'size_bytes': args.input.stat().st_size},
        'output': {'url': url_file(args.output_url_file), 'max_bytes': args.output_max_bytes,
                   'headers': {'Content-Type': 'application/x-tar'}},
        'claim': {'url': url_file(args.claim_url_file),
                  'headers': {'If-None-Match': '*', 'Content-Type': 'application/json'}}}
    contents = {name: (HERE / name).read_bytes() for name in
                ('transfer.py', 'run_bundle.py', 'offline_exec.py', 'validate_artifacts.py', 'command.json')}
    contents['runtime-sources.json'] = (json.dumps(inventory['runtime_sources'], sort_keys=True) + '\n').encode()
    contents['distributions.json'] = (json.dumps(inventory['distributions'], sort_keys=True) + '\n').encode()
    restored, packed, manifest = pack_support(contents)
    transfer['command_sha256'] = manifest['files']['command.json']['sha256']
    injected = {'bootstrap.py': (HERE / 'bootstrap.py').read_bytes(), 'payload.tar.gz': packed,
                'payload.json': (json.dumps(manifest, sort_keys=True) + '\n').encode(),
                'transfer.json': (json.dumps(transfer, sort_keys=True) + '\n').encode()}
    for name, content in injected.items():
        if not 0 < len(content) <= 65536:
            raise ValueError('Provider injected file exceeds its 64KiB API limit: ' + name)
    spec = {'image': args.image, 'containerCommand': '/opt/i4h/arena/.venv/bin/python',
        'args': '-I /opt/isaac-task/bootstrap.py --manifest /opt/isaac-task/payload.json --payload /opt/isaac-task/payload.tar.gz --transfer /opt/isaac-task/transfer.json',
        'environmentVariables': [{'name': name, 'value': 'Y'} for name in
            ('ACCEPT_EULA', 'ISAACSIM_ACCEPT_EULA', 'OMNI_KIT_ACCEPT_EULA')],
        'platform': args.platform, 'preset': args.preset, 'shmSizeBytes': str(args.shm_gib * 1024**3),
        'disk': {'type': 'NETWORK_SSD', 'sizeBytes': str(args.disk_gib * 1024**3)},
        'pricingModel': {'onDemand': {}}, 'timeout': str(args.timeout_seconds) + 's', 'restartAttempts': 0,
        'injectedFiles': [{'containerPath': '/opt/isaac-task/' + name,
                          'content': base64.b64encode(content).decode()} for name, content in sorted(injected.items())]}
    if args.diagnostics_public_ip:
        spec['publicIp'] = True
        spec['sshAuthorizedKeys'] = [args.ssh_public_key.read_text().strip()]
    request = {'metadata': {'parentId': args.project_id, 'name': args.name}, 'spec': spec, 'dryRun': False}
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    save(args.output / 'job-create.private.json', request)
    request['dryRun'] = True
    save(args.output / 'job-dry-run.private.json', request)
    save(args.output / 'receipt.json', {'image': args.image, 'input_sha256': sha(args.input),
        'input_size_bytes': args.input.stat().st_size, 'installation_sha256': sha(args.installation),
        'command_sha256': transfer['command_sha256'], 'request_sha256': sha(args.output / 'job-create.private.json'),
        'dry_run_sha256': sha(args.output / 'job-dry-run.private.json'),
        'injected_file_sha256': {name: hashlib.sha256(content).hexdigest() for name, content in injected.items()},
        'restored_support_files': manifest['files'], 'support_source_identity': manifest['source_identity'],
        'injected_decoded_bytes': sum(map(len, injected.values())),
        'restored_support_bytes': sum(map(len, restored.values())),
        'restart_attempts': 0, 'provider_calls': 0, 'credentials_in_request': 'Scoped URLs only; keep both request files private'})
    print(json.dumps({'request_directory': str(args.output), 'provider_calls': 0,
                      'receipt_sha256': sha(args.output / 'receipt.json')}))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    make = sub.add_parser('bundle')
    make.add_argument('--operation', required=True)
    for name in ('scenarios', 'project'):
        make.add_argument('--' + name, type=Path)
    for name in ('parameters', 'output'):
        make.add_argument('--' + name, type=Path, required=True)
    job = sub.add_parser('render')
    for name in ('image', 'project-id', 'name'):
        job.add_argument('--' + name, required=True)
    for name in ('input', 'installation', 'input-url-file', 'output-url-file', 'claim-url-file', 'output'):
        job.add_argument('--' + name, type=Path, required=True)
    job.add_argument('--platform', default='gpu-l40s-d')
    job.add_argument('--preset', default='1gpu-16vcpu-96gb')
    for name, default in (('disk-gib', 250), ('shm-gib', 16), ('timeout-seconds', 7200),
                          ('science-timeout-seconds', 6600), ('output-max-bytes', 32 * 1024**3)):
        job.add_argument('--' + name, type=positive, default=default)
    job.add_argument('--accept-eula', action='store_true')
    job.add_argument('--diagnostics-public-ip', action='store_true')
    job.add_argument('--ssh-public-key', type=Path)
    args = parser.parse_args()
    bundle(args) if args.mode == 'bundle' else render(args)


if __name__ == '__main__':
    main()
