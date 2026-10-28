"""Actual pinned Arena function with synthetic simulator and a real child process."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

RECIPE = Path(__file__).resolve().parents[1]


@pytest.fixture
def patched_arena(tmp_path):
    source = os.environ.get("I4H_SOURCE")
    if not source:
        pytest.skip("I4H_SOURCE must name the pinned upstream checkout")
    spec = importlib.util.spec_from_file_location("arena_outcome_patches", RECIPE / "scripts/apply_runtime_patches.py")
    patches = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patches)
    root, package = tmp_path / "sdk", tmp_path / "package"
    for name in {name for patch in patches.PATCHES for name in patch["files"]}:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(source) / name, target)
    shutil.copytree(RECIPE / "patches", package / "patches")
    patches.apply(root, package)
    return root / "arena/i4h_arena/app.py"


@pytest.mark.parametrize("mode", ["constructor-failure", "setup-failure", "body-failure", "diagnostic-failure", "normal"])
def test_installed_shutdown_hook_cannot_mask_failed_initialization(patched_arena, tmp_path, mode):
    output = tmp_path / "events.json"
    child = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).with_name("arena_outcome_probe.py")),
                            str(patched_arena), mode, str(output)], capture_output=True, timeout=10)
    assert child.returncode == (0 if mode == "normal" else 1), child.stderr
    events = json.loads(output.read_bytes())
    expected = {"normal": ["prepare", "construct", "yield", "close", "complete"],
                "setup-failure": ["prepare"], "constructor-failure": ["prepare", "construct"],
                "diagnostic-failure": ["prepare", "construct"], "body-failure": ["prepare", "construct", "yield"]}
    assert [event["event"] for event in events] == expected[mode]
    if mode == "normal":
        assert events[1]["arguments"] == {"kit_args": "user-setting", "headless": False, "device": "cuda:0",
            "num_envs": 3, "enable_cameras": True, "xr": False, "visualizer": ["kit"], "visualizer_explicit": True}
