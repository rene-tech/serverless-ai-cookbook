"""Public workflow presentation; native operations are the only public job IDs.

This module does not alter the immutable scientific executor or its receipts.
Saved output directories locate workflows with zero, one or several native jobs.
"""
import argparse
import copy
import json
import re
from urllib.parse import urlencode

from scientific_study import (path_in_workspace, owner_identity, get, request_cancel,
                              list_studies, engine_status)

NATIVE_OPERATION = re.compile(r'op-[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?')


def native_operation(value):
    return isinstance(value, str) and NATIVE_OPERATION.fullmatch(value) is not None


def public_workflow(value):
    """Expose native jobs, never the supervisor's private receipt-directory key.

    A workflow may prepare inputs before admission, run several native jobs, or
    do only local analysis. Its saved output directory locates that workflow;
    it is not another execution identity or an operation-ID resolver.
    """
    result = {key: copy.deepcopy(value[key]) for key in (
        'title', 'state', 'phase', 'current_step', 'completed_steps',
        'created_at', 'updated_at', 'finished_at', 'failure', 'cancellation_failure',
        'admission_unknown', 'cancellation_unknown', 'queue_blocked', 'artifacts',
        'completion_summaries', 'model_progress', 'output_directory', 'step_count',
        'study_admission', 'reused_existing_study', 'new_study_admitted',
        'cancellation_requested') if key in value}
    result['durable_workflow'] = True
    result.setdefault('state', 'admission_pending')
    result['operations'] = []
    unconfirmed_identity = False
    for step_id, step in value.get('steps', {}).items():
        candidates = ([{'operation_id': step['operation_id'], 'state': step.get('state')}]
                      if step.get('operation_id') else [])
        candidates.extend(step.get('operations', []))
        for operation in candidates:
            identifier = operation.get('operation_id')
            if native_operation(identifier):
                result['operations'].append({'step_id': step_id, 'operation_id': identifier,
                    'state': operation.get('state', operation.get('status'))})
            elif identifier:
                unconfirmed_identity = True
    for measurement in result.get('model_progress', []):
        if not native_operation(measurement.get('operation_id')):
            unconfirmed_identity = unconfirmed_identity or bool(measurement.get('operation_id'))
            measurement.pop('operation_id', None)
    if len(result['operations']) == 1:
        result['operation_id'] = result['operations'][0]['operation_id']
    result['operation_admission'] = ('unknown' if unconfirmed_identity or value.get('admission_unknown') or
        value.get('study_admission') == 'unknown' else
        'admitted' if result['operations'] else 'not_admitted')
    result['progress_url'] = '/demos?' + urlencode({'tab': 'runs', 'workflow': value['output_directory']})
    result['guidance'] = (
        'Only operation_id values identify Serverless jobs. Before a model phase is admitted, '
        'no platform job ID exists. The workflow supervisor continues preparation, model work '
        'and analysis independently of chat. Observe this saved output_directory with '
        'read_scientific_workflow or the live progress link; never resubmit to poll. '
        'Report measured model_progress units/rates, freshness and durable progress, '
        'not hardware or inferred speed.')
    result['next_observation'] = {'tool_name': 'read_scientific_workflow',
        'arguments': {'output_directory': value['output_directory']}}
    return result


def workflow_record(output_directory):
    """Resolve an owned workspace binding, not a public alias for a native job."""
    output = path_in_workspace(output_directory)
    binding = json.loads((output / 'study-binding.json').read_bytes())
    if binding.get('owner') != owner_identity():
        raise ValueError('Workflow belongs to a different dedicated owner.')
    record = get(binding['study_id'])
    if record['output_directory'] != str(output):
        raise ValueError('Workflow output binding does not match its saved receipt.')
    return record


def read_workflow(output_directory):
    return public_workflow(workflow_record(output_directory))


def cancel_workflow(output_directory):
    record = workflow_record(output_directory)
    return public_workflow(request_cancel(record['id']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--list', action='store_true')
    action.add_argument('--status')
    action.add_argument('--cancel')
    args = parser.parse_args()
    if args.list:
        health = engine_status()
        result = {'data': [public_workflow(item) for item in list_studies()],
                  'engine': {key: health[key] for key in ('configured', 'alive', 'last_observed_at')}}
    elif args.status:
        result = read_workflow(args.status)
    else:
        result = cancel_workflow(args.cancel)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
