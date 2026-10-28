"""The trusted controller selects the real authored-code interpreter explicitly."""

import json
from pathlib import Path

import pytest

from i4h_interactive import native_server


def test_controller_command_does_not_substitute_its_own_python(tmp_path):
    config = {
        "image": "registry.example/worker@sha256:" + "a" * 64,
        "runtime_python": "/opt/i4h/arena/.venv/bin/python",
    }
    source = tmp_path / "worker.json"
    source.write_text(json.dumps(config))
    selected = native_server.load_settings(source)
    spec = tmp_path / "workflow.json"
    command = native_server.workflow_command(selected, spec)
    assert command == [
        "/opt/i4h/arena/.venv/bin/python",
        "-I",
        "-B",
        str(Path(native_server.__file__).with_name("workflow.py")),
        "--spec",
        str(spec),
    ]


@pytest.mark.parametrize("runtime_python", [None, "python", "", 42])
def test_controller_rejects_missing_or_relative_runtime(tmp_path, runtime_python):
    source = tmp_path / "worker.json"
    source.write_text(
        json.dumps(
            {
                "image": "registry.example/worker@sha256:" + "a" * 64,
                "runtime_python": runtime_python,
            }
        )
    )
    with pytest.raises(ValueError, match="installed Arena interpreter"):
        native_server.load_settings(source)
