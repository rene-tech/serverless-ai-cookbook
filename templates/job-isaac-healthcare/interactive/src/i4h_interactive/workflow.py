"""Fresh process for each project's imports, policy services and interactive Kit."""

import argparse
import json
import signal
import subprocess
import sys
from pathlib import Path


def run(spec):
    # Customer Python imports only enter this isolated invocation process.
    from isaac_healthcare_runtime.contract import parameters
    from isaac_healthcare_runtime.project import prepare_project, apply_project_defaults
    from isaac_healthcare_runtime.inspection import inspect_context
    from isaac_healthcare_runtime.runtime import interactive_command

    root = Path(spec["root"])
    context = prepare_project(
        Path(spec["archive"]), root / "project-work", Path(spec["base_root"])
    )
    values = apply_project_defaults(parameters(spec["parameters"]), context)
    if values.get("training") or values.get("dataset_options"):
        raise ValueError(
            "training and dataset_options belong to the batch operation, not Arena GUI execution"
        )
    report = inspect_context(context, values)
    if report["selected"]["mode"] != "replay" and values["replay_episodes"] != [0]:
        raise ValueError(
            "replay_episodes requires the resolved replay mode; no replay selection was ignored"
        )
    output = root / "output"
    output.mkdir()
    (output / "workflow-inspection.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    child, child_joined, backends_joined, exit_code = None, False, False, 1
    manager = interactive_command(
        values,
        {"name": spec["session_id"], "seed": values["seed"]},
        output / "session",
        context=context,
        selected=report["selected"],
        kit_arguments=spec["kit_arguments"],
    )
    entered = False
    try:
        argv, env = manager.__enter__()
        entered = True
        env["LIVESTREAM"] = "2"
        # Same process group as this wrapper; policy backend groups remain owned
        # by the general runtime context and are joined before our witness.
        child = subprocess.Popen(
            argv, cwd=context["effective_root"], env=env, stdin=subprocess.DEVNULL
        )
        exit_code = child.wait()
        return exit_code
    finally:
        if child is not None:
            if child.poll() is None:
                child.send_signal(signal.SIGINT)
                try:
                    child.wait(timeout=spec["stop_grace_seconds"])
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            child_joined = child.poll() is not None
        else:
            child_joined = True
        if entered:
            manager.__exit__(None, None, None)
        backends_joined = True
        (root / "workflow-closeout.json").write_text(
            json.dumps(
                {
                    "session_id": spec["session_id"],
                    "children_joined": child_joined and backends_joined,
                    "kit_exit_code": None if child is None else child.returncode,
                    "wrapper_exit_code": exit_code,
                },
                sort_keys=True,
            )
            + "\n"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    return run(json.loads(args.spec.read_text()))


if __name__ == "__main__":
    sys.exit(main())
