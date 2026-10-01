#!/usr/bin/env python3
"""Capture installed primary-agent configuration and authenticate a QA instance.

Local runtime metadata is read from the candidate's database, not by widening
the end user's VIEW permission to expose server-owned agent configuration.
"""
import argparse
import json
from pathlib import Path
import subprocess
import httpx
from prepare_default_release import private_json, installed_agent
from replay_agent_instructions import UA

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', type=Path, required=True)
p.add_argument('--url', required=True)
p.add_argument('--container', required=True)
a = p.parse_args()
login = json.loads((a.root / 'login.json').read_text())
with httpx.Client(base_url=a.url, headers={'User-Agent': UA, 'Origin': a.url}, timeout=30) as c:
    response = c.post('/api/auth/login', json=login)
    response.raise_for_status()
    private_json(a.root / 'session.json', response.json())
agent = installed_agent(a.container)
private_json(a.root / 'agent.json', agent)
(a.root / 'instructions.md').write_text(agent['instructions'])
print(json.dumps({'container': a.container, 'model': agent['model'],
                  'instruction_characters': len(agent['instructions']),
                  'reasoning_effort': agent.get('model_parameters', {}).get('reasoning_effort')}))
