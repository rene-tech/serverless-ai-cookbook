"""Initialize portable assets and private Kit state in an RSL child process.

The upstream trainer/evaluator still owns its parser, configuration and simulator.
This process-local AppLauncher hook adds only the supported portable-root option
after the upstream parser has consumed the original scientific arguments.
"""

from __future__ import annotations

import argparse
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys


def portable_arguments(arguments, root):
    """Preserve all non-owned Kit arguments; reject a conflicting state root."""
    root = str(Path(root).absolute())
    output = []
    index = 0
    while index < len(arguments):
        value = arguments[index]
        if value == "--portable-root":
            if index + 1 == len(arguments) or arguments[index + 1].startswith("--"):
                raise ValueError("--portable-root requires its private directory")
            supplied = arguments[index + 1]
            index += 2
        elif value.startswith("--portable-root="):
            supplied = value.partition("=")[2]
            index += 1
        else:
            output.append(value)
            index += 1
            continue
        if not supplied or str(Path(supplied).absolute()) != root:
            raise ValueError("Explicit Kit --portable-root conflicts with the invocation's private Kit directory")
    return [*output, "--portable-root", root]


def _record(path, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def install_kit_root(launcher, root, receipt):
    original = launcher._create_app

    @wraps(original)
    def create_app(self):
        before = list(sys.argv)
        sys.argv = portable_arguments(before, root)
        _record(receipt, {"phase": "kit_startup", "original_argv": before,
                          "kit_argv": list(sys.argv), "portable_root": str(root)})
        return original(self)

    create_app._i4h_portable_root = str(root)
    launcher._create_app = create_app


def prepare(context):
    from isaac_healthcare_runtime.bootstrap import prepare_imports
    from isaac_healthcare_runtime.launch import localize_constants

    project = context["project"]
    prepare_imports(project)
    from i4h_arena.assets import constants

    before = {name: value for name, value in vars(constants).items() if isinstance(value, str)}
    localize_constants(constants, explicit_root=project.get("asset_root"))
    root = Path(context["kit_root"])
    if not root.is_absolute():
        raise ValueError("Private Kit directory must be absolute")
    root.mkdir(parents=True, exist_ok=True)
    os.environ["ISAAC_HEALTHCARE_KIT_ROOT"] = str(root)
    from isaaclab.app import AppLauncher

    install_kit_root(AppLauncher, root, context["receipt"])
    source = Path(AppLauncher._create_app.__wrapped__.__code__.co_filename)
    _record(context["receipt"], {
        "phase": "bootstrap_prepared", "portable_root": str(root),
        "effective_sdk": project["effective_root"],
        "app_launcher_source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "localized_constants": {name: {"source": value, "local": getattr(constants, name)}
                                for name, value in before.items() if value != getattr(constants, name)},
    })


def execute(context, arguments):
    if not arguments:
        raise ValueError("Upstream RSL child command is empty")
    if arguments[0] == "-m":
        if len(arguments) < 2 or not arguments[1] or arguments[1].startswith("-"):
            raise ValueError("Upstream RSL module name is missing")
        module, tail = arguments[1], arguments[2:]
        prepare(context)
        sys.argv = [module, *tail]
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    else:
        if arguments[0].startswith("-"):
            raise ValueError("Unsupported upstream RSL child interpreter arguments")
        script, tail = Path(arguments[0]), arguments[1:]
        if not script.is_file():
            raise ValueError(f"Upstream RSL script does not exist: {script}")
        prepare(context)
        # Match normal Python script invocation, including local helper imports.
        sys.path.insert(0, str(script.absolute().parent))
        sys.argv = [str(script), *tail]
        runpy.run_path(str(script), run_name="__main__")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    execute(json.loads(args.context.read_bytes()), arguments)


if __name__ == "__main__":
    main()
