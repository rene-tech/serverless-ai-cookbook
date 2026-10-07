#!/usr/bin/env python3
"""Replay catalog conversations through QA LibreChat, without scientific App jobs.

Uses the real authenticated agent/chat and message routes, not direct LLM calls.
Keep --output private: it contains chat transcripts, but never login credentials.
Every accepted conversation ID is saved before polling so retries do not duplicate
turns. Invoke separately for two unchanged-release cohorts.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

import httpx

CASES = {
    'all': ['fetch all models that are available to me'],
    'design-and-list': [
        'Help me design and rank molecular or protein candidates. Start from a live authorized catalog and ask about the target, public reference data and experimental decision. Inspect schemas before chaining Apps. Define fixed preparation, candidate counts, filters, ranking metrics, failure handling and a held-out or experimental validation plan. Ask before compute, upload large inputs as artifacts, track operation IDs, and keep generated hypotheses separate from measured binding or function.',
        'fetch all models that are available to me',
    ],
    'reproduction': ['Help me reproduce a published scientific result using public data and the Scientific AI Apps available to my key. Ask for my field or suggest one realistic paper. Search primary sources, verify the paper, code, dataset, license and reported metric, then inspect the live App catalog and exact schemas. Build a bounded reproduction with fixed inputs, preprocessing, seeds, metrics and artifact provenance. Do not claim reproduction from a smoke test. Ask before submitting compute, save every operation in the Runs panel, and compare the terminal result with the paper.'],
    'md': ['Which molecular dynamics Apps can I access? List them without running a simulation.'],
    'single-cell': ['Which single-cell analysis Apps can I access? Do not run any model.'],
}
SAFE_TOOLS = {
    'workbench_list_apps_mcp_scientific-demos', 'tavily_search_mcp_tavily',
    'get_model_schema_mcp_scientific-ai-apps', 'read_file', 'tool_search',
}


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with open(temporary, 'w', opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        json.dump(value, stream, indent=2)
    temporary.replace(path)


def normalize(text):
    return re.sub(r'[^a-z0-9]+', '', text.lower())


def run_case(args, case, token, expected):
    origin = args.origin.rstrip('/')
    headers = {'Origin': origin, 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/140.0.0.0 Safari/537.36', 'Authorization': 'Bearer ' + token}
    parent, conversation = '00000000-0000-0000-0000-000000000000', None
    checks = []
    with httpx.Client(base_url=origin, headers=headers, timeout=90) as client:
        for turn, prompt in enumerate(CASES[case]):
            started = time.monotonic()
            prefix = args.output / f'{case}-{turn}'
            intent_path, accepted_path = prefix.with_suffix('.intent.json'), prefix.with_suffix('.accepted.json')
            if accepted_path.exists():
                accepted = json.loads(accepted_path.read_text())
                intent = json.loads(intent_path.read_text())
            else:
                if intent_path.exists():
                    raise RuntimeError('Ambiguous chat admission: reconcile retained intent before retry')
                intent = {'endpoint': 'agents', 'agent_id': 'agent_nebius_scientific_ai',
                          'model': 'agent_nebius_scientific_ai', 'text': prompt,
                          'conversationId': conversation, 'parentMessageId': parent,
                          'messageId': str(uuid.uuid4()), 'clientRequestId': 'catalog-qa-' + str(uuid.uuid4()),
                          'isContinued': False, 'isRegenerate': False}
                save(intent_path, intent)
                response = client.post('/api/agents/chat', json=intent)
                response.raise_for_status()
                accepted = response.json()
                save(accepted_path, accepted)
            conversation = accepted['conversationId']
            deadline = time.monotonic() + 300
            while True:
                response = client.get('/api/agents/chat/status/' + conversation)
                response.raise_for_status()
                status = response.json()
                response = client.get('/api/messages/' + conversation)
                response.raise_for_status()
                rows = response.json()
                rows = rows if isinstance(rows, list) else rows['messages']
                last = next((m for m in reversed(rows) if not m.get('isCreatedByUser')
                             and m.get('parentMessageId') == intent['messageId']), None)
                if not status.get('active') and last and not last.get('unfinished'):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Retained conversation still running: ' + conversation)
                time.sleep(2)
            save(prefix.with_suffix('.messages.json'), rows)
            if last.get('error'):
                raise RuntimeError('Agent error; inspect retained messages')
            calls = [x['tool_call'] for x in last.get('content', []) if x.get('type') == 'tool_call']
            catalog_calls = [x for x in calls if x['name'] == 'workbench_list_apps_mcp_scientific-demos']
            assert len(catalog_calls) == 1, (case, turn, 'catalog call count', len(catalog_calls))
            assert all(x['name'] in SAFE_TOOLS for x in calls), 'Unexpected tool; inspect private trace'
            assert catalog_calls[0].get('runStepStatus') == 'completed'
            catalog = json.loads(catalog_calls[0]['output'])
            assert catalog['catalog_scope'] == 'full_authorized_catalog'
            assert catalog['count'] == catalog['total_authorized_count'] == len(expected)
            assert sorted(x['model_id'] for x in catalog['data']) == sorted(expected)
            text = '\n'.join(x.get('text', '') for x in last.get('content', []) if x.get('type') == 'text')
            # Full catalog requests must enumerate every returned App, not just
            # show the correct tool output while the prose silently drops a group.
            if case == 'all' or (case == 'design-and-list' and turn == 1):
                flattened = normalize(text)
                missing = [x['model_id'] for x in catalog['data']
                           if normalize(x['model_id']) not in flattened and normalize(x['display_name']) not in flattened]
                assert not missing, ('Final answer omitted Apps', missing)
            if case == 'md':
                assert all(normalize(x['model_id']) in normalize(text)
                           for x in catalog['data'] if x['use_case'] == 'Molecular dynamics')
            if case == 'single-cell':
                assert 'scvi' in normalize(text) and 'scanvi' in normalize(text)
            parent = last['messageId']
            checks.append({'case': case, 'turn': turn, 'conversation_id': conversation,
                           'message_id': parent, 'catalog_calls': 1, 'catalog_count': catalog['count'],
                           'tools': [x['name'] for x in calls], 'final_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                           'final_text_chars': len(text), 'observed_wall_seconds': round(time.monotonic() - started, 3),
                           'passed': True})
            save(prefix.with_suffix('.receipt.json'), checks[-1])
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--login-file', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert not args.output.stat().st_mode & 0o077, 'Output must be private'
    login = json.loads(args.login_file.read_text())
    with httpx.Client(base_url=args.origin, headers={'Origin': args.origin,
                      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/140.0.0.0 Safari/537.36'}, timeout=60) as client:
        response = client.post('/api/auth/login', json=login)
        response.raise_for_status()
        token = response.json()['token']
        response = client.get('/api/scientific-demos/apps', headers={'Authorization': 'Bearer ' + token})
        response.raise_for_status()
        expected = sorted(x['id'] for x in response.json()['data'])
        assert expected, 'QA key must have a nonempty catalog'
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_case, args, case, token, expected) for case in CASES]
        rows = [row for future in futures for row in future.result()]
    receipt = {'origin': args.origin, 'expected_apps': expected, 'cases': len(CASES),
               'completed_turns': len(rows), 'rows': rows, 'passed': True,
               'model_operations_submitted': 0, 'uses_customer_credentials': False}
    save(args.output / 'summary.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
