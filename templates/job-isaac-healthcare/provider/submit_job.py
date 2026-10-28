"""One reviewed SDK dry run or finite Job create. Never retries an unknown create."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def main():
    from nebius.aio.cli_config import Config
    from nebius.api.nebius.ai.v1 import CreateJobRequest, JobServiceClient
    from nebius.sdk import SDK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--successful-dry-run', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    if sha(args.request) != args.request_sha256:
        raise ValueError('The reviewed request bytes changed')
    raw = json.loads(args.request.read_bytes())
    if raw.get('dryRun') is not (not args.execute):
        raise ValueError('Real create requires --execute and explicit dryRun:false')
    request = CreateJobRequest.from_json(args.request.read_bytes())
    if not re.fullmatch(r'[^@\s]+@sha256:[0-9a-f]{64}', request.spec.image):
        raise ValueError('Use the complete immutable image reference')
    if request.spec.restart_attempts != 0:
        raise ValueError('This finite transfer recipe does not automatically repeat science')
    if args.execute:
        if not args.successful_dry_run:
            raise ValueError('Bind the successful dry-run receipt for the exact scientific request')
        dry = json.loads(args.successful_dry_run.read_bytes())
        if dry['operation_id'] != 'dry-run' or dry['resource_id'] or dry['done'] is not True or dry['successful'] is not True:
            raise ValueError('Dry run was not a resource-free success')
        previous = Path(dry['request']['path'])
        if sha(previous) != dry['request']['sha256']:
            raise ValueError('Dry-run request evidence changed')
        wanted = json.loads(previous.read_bytes())
        if wanted.get('dryRun') is not True:
            raise ValueError('Dry-run evidence belongs to another request type')
        wanted['dryRun'] = False
        if wanted != raw:
            raise ValueError('The real request differs from the successful dry run')
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    reference = {'path': str(args.request.resolve()), 'sha256': args.request_sha256}
    write(args.output / 'intent.json', {'request': reference, 'dry_run': not args.execute,
          'maximum_create_rpc_attempts': 1, 'unknown_outcome_action': 'GET-only reconciliation; never resubmit'})
    directory_fd = os.open(args.output, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    sdk = SDK(config_reader=Config(profile=args.profile, max_retries=1),
              federation_invitation_no_browser_open=True)
    try:
        operation = JobServiceClient(sdk).create(request, retries=1, timeout=60, per_retry_timeout=60).wait()
        write(args.output / 'operation.private.json', json.loads(operation.raw().to_json()))
        receipt = {'request': reference, 'operation_id': operation.id, 'resource_id': operation.resource_id,
                   'done': operation.done(), 'successful': operation.successful() if operation.done() else None}
        write(args.output / 'receipt.json', receipt)
        if not args.execute and not (operation.id == 'dry-run' and not operation.resource_id
                                    and operation.done() and operation.successful()):
            raise RuntimeError('Dry run did not complete successfully')
        if args.execute and not operation.resource_id:
            raise RuntimeError('Create outcome needs GET-only reconciliation; do not repeat it')
        if args.execute and operation.done() and not operation.successful():
            raise RuntimeError('Create operation failed; retain its ID and do not repeat it')
        print(json.dumps(receipt))
    except BaseException as error:
        write(args.output / 'unknown-or-failed.json', {'error_type': type(error).__name__,
              'action': 'Retain every receipt; inspect the returned operation/Job by GET. Do not repeat create.'})
        print('Request failed or is uncertain; retain this packet and reconcile by GET only.', file=sys.stderr)
        return 1
    finally:
        sdk.sync_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
