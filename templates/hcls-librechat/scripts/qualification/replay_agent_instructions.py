#!/usr/bin/env python3
"""Replay private customer prompts through an isolated LibreChat, never raw LLM mocks.

The manifest contains case_id/prompt pairs and stays outside Git with customer
inputs. A watchdog aborts only this harness's own chat generation. Scientific
jobs are not resubmitted or cancelled by an observation timeout. Results are
measurements for human/fixture evaluation, not automatic scientific passes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlsplit

import httpx

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'


def save(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as handle:
        json.dump(value, handle, indent=2)


def summarize(messages):
    assistants = [m for m in messages if not m.get('isCreatedByUser')]
    parts = [p for m in assistants for p in (m.get('content') or [])]
    calls = [p['tool_call'] for p in parts if p.get('type') == 'tool_call']
    return {
        'visible_text': '\n'.join(p.get('text', '') for p in parts if p.get('type') == 'text'),
        'reasoning_characters': sum(len(p.get('think', '')) for p in parts if p.get('type') == 'think'),
        'tool_calls': len(calls), 'tool_names': [c.get('name') for c in calls],
        'tool_seconds': sum(c.get('runStepDurationMs', 0) or 0 for c in calls) / 1000,
        'errors': ([p.get('error') for p in parts if p.get('type') == 'error']
                   + [m.get('text', 'message-level error') for m in assistants if m.get('error')]),
        'empty_answer': not any(p.get('text', '').strip() for p in parts if p.get('type') == 'text'),
        'unfinished': any(m.get('unfinished') for m in assistants),
        # LibreChat's message tokenCount is not provider billing/usage evidence.
        'provider_usage': None, 'scientific_pass': None,
    }


def run_case(args, token, original, case, model):
    variant = model.replace('/', '_')
    if args.reasoning_effort:
        variant += '-' + args.reasoning_effort
    directory = args.output / variant / case['case_id']
    if directory.exists():
        raise ValueError('Refusing to overwrite a previous replay')
    directory.mkdir(parents=True, mode=0o700)
    headers = {'Origin': args.base_url, 'User-Agent': UA, 'Authorization': 'Bearer ' + token}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=45) as client:
        instructions = args.instruction_text
        output_directory = f'/workspace/replays/{args.cohort_id}/{variant}/{case["case_id"]}'
        instructions += ('\n\nFor this isolated replay, put new output files under '
                         f'/workspace/replays/{args.cohort_id}/{variant}/{case["case_id"]}. '
                         'Preserve existing input files.')
        fields = ('tools', 'mcpServerNames', 'skills_enabled', 'artifacts', 'provider')
        candidate = {k: original[k] for k in fields if k in original}
        candidate.update({'name': 'Instruction replay ' + case['case_id'], 'instructions': instructions,
            'model': model, 'model_parameters': {'model': model, 'max_tokens': 16384,
                                               'maxContextTokens': 131072}})
        if args.reasoning_effort:
            candidate['model_parameters']['reasoning_effort'] = args.reasoning_effort
        if args.use_seeded_agent:
            if model != original['model'] or args.reasoning_effort:
                raise ValueError('Seeded-agent qualification must retain its actual model/settings')
            agent = original
            instructions = original['instructions']
        else:
            response = client.post('/api/agents', json=candidate)
            response.raise_for_status()
            agent = response.json()
        save(directory / 'agent.json', agent)
        agent_id = agent['id']
        payload = {'endpoint': 'agents', 'agent_id': agent_id, 'model': agent_id,
            'text': case['prompt'].replace('{output}', output_directory), 'conversationId': None,
            'parentMessageId': '00000000-0000-0000-0000-000000000000',
            'messageId': str(uuid.uuid4()), 'clientRequestId': str(uuid.uuid4()),
            'isContinued': False, 'isRegenerate': False}
        start = time.monotonic()
        response = client.post('/api/agents/chat', json=payload)
        response.raise_for_status()
        submitted = response.json()
        save(directory / 'submission.json', submitted)
        cid = submitted['conversationId']
        # Status reads do not submit inference. The real client uses this same
        # durable generation when reconnecting; no synthetic assistant loop.
        watchdog = False
        while True:
            status_response = client.get('/api/agents/chat/status/' + cid)
            status_response.raise_for_status()
            status = status_response.json()
            save(directory / 'status.json', status)
            if not status.get('active'):
                break
            if time.monotonic() - start > args.deadline:
                aborted = client.post('/api/agents/chat/abort', json={'conversationId': submitted['streamId']})
                save(directory / 'abort.json', {'status': aborted.status_code, 'body': aborted.json()})
                watchdog = True
                break
            time.sleep(3)
        messages_response = client.get('/api/messages/' + cid)
        messages_response.raise_for_status()
        messages = messages_response.json()
        save(directory / 'messages.json', messages)
        result = {'case_id': case['case_id'], 'model': model, 'conversation_id': cid,
            'cohort_id': args.cohort_id,
            'reasoning_effort': (original.get('model_parameters', {}).get('reasoning_effort')
                                 if args.use_seeded_agent else args.reasoning_effort),
            'seeded_agent': args.use_seeded_agent, 'output_directory': output_directory,
            'seconds': round(time.monotonic() - start, 3), 'watchdog_aborted': watchdog,
            'instructions_sha256': hashlib.sha256(instructions.encode()).hexdigest(),
            'core_instructions_sha256': hashlib.sha256(args.instruction_text.encode()).hexdigest(),
            **summarize(messages)}
        save(directory / 'summary.json', result)
        print(json.dumps({k: v for k, v in result.items() if k not in
                         ('visible_text', 'tool_names')}), flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--agent', type=Path, required=True)
    parser.add_argument('--instructions', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--model', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline', type=int, default=180)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--reasoning-effort', choices=['low', 'high', 'max'])
    parser.add_argument('--use-seeded-agent', action='store_true',
                        help='Exercise the actual deployed primary agent unchanged')
    parser.add_argument('--allow-candidate-host',
                        help='Explicit hostname of the isolated HTTPS qualification endpoint')
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    local = parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
    remote = (parsed.scheme == 'https' and args.allow_candidate_host
              and parsed.hostname == args.allow_candidate_host)
    if not (local or remote) or parsed.username or parsed.password:
        parser.error('Use loopback or explicitly name the isolated HTTPS candidate host')
    token = json.loads(args.session.read_text())['token']
    original = json.loads(args.agent.read_text())
    args.instruction_text = args.instructions.read_text().strip()
    args.cohort_id = uuid.uuid4().hex
    cases = json.loads(args.manifest.read_text())['cases']
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_case, args, token, original, case, model)
                   for case in cases for model in args.model]
        results = [f.result() for f in futures]
    save(args.output / 'summary.json', results)


if __name__ == '__main__':
    main()
