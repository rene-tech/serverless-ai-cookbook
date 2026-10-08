"""Make private browser state for an operator-supplied QA login. Never print keys."""
import argparse
import json
import os
from pathlib import Path
import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', required=True)
parser.add_argument('--credentials', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
os.umask(0o077)
credentials = json.loads(args.credentials.read_text())
with httpx.Client(base_url=args.url, headers={'Origin': args.url,
        'User-Agent': 'Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36'}, timeout=45) as client:
    response = client.post('/api/auth/login', json={k: credentials[k] for k in ('email', 'password')})
    response.raise_for_status()
    state = {'cookies': [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path,
                         'expires': c.expires or -1, 'secure': c.secure,
                         'httpOnly': c.has_nonstandard_attr('HttpOnly'), 'sameSite': 'Lax'}
                        for c in client.cookies.jar], 'origins': []}
    args.output.write_text(json.dumps(state))
    args.output.chmod(0o600)
print(json.dumps({'login': True, 'private_browser_state_written': True}))
