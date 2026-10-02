#!/usr/bin/env python3
"""Fill an observed QA login form using a private file, without printing secrets.

Use only a task-owned Playwright CLI session already opened at the intended QA
origin. This is an interactive release check, not an application authentication
helper and not permission to automate another user's browser session.
"""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--login', required=True, type=Path)
    parser.add_argument('--session-name', required=True)
    parser.add_argument('--cli', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    credentials = json.loads(args.login.read_text())
    code = ('async (page) => { await page.getByRole("textbox", {name:"Email",exact:true}).fill(' +
            json.dumps(credentials['email']) + '); '
            'await page.getByRole("textbox",{name:"Password",exact:true}).fill(' +
            json.dumps(credentials['password']) + '); '
            'await page.getByRole("button",{name:"Continue",exact:true}).click(); }')
    result = subprocess.run(['bash', str(args.cli), '-s=' + args.session_name, 'run-code', code],
                            text=True, capture_output=True)
    sanitized = (result.stdout + result.stderr).replace(credentials['password'], '[REDACTED]')
    args.output.write_text(sanitized)
    args.output.chmod(0o600)
    print(json.dumps({'login_command_exit': result.returncode, 'credentials_printed': False}))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
