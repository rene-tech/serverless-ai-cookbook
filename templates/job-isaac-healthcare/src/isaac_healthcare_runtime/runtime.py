"""Run the real, pinned i4h controller in isolated subprocesses and retain its evidence."""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

from .contract import ASSET_GENERATION, MODEL_ID, SOURCE, digest, parameters, scenarios
from .validate import validate_recording

ROOT = Path("/opt/i4h")
PYTHON = ROOT / "arena/.venv/bin/python"
ASSET_MANIFEST = Path("/opt/i4h-assets/v0.9.0-7cf86a1/manifest.json")
PATCH_MANIFEST = Path("/opt/isaac-healthcare/upstream-patches.json")


def command(values, scenario, directory):
    argv = [
        str(PYTHON),
        "-I",
        "-m",
        "isaac_healthcare_runtime.launch",
        "--workflow",
        values["workflow"],
        "--mode",
        "rule-based",
        "--headless",
        "--no-sensor-view",
        "--envs",
        "1",
        "--episodes",
        str(values["episodes"]),
        "--attempts",
        str(values["attempts"]),
        "--record",
        str(directory / "demos.hdf5"),
        "--record-failures",
    ]
    for key, flag in (("episode_steps", "--episode-steps"), ("physics", "--presets")):
        if values[key] is not None:
            argv.extend([flag, str(values[key])])
    if scenario["seed"] is not None:
        argv.extend(["--seed", str(scenario["seed"])])
    if not values["cameras"]:
        argv.append("--no-cameras")
    return argv


def execute(argv, directory):
    env = dict(os.environ)
    for name, relative in {
        "HOME": "home",
        "XDG_CACHE_HOME": "cache",
        "CUDA_CACHE_PATH": "cuda",
        "TMPDIR": "tmp",
        "I4H_PID_DIR": "pids",
        "ISAAC_HEALTHCARE_KIT_ROOT": "kit",
    }.items():
        path = directory / ".runtime" / relative
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env.update(
        {"PYTHONDONTWRITEBYTECODE": "1", "I4H_WORKFLOWS": str(ROOT), "UV_OFFLINE": "1"}
    )
    operator = directory.parent.parent / ".operator"
    operator.mkdir(exist_ok=True)
    raw_log = operator / (directory.name + ".log")
    with raw_log.open("x", encoding="utf-8") as log:
        process = subprocess.Popen(
            argv,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        previous = {}

        def stop(signum, frame):
            if process.poll() is None:
                os.killpg(process.pid, signum)

        try:
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous[signum] = signal.signal(signum, stop)
            # The native worker captures stdout in its access-controlled operator log.
            # Raw renderer/device diagnostics never enter the public scientific archive.
            for line in process.stdout:
                log.write(line)
                log.flush()
                sys.stdout.write(line)
                sys.stdout.flush()
            return process.wait(), raw_log
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=60)


def run(input_path, parameter_values, output):
    values = parameters(parameter_values)
    cases = scenarios(json.loads(input_path.read_bytes()))
    if (
        os.environ.get("ACCEPT_EULA") != "Y"
        and os.environ.get("ISAACSIM_ACCEPT_EULA") != "Y"
    ):
        raise ValueError(
            "Set ACCEPT_EULA=Y only after accepting the NVIDIA Isaac Sim license"
        )
    output.mkdir(parents=True, exist_ok=True)
    root = output / "simulation"
    root.mkdir(exist_ok=False)
    (root / "request.json").write_text(
        json.dumps({"parameters": values, "scenarios": cases}, indent=2) + "\n"
    )
    shutil.copyfile(ASSET_MANIFEST, root / "assets.json")
    shutil.copyfile(PATCH_MANIFEST, root / "upstream-patches.json")
    start = time.monotonic()
    reports = []
    for index, case in enumerate(cases):
        directory = root / f"scenario-{index:06d}"
        directory.mkdir()
        argv = command(values, case, directory)
        (directory / "execution.json").write_text(
            json.dumps({"scenario": case, "argv": argv}, indent=2) + "\n"
        )
        started = time.monotonic()
        returncode, raw_log = execute(argv, directory)
        recording = directory / "demos.hdf5"
        if not recording.exists() or returncode not in (0, 1):
            raise RuntimeError(
                f"Isaac simulation scenario {index} failed during startup or execution "
                f"(exit {returncode}); full diagnostics are in the operator logs. "
                "Check runtime and asset availability before retrying"
            )
        checked = validate_recording(recording, values, directory / "previews")
        summary_pattern = (
            re.escape(values["workflow"]) + r" \[rule-based\] run=\S+: "
            r"(\d+)/(\d+) episodes succeeded \((\d+) attempts\); "
            r"(\d+) new demonstrations saved"
        )
        summaries = re.findall(summary_pattern, raw_log.read_text(errors="replace"))
        if not summaries or tuple(map(int, summaries[-1])) != (
            checked["successful_episodes"],
            values["episodes"],
            len(checked["episodes"]),
            len(checked["episodes"]),
        ):
            raise RuntimeError(
                "Simulator did not publish a normal terminal run summary matching its recording; "
                "inspect the operator log for the failing execution step"
            )
        if checked["task_complete"] != (returncode == 0):
            raise RuntimeError(
                "Simulator exit status differs from recorded task completion"
            )
        (directory / "workflow.log").write_text(
            "Workflow outcome log from upstream HDF5 metadata and terminal summary.\n"
            + json.dumps(
                {
                    "workflow": values["workflow"],
                    "scenario": case,
                    "physics": values["physics"] or "physx",
                    "control_hz": 60.0,
                    "episode_step_cap": values["episode_steps"] or 600,
                    "requested_episodes": values["episodes"],
                    "task_complete": checked["task_complete"],
                    "episodes": checked["episodes"],
                },
                indent=2,
            )
            + "\n"
        )
        reports.append(
            {
                "scenario": case,
                "recording": f"scenario-{index:06d}/demos.hdf5",
                "simulation_seconds": time.monotonic() - started,
                **checked,
            }
        )
        # Only invocation-owned simulator caches are removed; scientific logs/recordings remain.
        shutil.rmtree(directory / ".runtime")
    elapsed = time.monotonic() - start
    archive_path = output / "simulation.tar"
    with tarfile.open(archive_path, "w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise RuntimeError("Simulator output contains an unexpected symlink")
            if path.is_file():
                archive.add(
                    path, arcname=path.relative_to(root).as_posix(), recursive=False
                )
    samples = sum(row["samples"] for row in reports)
    report = {
        "schema": "isaac-healthcare-result/v1",
        "model_id": MODEL_ID,
        "operation": "simulate",
        "input_sha256": digest(input_path),
        "parameters": values,
        "source_revision": SOURCE,
        "asset_generation": ASSET_GENERATION,
        "materialized_assets_sha256": digest(ASSET_MANIFEST),
        "upstream_patches_sha256": digest(PATCH_MANIFEST),
        "isaac_sim": "6.0.1",
        "scenarios": reports,
        "task_complete": all(row["task_complete"] for row in reports),
        "scientific_validation": "passed",
        "physics": values["physics"] or "physx",
        "control_hz": 60.0,
        "scene_step_cap": 600,
        "recording_semantics": "Upstream v1 omits the termination/reset sample; task success is the upstream predicate, not a final-frame guess.",
        "files": {
            "simulation.tar": {
                "sha256": digest(archive_path),
                "size_bytes": archive_path.stat().st_size,
            }
        },
        "runtime_metrics": {
            "simulation_seconds": elapsed,
            "samples_completed": samples,
            "samples_per_second": samples / elapsed if elapsed else None,
        },
    }
    (output / "result.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Scenario JSON")
    parser.add_argument("--parameters-json", default="{}")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(
            args.input, json.loads(args.parameters_json), args.output_dir.resolve()
        )
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"Isaac healthcare simulation failed: {error}\n")
    print(
        json.dumps(
            {
                "result": str(args.output_dir / "result.json"),
                "task_complete": result["task_complete"],
            }
        )
    )


if __name__ == "__main__":
    main()
