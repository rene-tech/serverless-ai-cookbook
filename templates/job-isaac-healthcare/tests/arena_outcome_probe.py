"""Synthetic simulator constructor; run only as a disposable CPU subprocess."""
import argparse
import atexit
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

source, mode, output = sys.argv[1:]
output = Path(output)
events = []


def retain(event, **fields):
    events.append({"event": event, **fields})
    output.write_text(json.dumps(events, sort_keys=True) + "\n")


def mask_failure():
    atexit.register(lambda: os._exit(0))


def prepare(device):
    retain("prepare", device=device)
    if mode == "setup-failure":
        mask_failure()
        raise RuntimeError("synthetic side-effectful setup failure")


class Application:
    def close(self):
        retain("close")


class BrokenFlush:
    def write(self, value):
        return len(value)

    def flush(self):
        raise OSError("synthetic diagnostic stream failure")


class AppLauncher:
    @staticmethod
    def add_app_launcher_args(parser):
        parser.add_argument("--kit-args", default="user-setting")

    def __init__(self, args):
        retain("construct", arguments=vars(args))
        mask_failure()
        if mode == "diagnostic-failure":
            sys.stdout = BrokenFlush()
        if mode in ("constructor-failure", "diagnostic-failure"):
            raise RuntimeError("synthetic constructor failed after installing shutdown hook")
        self.app = Application()


for name in ("i4h_arena", "i4h_arena.medical", "i4h_arena.medical.slang_cuda", "isaaclab", "isaaclab.app"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["i4h_arena.medical.slang_cuda"].prepare_slang_for_kit = prepare
sys.modules["isaaclab.app"].AppLauncher = AppLauncher
spec = importlib.util.spec_from_file_location("exact_arena_subject", source)
subject = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = subject
spec.loader.exec_module(subject)
args = argparse.Namespace(headless=False, device="cuda:0", num_envs=3,
                          no_cameras=False, enable_cameras=True, xr=False,
                          python_server=False, usd_thread_limit=None)
with subject.launch_app(args) as context:
    assert context.args is args and isinstance(context.app, Application)
    retain("yield")
    if mode == "body-failure":
        raise RuntimeError("synthetic workflow failure")
retain("complete")
