"""Run the portable CLI on an owned input bundle, with no fixture identity gates."""
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


def run():
    incoming = Path(os.environ['HOLOSCAN_PROVIDER_INPUT']) / 'input.tar'
    output = Path(os.environ['HOLOSCAN_PROVIDER_OUTPUT'])
    with tempfile.TemporaryDirectory(prefix='holoscan-bundle-') as temporary:
        root = Path(temporary)
        with tarfile.open(incoming, 'r:') as archive:
            seen = set()
            for member in archive.getmembers():
                name = PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts or '\\' in member.name:
                    raise ValueError('Bundle members must use relative POSIX paths')
                if not (member.isfile() or member.isdir()) or name.as_posix() in seen:
                    raise ValueError('Bundle members must be unique regular files or directories')
                seen.add(name.as_posix())
            archive.extractall(root, filter='data')
        parameters = json.loads((root / 'parameters.json').read_text())
        video_file = parameters.get('video_file', 'video.mp4')
        if not isinstance(video_file, str):
            raise ValueError('video_file must be a relative POSIX filename')
        selected = PurePosixPath(video_file)
        if selected.is_absolute() or '..' in selected.parts or '\\' in video_file:
            raise ValueError('video_file must be relative without parent traversal')
        return subprocess.run([
            sys.executable, '-I', '/opt/holoscan-video/holoscan_video.py',
            '--input-video', str(root / video_file),
            '--model', str(root / 'tool_loc_convlstm.onnx'),
            '--output-dir', str(output),
            '--parameters-file', str(root / 'parameters.json'),
        ], check=False).returncode


if __name__ == '__main__':
    sys.exit(run())
