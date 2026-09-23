"""Exercise the installed client/SDK using isolated, read-only HTTP fault tests.

Pure Python pytest tooling is mounted read-only from the existing test venv;
the image's Python, MCP/httpx2 and application dependencies are not replaced.
No supervisor, external network, customer mount or GPU is started.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


TESTS = ('test_operation_polling.py', 'test_scientific_batch_client.py',
         'test_result_recovery.py', 'test_terminal_diagnostics.py',
         'test_artifact_streaming.py', 'test_artifact_input_streaming.py',
         'test_receipt_storage.py', 'test_receipt_publication.py')


def sha256(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    test_tools = {}
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
               '--tmpfs', '/tmp:rw,nosuid,size=1g', '--cpus', '2', '--memory', '2g',
               '--mount', f'type=bind,source={root},target=/worktree,readonly',
               '--mount', f'type=bind,source={args.output},target=/qualification',
               '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
               '-e', 'PYTHONPATH=/tmp/test-libs:/opt/bionemo:/worktree/templates/hcls-librechat',
               '-e', 'SCIENTIFIC_BATCH_TEST_HELPER=/opt/bionemo/invoke-scientific-batch.py',
               '--entrypoint', '/opt/scientific-client/bin/python']
    for name in ('pytest', '_pytest', 'py', 'pluggy', 'iniconfig', 'pygments', 'packaging'):
        spec = importlib.util.find_spec(name)
        location = Path(next(iter(spec.submodule_search_locations)) if spec.submodule_search_locations else spec.origin)
        target = name if location.is_dir() else name + '.py'
        command += ['--mount', f'type=bind,source={location},target=/tmp/test-libs/{target},readonly']
        test_tools[name] = {'source': str(location), 'files_sha256': {
            str(path.relative_to(location.parent)): sha256(path)
            for path in sorted(location.rglob('*.py')) if location.is_dir()}
            if location.is_dir() else {location.name: sha256(location)}}
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]
    installed = json.loads(subprocess.check_output(command + [args.image, '-c',
        'import hashlib,importlib.metadata,json,sys; from pathlib import Path; '
        'p=Path("/opt/bionemo/invoke-scientific-batch.py"); '
        'print(json.dumps({"python":sys.version,"helper_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),'
        '"mcp":importlib.metadata.version("mcp"),"httpx2":importlib.metadata.version("httpx2")}))']))
    source = root / 'templates/hcls-librechat/scripts/scientific-batch-acceptance.py'
    if installed['helper_sha256'] != sha256(source):
        raise RuntimeError('Installed helper differs from the source under test')
    with (args.output / 'pytest.log').open('x') as log:
        process = subprocess.run(command + [args.image, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            '--basetemp=/tmp/polling-tests', '--junitxml=/qualification/pytest.xml',
            *['/worktree/templates/hcls-librechat/' + test for test in TESTS]], stdout=log, stderr=subprocess.STDOUT)
    suites = ET.parse(args.output / 'pytest.xml').getroot() if (args.output / 'pytest.xml').exists() else []
    counts = {key: sum(int(suite.get(key, 0)) for suite in suites)
              for key in ('tests', 'failures', 'errors', 'skipped')}
    receipt = {'status': 'passed' if process.returncode == 0 else 'failed',
               'recorded_at': datetime.now(timezone.utc).isoformat(),
               'image': args.image, 'image_id': image['Id'],
               'source_revision': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
               'installed': installed, 'counts': counts, 'exit_code': process.returncode,
               'test_sources_sha256': {test: sha256(root / 'templates/hcls-librechat' / test) for test in TESTS},
               'test_tools': test_tools, 'network': 'none', 'gpu': False,
               'customer_bucket_mounted': False, 'scientific_submissions': 0,
               'logs_sha256': {name: sha256(args.output / name) for name in ('pytest.log', 'pytest.xml')
                               if (args.output / name).exists()},
               'customer_ready': False}
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: receipt[key] for key in ('status', 'image', 'counts', 'customer_ready')}))
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
