"""Prepare/create a same-owner replacement from a private endpoint backup.

No secret is resolved into the request: existing MysteryBox and bucket selectors
are preserved. Creation requires the predecessor to be stopped. This helper does
not delete endpoints; qualification and deletion remain explicit later steps.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import traceback

from nebius.aio.cli_config import Config
from nebius.api.nebius.ai.v1 import CreateEndpointRequest, EndpointServiceClient
from nebius.sdk import SDK


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--profile', default='sandbox2')
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if '@sha256:' not in args.image:
        raise ValueError('Use the qualified immutable workbench image')
    backup = json.loads((args.backup / 'endpoint-private.json').read_text())
    receipt = json.loads((args.backup / 'receipt.json').read_text())
    if receipt['endpoint'] != backup['metadata']['id'] or not receipt['read_only']:
        raise ValueError('Missing matching account backup')
    live = json.loads(subprocess.check_output(['nebius', '--profile', args.profile, 'ai', 'endpoint',
        'get', '--id', receipt['endpoint'], '--format', 'json']))
    if live['spec'] != backup['spec']:
        raise ValueError('Predecessor configuration changed; recapture it first')
    if args.create and live['status']['state'] != 'STOPPED':
        raise ValueError('Stop the exact predecessor before enabling another same-user supervisor')
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = copy.deepcopy(backup['spec'])
    spec['image'] = args.image
    for variable in spec['environment_variables']:
        if variable['name'] == 'SCIENTIFIC_STUDY_OWNER_MODE':
            variable['value'] = 'stopped-predecessor'
    request = {'metadata': {'parent_id': backup['metadata']['parent_id'], 'name': args.name}, 'spec': spec}
    (args.output / 'request-private.json').write_text(json.dumps(request, indent=2))
    typed = CreateEndpointRequest.from_json(json.dumps(request))
    typed.dry_run = not args.create
    sdk = SDK(config_reader=Config(profile=args.profile), user_agent_prefix='scientific-ai-workbench-replacement/2026.09.23')
    try:
        operation = EndpointServiceClient(sdk).create(typed).wait()
        operation.sync_wait(timeout=600)
        result = {'dry_run': not args.create, 'predecessor': receipt['endpoint'],
            'image': args.image, 'operation_id': operation.id, 'resource_id': operation.resource_id,
            'done': operation.done(), 'bucket_changed': False, 'predecessor_deleted': False}
        (args.output / 'receipt.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
    except Exception:
        (args.output / 'error-private.log').write_text(traceback.format_exc())
        raise SystemExit('Replacement request failed; private diagnostics retained, no endpoint deleted')
    finally:
        sdk.sync_close()


if __name__ == '__main__':
    main()
