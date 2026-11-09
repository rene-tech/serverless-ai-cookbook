"""A listening chat API is not ready when its required workspace is disconnected."""
import os
from pathlib import Path
import sys
from urllib.request import urlopen


def check():
    with urlopen('http://127.0.0.1:3080/health', timeout=3) as response:
        if response.status != 200:
            raise RuntimeError('Chat API is unavailable')
    if os.environ.get('SCIENTIFIC_REQUIRE_PERSISTENT_STATE', '').lower() == 'true':
        workspace = Path(os.environ.get('SCIENTIFIC_WORKSPACE', '/workspace'))
        # Listing probes the mount, including a dead FUSE connection. Never
        # create files or fall back to container storage during a health check.
        with os.scandir(workspace) as entries:
            next(entries, None)


if __name__ == '__main__':
    try:
        check()
    except Exception as error:
        print(f'Workbench not ready: {error}', file=sys.stderr)
        sys.exit(1)
