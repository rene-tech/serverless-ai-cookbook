"""Compare supported account exports after restore, without emitting private data."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


AGENT_FIELDS = ('id', 'name', 'description', 'instructions', 'tools', 'model',
                'model_parameters', 'provider', 'category', 'conversation_starters',
                'mcpServerNames', 'skills_enabled', 'artifacts')
USER_FIELDS = ('email', 'name', 'username', 'role', 'provider', 'emailVerified')


def body(directory, name):
    return json.loads((directory / (name + '.json')).read_text())['body']


def projection(value, fields):
    return {name: value.get(name) for name in fields}


def verify(before, after, restore):
    original = json.loads((before / 'receipt.json').read_text())
    restored = json.loads((restore / 'receipt.json').read_text())
    if restored['conversations_verified'] != original['conversations']:
        raise ValueError('Restored conversation count differs')
    if projection(body(before, 'account-user'), USER_FIELDS) != projection(body(after, 'account-user'), USER_FIELDS):
        raise ValueError('Seeded account profile differs')
    for name in ('projects', 'presets', 'favorites', 'tool-favorites', 'active-skills'):
        if body(before, name) != body(after, name):
            raise ValueError(name + ' differs; do not claim account preservation')
    agents = 0
    for path in before.glob('agent-*-details.json'):
        current = after / path.name
        if not current.exists():
            raise ValueError('A seeded agent is missing')
        old_detail = json.loads(path.read_text())['body']
        new_detail = json.loads(current.read_text())['body']
        if projection(old_detail, AGENT_FIELDS) != projection(new_detail, AGENT_FIELDS):
            raise ValueError('A seeded agent configuration differs')
        agents += 1
    old_operations = {row['id'] for row in body(before, 'runs')['data']}
    new_operations = {row['id'] for row in body(after, 'runs')['data']}
    if not old_operations.issubset(new_operations):
        raise ValueError('Existing platform operation history is incomplete')
    old_studies = {row['id']: row for row in body(before, 'studies')['data']}
    new_studies = {row['id']: row for row in body(after, 'studies')['data']}
    for study_id, old in old_studies.items():
        if old.get('state') not in ('failed', 'completed', 'cancelled'):
            raise ValueError('This migration verifier does not claim active-study continuity')
        current = new_studies.get(study_id, {})
        if projection(old, ('state', 'status', 'completed_steps', 'output_directory')) != projection(current, ('state', 'status', 'completed_steps', 'output_directory')):
            raise ValueError('Existing bucket-backed study differs')
    return {
        'status': 'passed', 'scope': 'supported account import and persistent platform history',
        'conversations': restored['conversations_verified'], 'messages': restored['messages_verified'],
        'images': restored.get('images_restored', 0), 'seeded_agents_verified': agents,
        'existing_platform_operations_verified': len(old_operations),
        'terminal_bucket_studies_verified': len(old_studies),
        'mongo_database_restored': False, 'arbitrary_execution_state_migrated': False,
        'transient_inline_ui_handles_migrated': False, 'customer_ready': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--after', required=True, type=Path)
    parser.add_argument('--restore', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.before, args.after, args.restore)
    result['recorded_at'] = datetime.now(timezone.utc).isoformat()
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
