#!/usr/bin/env python3
"""Portable, job-local dispatcher for upstream i4h RL and dataset operations.

The caller extracts the project and prepares its effective SDK tree. This module
does not schedule work, install packages, download models or change that tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

OPERATIONS = ("train", "evaluate", "export", "dataset-inspect", "dataset-convert")
HERE = Path(__file__).resolve().parent


def read_json(path):
    def bad(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(Path(path).read_text(), parse_constant=bad)


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_json(path, value):
    with Path(path).open("x") as target:
        json.dump(value, target, indent=2, allow_nan=False)
        target.write("\n")


def relative_input(root, value, name, *, directory=False):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"{name} must be a nonempty path relative to the project archive")
    if ".." in Path(value).parts:
        raise ValueError(f"{name} must not traverse outside the project archive")
    current = Path(root).resolve()
    for part in Path(value).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{name} must not use a symbolic link: {value}")
    if not current.exists() or (not directory and not current.is_file()):
        raise ValueError(f"{name} does not exist as a {'file or directory' if directory else 'file'}: {value}")
    return current


def validate_options(value, filename):
    schema = read_json(HERE / filename)
    if not isinstance(value, dict):
        raise ValueError(f"{schema['title']} must be an object")
    unknown = set(value) - schema["properties"].keys()
    if unknown:
        raise ValueError(f"Unknown {schema['title']} fields: {', '.join(sorted(unknown))}")
    result = {}
    for name, definition in schema["properties"].items():
        item = value.get(name, definition.get("default"))
        types = definition.get("type", [])
        types = [types] if isinstance(types, str) else types
        actual = ("null" if item is None else "boolean" if isinstance(item, bool)
                  else "integer" if isinstance(item, int) else "number" if isinstance(item, float)
                  else "string" if isinstance(item, str) else "array" if isinstance(item, list)
                  else "object" if isinstance(item, dict) else "unknown")
        if types and actual not in types and not (actual == "integer" and "number" in types):
            raise ValueError(f"{name} must have type {types}, got {actual}")
        if "enum" in definition and item not in definition["enum"]:
            raise ValueError(f"{name} must be one of {definition['enum']}")
        if isinstance(item, str) and len(item) < definition.get("minLength", 0):
            raise ValueError(f"{name} must be nonempty")
        if actual in ("number", "integer"):
            if (actual == "number" and not math.isfinite(item)) or item < definition.get("minimum", -math.inf):
                raise ValueError(f"{name} must be finite and >= {definition.get('minimum')}")
        if actual == "array" and any(not isinstance(x, str) or not x for x in item):
            raise ValueError(f"{name} must contain nonempty strings")
        result[name] = item
    return result


def inventory(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Output contains a symbolic link: {path.relative_to(root)}")
        if path.is_file():
            result[str(path.relative_to(root))] = {"sha256": digest(path), "size_bytes": path.stat().st_size}
        elif not path.is_dir():
            raise ValueError(f"Output contains a non-regular object: {path.relative_to(root)}")
    return result


def public_validation(value):
    """Keep science metrics in summaries; complete upstream report stays retained."""
    value = json.loads(json.dumps(value, allow_nan=False))
    value.pop("agent_configuration", None)
    if isinstance(value.get("evaluation"), dict):
        for key in ("checkpoint", "patient_twin", "exported_policy", "created_at"):
            value["evaluation"].pop(key, None)
    return value


def prepare(operation, *, input_dir, sdk_root, output_dir, parameters, workflow=None,
            arena_python=None, dataset_python=None, python_paths=(), preflight=False):
    if operation not in OPERATIONS:
        raise ValueError(f"Unknown training/dataset operation: {operation}")
    input_dir, sdk_root, output_dir = (Path(v).resolve() for v in (input_dir, sdk_root, output_dir))
    if not input_dir.is_dir() or not sdk_root.is_dir():
        raise ValueError("The extracted project and effective SDK directories must exist")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    training = validate_options(parameters.get("training", {}), "training.schema.json")
    dataset = validate_options(parameters.get("dataset_options", {}), "dataset-options.schema.json")
    selected_workflow = workflow or parameters.get("workflow")
    payload = {"operation": operation, "input_dir": str(input_dir), "sdk_root": str(sdk_root),
               "output_dir": str(output_dir), "workflow": selected_workflow,
               "training": training, "dataset_options": dataset, "preflight": preflight}
    for name in ("checkpoint", "dataset", "patient_twin"):
        value = parameters.get(name)
        if value is not None:
            payload[name] = str(relative_input(input_dir, value, name, directory=name in ("checkpoint", "dataset")))
        else:
            payload[name] = None
    for name in ("resume_dir", "train_config"):
        if training[name] is not None:
            training[name] = str(relative_input(input_dir, training[name], "training." + name,
                                               directory=name == "resume_dir"))
    if operation in ("train", "evaluate", "export"):
        if not isinstance(selected_workflow, str) or not selected_workflow or Path(selected_workflow).name != selected_workflow:
            raise ValueError("Training/evaluation/export requires a resolved workflow name")
        profile = training["profile"] or f"rl/profiles/{selected_workflow}.yaml"
        if Path(profile).is_absolute() or ".." in Path(profile).parts:
            raise ValueError("training.profile must be relative to the effective SDK tree")
        profile = sdk_root / profile
        if not profile.is_file():
            raise ValueError(f"RL profile does not exist: {profile}. Supply a workflow-owned profile in overlay/rl/profiles.")
        payload["profile"] = str(profile)
        payload["profile_sha256"] = digest(profile)
        if operation in ("evaluate", "export") and not payload["checkpoint"]:
            raise ValueError(f"{operation} requires checkpoint relative to the project archive")
        executable = Path(arena_python or os.environ.get("I4H_ARENA_PYTHON", sys.executable))
    else:
        if not payload["dataset"]:
            raise ValueError(f"{operation} requires dataset relative to the project archive")
        if operation == "dataset-convert" and not dataset["robot"]:
            raise ValueError("dataset-convert requires dataset_options.robot, naming an upstream/project descriptor")
        executable = Path(dataset_python or os.environ.get("I4H_DATASET_PYTHON", "/opt/i4h/tools/dataset/.venv/bin/python"))
    if not executable.is_file():
        raise ValueError(f"Required interpreter is not installed: {executable}; build the separately locked training/dataset environment")
    payload["arena_python"] = str(Path(arena_python or sys.executable).absolute())
    payload["python_paths"] = []
    for value in python_paths:
        path = Path(value).resolve()
        if not path.is_dir():
            raise ValueError(f"Project Python source path does not exist: {path}")
        payload["python_paths"].append(str(path))
    return payload, [str(executable.absolute()), "-I", str(HERE / "bridge.py")]


def run_operation(operation, *, input_dir, sdk_root, output_dir, parameters, workflow=None,
                  arena_python=None, dataset_python=None, python_paths=(), preflight=False):
    """Return a typed summary; caller retains all output files in its normal artifact grant."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("training-request.json", "training-result.json", "training-error.json", "training-execution.log", "artifacts"):
        if (output_dir / name).exists():
            raise ValueError(f"Refusing to overwrite prior training output: {output_dir / name}")
    start = time.time()
    try:
        payload, command = prepare(operation, input_dir=input_dir, sdk_root=sdk_root, output_dir=output_dir,
                                   parameters=parameters, workflow=workflow, arena_python=arena_python,
                                   dataset_python=dataset_python, python_paths=python_paths, preflight=preflight)
        request = output_dir / "training-request.json"
        write_json(request, payload)
        command += ["--request", str(request)]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        # The job owner controls termination; upstream child processes inherit
        # its process group. No retries, detached session or second scheduler.
        with (output_dir / "training-execution.log").open("xb") as log:
            completed = subprocess.run(command, cwd=sdk_root, env=environment, stdout=log, stderr=subprocess.STDOUT)
        report = output_dir / "training-validation.json"
        if completed.returncode or not report.is_file():
            failure = output_dir / "training-engine-error.json"
            detail = read_json(failure).get("cause") if failure.is_file() else None
            if not detail:
                with (output_dir / "training-execution.log").open("rb") as log:
                    log.seek(max(0, (output_dir / "training-execution.log").stat().st_size - 8192))
                    detail = log.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Upstream {operation} failed (exit {completed.returncode}): {detail or 'missing semantic result; see training-execution.log'}")
        validation = read_json(report)
        if validation.get("status") not in ("validated", "preflight_pass"):
            raise RuntimeError("Upstream operation produced no validated semantic report")
        all_files = inventory(output_dir)
        operator_files = [name for name in all_files if name in (
            "training-request.json", "training-execution.log", "training-engine-error.json",
            "training-error.json", "training-validation.json") or
            name.endswith(".log") or (name.startswith("artifacts/") and Path(name).name == "run.json")]
        result = {"schema": "isaac-healthcare-training-result/v1", "status": "prepared" if preflight else "succeeded",
                  "operation": operation, "workflow": payload["workflow"], "engine_exit_code": completed.returncode,
                  "elapsed_seconds": time.time() - start, "validation": public_validation(validation),
                  "files": all_files, "operator_diagnostics": operator_files, "scientific_execution": not preflight}
        write_json(output_dir / "training-result.json", result)
        return result
    except Exception as error:
        failure = {"schema": "isaac-healthcare-training-error/v1", "status": "failed", "operation": operation,
                   "cause": str(error), "type": type(error).__name__, "elapsed_seconds": time.time() - start,
                   "diagnostics": "Preserve training-execution.log and any partial artifacts; no automatic retry."}
        if not (output_dir / "training-error.json").exists():
            write_json(output_dir / "training-error.json", failure)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=OPERATIONS, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--parameters-file", type=Path, required=True)
    parser.add_argument("--workflow")
    parser.add_argument("--arena-python", type=Path)
    parser.add_argument("--dataset-python", type=Path)
    parser.add_argument("--python-path", action="append", default=[])
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        result = run_operation(args.operation, input_dir=args.input_dir, sdk_root=args.sdk_root,
                               output_dir=args.output_dir, parameters=read_json(args.parameters_file),
                               workflow=args.workflow, arena_python=args.arena_python, dataset_python=args.dataset_python,
                               python_paths=args.python_path, preflight=args.prepare_only)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
