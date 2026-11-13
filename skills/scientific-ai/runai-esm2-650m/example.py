"""Portable ESM-2 client. Requires boto3 only for owner-bucket upload."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import time
import urllib.error
import urllib.request
from uuid import uuid4

WORKFLOWS = ['score-variants', 'score-sequences', 'extract-representations',
             'predict-contacts', 'logits', 'masked-completion']
parser = argparse.ArgumentParser()
parser.add_argument('--model', choices=['esm2-650m', 'esm2-3b'], default='esm2-650m')
parser.add_argument('--workflow', choices=WORKFLOWS, default='score-variants')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--prepare-only', action='store_true')
parser.add_argument('--negative', action='store_true', help='Wrong WT variant; expect a structured validation failure.')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
members = {'sequences.fasta': '>synthetic\nACDEFGHIKLMNPQRSTVWY\n',
           'variants.csv': ('id,sequence_id,mutations\nidentity,synthetic,A1A\nfirst,synthetic,A1G\n'
                            'last,synthetic,Y20A\nmulti,synthetic,C2S:W19F\n')}
if args.negative:
    if args.workflow != 'score-variants':
        raise ValueError('--negative is the score-variants wrong-WT fixture')
    members['variants.csv'] = 'id,sequence_id,mutations\nwrong-wt,synthetic,Y1A\n'
archive = args.output / 'input.tar.gz'
with archive.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w|') as handle:
    for name, content in members.items():
        data = content.encode(); item = tarfile.TarInfo(name); item.size = len(data); item.mtime = 0
        handle.addfile(item, io.BytesIO(data))
parameters = {}
if args.workflow == 'masked-completion':
    parameters = {'masked_positions': [{'sequence_id': 'synthetic', 'positions': [2, 5]}], 'top_k': 5}
if args.workflow == 'extract-representations':
    parameters = {'layers': [0, 12, 33] if args.model == 'esm2-650m' else [0, 18, 36],
                  'representations': ['per-token', 'mean', 'bos']}
if args.prepare_only:
    print(json.dumps({'archive': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                      'workflow': args.workflow, 'parameters': parameters})); raise SystemExit

placement = {name: os.environ.get('SCIENTIFIC_AI_' + name.upper()) for name in ('region', 'gpu')}
if not all(placement.values()):
    raise ValueError('Set SCIENTIFIC_AI_REGION and SCIENTIFIC_AI_GPU to an allowed explicit placement before upload')
base = os.environ['SCIENTIFIC_AI_BASE_URL'].rstrip('/')
if not base.startswith('https://'):
    raise ValueError('Use the configured HTTPS scientific API origin')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


api_client = urllib.request.build_opener(NoRedirect)
public_client = urllib.request.build_opener(NoRedirect)


def api(path, body=None, key=None):
    headers = {'Authorization': 'Bearer ' + os.environ['SCIENTIFIC_AI_API_KEY']}
    if key:
        headers['Idempotency-Key'] = key
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with api_client.open(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError('Scientific API rejected request: ' + error.read().decode()) from None


schema = api('/v1/models/' + args.model + '?workflow=' + args.workflow)
if args.workflow not in schema['workflows']:
    raise ValueError('Selected workflow is unavailable in discovery')
import boto3
s3 = boto3.session.Session().client('s3', endpoint_url=os.environ['OWNER_S3_ENDPOINT'],
                                   region_name=os.environ.get('AWS_DEFAULT_REGION', 'eu-north1'))
key = os.environ['OWNER_INPUT_PREFIX'].strip('/') + '/' + uuid4().hex + '/input.tar.gz'
s3.upload_file(str(archive), os.environ['OWNER_BUCKET'], key)
request = {'model': args.model, 'workflow': args.workflow, 'parameters': parameters,
           'inputs': [{'name': 'input.tar.gz', 'key': key, 'size_bytes': archive.stat().st_size,
                       'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}]}
request.update(placement)
if args.model == 'esm2-3b':
    request['version'] = 'esm2-3b-476b6399'
submission = {'idempotency_key': uuid4().hex, 'request': request}
(args.output / 'submission.json').write_text(json.dumps(submission, indent=2))
run = api('/v1/runs', request, key=submission['idempotency_key'])
(args.output / 'run.json').write_text(json.dumps(run, indent=2))
for _ in range(720):
    status = api('/v1/runs/' + run['run_id'])
    if status['phase'] in ['SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMED_OUT', 'INTERRUPTED']:
        break
    time.sleep(5)
else:
    raise RuntimeError('Client wait ended; durable run ID remains in run.json. Poll or cancel that run; do not resubmit.')
(args.output / 'status.json').write_text(json.dumps(status, indent=2))
if status['phase'] != 'SUCCEEDED':
    raise RuntimeError(json.dumps(status.get('error', status)))
manifest = api('/v1/runs/' + run['run_id'] + '/artifacts')
for item in manifest['files']:
    relative = PurePosixPath(item['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe artifact path')
    target = args.output / 'results' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    checksum = hashlib.sha256(); total = 0
    with public_client.open(item['download_url'], timeout=60) as source, target.open('xb') as output:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(block); total += len(block); output.write(block)
    if checksum.hexdigest() != item['sha256'] or total != item['size_bytes']:
        raise ValueError('Owner artifact integrity check failed')
print(json.dumps({'run_id': run['run_id'], 'phase': status['phase'], 'verified_files': len(manifest['files'])}))
