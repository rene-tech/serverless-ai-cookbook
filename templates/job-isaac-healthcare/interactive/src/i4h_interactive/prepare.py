"""Prepare an ordinary upstream workflow launch without starting Isaac or a GPU."""

import argparse
import json
from pathlib import Path

from .contract import kit_arguments, validate


def prepare(config, context, workflow_argv, output, *, python):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    # The generic project preparer owns extraction/import path verification.
    if not isinstance(context.get("project"), dict) or not context["project"].get(
        "effective_root"
    ):
        raise ValueError("a prepared project context is required")
    forbidden = ("--headless", "--python-server", "--auto-launch-cloudxr")
    if any(arg.split("=", 1)[0] in forbidden for arg in workflow_argv):
        raise ValueError(
            "this WebRTC transport cannot enable another server or a headless-only visualizer"
        )
    context = {
        **context,
        "kit_arguments": [*context.get("kit_arguments", []), *kit_arguments(config)],
    }
    context_path = output / "runtime-context.json"
    context_path.write_text(json.dumps(context, indent=2) + "\n")
    config = {
        **config,
        "startup_readiness_file": str(Path(config["work_dir"]) / "startup-ready.json"),
        "command": [
            str(Path(python).resolve()),
            "-I",
            "-B",
            "-m",
            "isaac_healthcare_runtime.launch",
            "--context",
            str(context_path),
            *workflow_argv,
        ],
    }
    validate(config)
    (output / "session.json").write_text(json.dumps(config, indent=2) + "\n")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("workflow_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = (
        args.workflow_argv[1:]
        if args.workflow_argv[:1] == ["--"]
        else args.workflow_argv
    )
    prepare(
        json.loads(args.session.read_text()),
        json.loads(args.context.read_text()),
        argv,
        args.output,
        python=args.python,
    )


if __name__ == "__main__":
    main()
