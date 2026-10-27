"""Merge authored builder settings without replacing explicit outer controls."""

from .contract import schema


def merge_workflow_arguments(upstream_defaults, supplied):
    if not isinstance(upstream_defaults, dict) or not isinstance(supplied, dict):
        raise TypeError('Workflow arguments must be JSON objects')
    owners = {name: name for name in schema('parameters')['properties']}
    owners.update({'episode': 'replay_episodes', 'seconds': 'idle_seconds',
                   'presets': 'physics', 'num_envs': 'envs'})
    conflicts = sorted(set(upstream_defaults) & set(supplied) & owners.keys())
    if conflicts:
        detail = ', '.join(f'{name} is owned by parameters.{owners[name]}' for name in conflicts)
        raise ValueError(f'workflow_args conflict with explicit outer controls: {detail}')
    return {**upstream_defaults, **supplied}
