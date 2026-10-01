#!/usr/bin/env python3
"""Verify actual replay delivery and authenticated downloads, never resubmit work.

This is technical artifact/measurement evidence, not force-field accuracy or
scientific convergence. Raw customer responses remain in the private replay.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs, urlsplit

import httpx
from replay_agent_instructions import UA, summarize, save


def read_tool_output(value):
    try:
        data = json.loads(value)
        if isinstance(data, list) and len(data) == 1 and data[0].get('type') == 'text':
            data = json.loads(data[0]['text'])
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def tool_failures(calls):
    """A later answer must not hide failed commands or MCP transport errors."""
    failures = []
    for call in calls:
        output = read_tool_output(call.get('output'))
        raw = str(call.get('output', ''))
        if (output.get('status') in {'failed', 'timed_out', 'interrupted'} or
                output.get('isError') is True or call.get('isError') is True or
                re.search(r'MCP error -?\d+|McpError|Request timed out|Error executing tool', raw)):
            failures.append({'tool': call.get('name'), 'status': output.get('status', 'tool_error'),
                             'job_id': output.get('job_id'), 'exit_code': output.get('exit_code')})
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--login', type=Path, required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-rejection-case', action='append', default=[],
                        help='Explicit negative fixture, still retained in evidence; never excludes transport errors.')
    parser.add_argument('--require-report-case', action='append', default=[],
                        help='Named cases must finish with a verified report; a plan or progress message does not pass.')
    args = parser.parse_args()
    os.umask(0o077)
    test = Path(__file__).parents[2] / 'test_prepare_openff.py'
    subprocess.run(['docker', 'cp', str(test), args.container + ':/tmp/test_prepare_openff.py'], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(['docker', 'cp', str(test.with_name('prepare-openff.py')),
                    args.container + ':/tmp/prepare-openff.py'], check=True, stdout=subprocess.DEVNULL)
    rows = []
    with httpx.Client(base_url=args.base_url, headers={'Origin': args.base_url, 'User-Agent': UA}, timeout=60) as client:
        login = client.post('/api/auth/login', json=json.loads(args.login.read_text()))
        login.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + login.json()['token']
        for path in sorted(args.replay.glob('*/*/messages.json')):
            messages = json.loads(path.read_text())
            summary = summarize(messages)
            parts = [p for m in messages if not m.get('isCreatedByUser') for p in m.get('content', [])]
            calls = [p['tool_call'] for p in parts if p.get('type') == 'tool_call']
            reports, directories, downloads = [], set(), []
            failures = list(summary['errors'])
            observed_failures = tool_failures(calls)
            for error in observed_failures:
                expected = (path.parent.name in args.expected_rejection_case and
                            error['status'] == 'failed' and error['exit_code'] is not None)
                if not expected:
                    failures.append('unexpected failed tool: ' + str(error['tool']))
            warnings_path = path.parent / 'transport-warnings.json'
            if warnings_path.exists() and json.loads(warnings_path.read_text()):
                failures.append('replay transport warnings')
            if summary['empty_answer'] or summary['unfinished']:
                failures.append('incomplete agent answer')
            for call in calls:
                output = read_tool_output(call.get('output'))
                if output.get('schema') == 'scientific-verified-delivery/v1':
                    reports.append(output['report_markdown'])
                if call['name'].startswith('prepare_openff_ligand'):
                    value = read_tool_output(call['args'])
                    if output.get('status') != 'needs_user_input':
                        directories.add(output.get('output_directory') or str(Path('/workspace') / value['output_directory']))
            for report in reports:
                if report not in summary['visible_text']:
                    failures.append('verified report was modified or omitted from the final answer')
            if path.parent.name in args.require_report_case and not reports:
                failures.append('promised verified result was not delivered')
            for url in sorted(set(re.findall(r'\]\((/demos\?[^)]+)\)', summary['visible_text']))):
                query = parse_qs(urlsplit(url).query)
                file = query.get('file', [None])[0]
                if not file:
                    response = client.get('/api/scientific-demos/workspace', params={'path': query.get('path', [''])[0]})
                else:
                    response = client.get('/api/scientific-demos/workspace/file', params={'path': file})
                if response.status_code != 200:
                    failures.append(f'delivered workspace link returned HTTP {response.status_code}')
                downloads.append({'path': file or query.get('path', [''])[0], 'http_status': response.status_code,
                                  'bytes': len(response.content), 'sha256': hashlib.sha256(response.content).hexdigest()})
            preparations = []
            for directory in sorted(directories):
                checked = subprocess.run(['docker', 'exec', '-e', 'OPENFF_PREPARATION_FIXTURE=' + directory,
                    args.container, '/opt/openff/bin/python', '/tmp/test_prepare_openff.py', '-v'],
                    text=True, capture_output=True, timeout=120)
                if checked.returncode:
                    failures.append('independent ligand file/charge/identity validation failed')
                # Keep full test diagnostics private, not in console/telemetry.
                save(path.parent / 'artifact-validation.json', {'exit_code': checked.returncode,
                     'diagnostic': checked.stdout + checked.stderr})
                prefix = str(Path(directory).relative_to('/workspace'))
                response = client.get('/api/scientific-demos/workspace/file', params={'path': prefix + '/manifest.json'})
                response.raise_for_status()
                manifest = response.json()
                verified = 0
                for name, expected in manifest['files'].items():
                    fetched = client.get('/api/scientific-demos/workspace/file', params={'path': prefix + '/' + name})
                    if (fetched.status_code != 200 or len(fetched.content) != expected['bytes'] or
                            hashlib.sha256(fetched.content).hexdigest() != expected['sha256']):
                        failures.append('downloaded artifact bytes differ from manifest')
                    else:
                        verified += 1
                preparations.append({'directory': directory, 'file_validation_pass': checked.returncode == 0,
                                     'hash_verified_http_downloads': verified})
            rows.append({'case_id': path.parent.name, 'verified_report_count': len(reports),
                         'delivered_links': downloads, 'preparations': preparations,
                         'observed_tool_failures': observed_failures,
                         'failures': failures, 'technical_delivery_pass': not failures})
    result = {'scope': 'technical delivery, not scientific accuracy/convergence', 'cases': rows,
              'passed': bool(rows) and all(r['technical_delivery_pass'] for r in rows)}
    save(args.output, result)
    print(json.dumps({'cases': len(rows), 'passed': result['passed'],
                      'failed_cases': [r['case_id'] for r in rows if not r['technical_delivery_pass']]}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
