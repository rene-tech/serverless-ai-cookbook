#!/usr/bin/env python3
"""Invoke pinned upstream APIs in their owning interpreter and inspect outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback
from types import FunctionType


def explicit_interpreter(value, field):
    """Honor an explicit installed interpreter without upstream fallback.

    Keep the virtualenv's lexical executable path: resolving its symlink to the
    base Python would select a different environment. None retains the owning
    upstream launcher's defaults; no package installation or probing occurs.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must name an installed executable interpreter")
    path = Path(value).expanduser().absolute()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(
            f"{field} interpreter is missing or not executable: {path}; "
            "the explicit selection will not fall back to another environment"
        )
    return str(path)


def _scoped_function(function, **replacements):
    """Use the upstream function unchanged, with invocation-local collaborators."""
    scoped = FunctionType(function.__code__, {**function.__globals__, **replacements},
                          function.__name__, function.__defaults__, function.__closure__)
    scoped.__kwdefaults__ = function.__kwdefaults__
    return scoped


class PortableRslProcesses:
    """Only this backend call site receives a bootstrap; subprocess is untouched."""

    def __init__(self, original, request):
        self.original, self.request, self.count = original, request, 0

    def __getattr__(self, name):
        return getattr(self.original, name)

    def call(self, command, **kwargs):
        if (not isinstance(command, (list, tuple)) or len(command) < 2
                or any(not isinstance(value, str) or not value for value in command)
                or kwargs.get("shell")):
            raise ValueError("Portable RSL requires the upstream explicit Python argv without a shell")
        self.count += 1
        output = Path(self.request["output_dir"])
        context_path = output / f"training-child-context-{self.count:04d}.json"
        receipt = output / f"training-child-startup-{self.count:04d}.jsonl"
        environment = kwargs.get("env", os.environ)
        kit_root = environment.get("ISAAC_HEALTHCARE_KIT_ROOT")
        if not kit_root or not Path(kit_root).is_absolute():
            raise ValueError("Portable RSL launch is missing its absolute private Kit directory")
        root = Path(self.request["sdk_root"])
        paths = [Path(value) for value in self.request["python_paths"]]
        paths += [root / name for name in ("rl", "tools/dataset", "common", "arena", "engine", "workflows")]
        context = {
            "project": {"effective_root": str(root), "project_dir": self.request["input_dir"],
                        "python_paths": list(dict.fromkeys(str(path) for path in paths if path.is_dir())),
                        "asset_root": environment.get("I4H_ASSET_PATH")},
            "kit_root": kit_root, "receipt": str(receipt), "upstream_argv": list(command),
        }
        write(context_path, context)
        actual = [command[0], "-I", str(Path(__file__).with_name("child_bootstrap.py")),
                  "--context", str(context_path), "--", *command[1:]]
        print("portable RSL child: " + json.dumps(actual), flush=True)
        return self.original.call(actual, **kwargs)


def portable_rl_call(function, backend, request, *args):
    """Keep CLI validation and scientific launch functions; adapt only RSL children."""
    processes = PortableRslProcesses(backend.subprocess, request)

    class InvocationBackend:
        def __getattr__(self, name):
            value = getattr(backend, name)
            return _scoped_function(value, subprocess=processes) if name in ("launch", "export") else value

    original_load = function.__globals__["load_backend"]

    def load(name):
        return InvocationBackend() if name == "rsl_rl" else original_load(name)

    return _scoped_function(function, load_backend=load)(*args)


def read(path):
    def invalid(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(Path(path).read_text(), parse_constant=invalid)


def write(path, value):
    with Path(path).open("x") as target:
        json.dump(value, target, indent=2, allow_nan=False)
        target.write("\n")


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def nonempty(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty required artifact: {path}")
    return path


def tensor_inventory(state):
    import torch
    tensors = []
    def visit(value):
        if isinstance(value, torch.Tensor):
            if value.is_floating_point() or value.is_complex():
                if not bool(torch.isfinite(value).all()):
                    raise ValueError("Checkpoint contains non-finite model weights")
            tensors.append({"shape": list(value.shape), "dtype": str(value.dtype), "elements": value.numel()})
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
    visit(state)
    if not tensors or not sum(item["elements"] for item in tensors):
        raise ValueError("Checkpoint contains no nonempty model tensors")
    return {"tensor_count": len(tensors), "parameter_elements": sum(item["elements"] for item in tensors),
            "all_weights_finite": True}


def validate_checkpoint(path, *, rsl=True):
    import torch
    checkpoint = torch.load(nonempty(path), map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("Trainer checkpoint must contain a mapping")
    # RSL-RL5 serializes actor and critic separately; older native checkpoints
    # use model_state_dict. Inspect the actual serialization, never a filename.
    if rsl and "actor_state_dict" in checkpoint:
        if not isinstance(checkpoint["actor_state_dict"], dict) or not checkpoint["actor_state_dict"]:
            raise ValueError("RSL-RL checkpoint has an empty actor_state_dict")
        if not isinstance(checkpoint.get("critic_state_dict"), dict) or not checkpoint["critic_state_dict"]:
            raise ValueError("RSL-RL checkpoint is missing critic_state_dict")
        state = {"actor": checkpoint["actor_state_dict"], "critic": checkpoint["critic_state_dict"]}
    else:
        state = checkpoint.get("model_state_dict") if rsl else checkpoint
    if not isinstance(state, dict) or not state:
        raise ValueError("RSL-RL checkpoint is missing actor/critic or model state dictionaries")
    result = tensor_inventory(state)
    if rsl:
        iteration = checkpoint.get("iter")
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 0:
            raise ValueError("RSL-RL checkpoint has no nonnegative training iteration")
        result["iteration"] = iteration
        result["optimizer_state_present"] = isinstance(checkpoint.get("optimizer_state_dict"), dict)
    return result


def validate_evaluation(path, *, expected_task=None, expected_episodes=None, backend="rsl_rl"):
    value = read(nonempty(path))
    if backend == "rlinf":
        metrics = value.get("metrics", {})
        required = {"eval/return", "eval/success_once", "eval/episode_len", "eval/num_trajectories"}
        if not required <= metrics.keys() or not all(isinstance(metrics[k], (int, float)) and
                                                     not isinstance(metrics[k], bool) and math.isfinite(metrics[k]) for k in required):
            raise ValueError("RLinf evaluation lacks finite upstream trajectory metrics")
        if metrics["eval/num_trajectories"] <= 0:
            raise ValueError("RLinf evaluation contains no trajectories")
        return {"metrics": metrics, "task_success": metrics["eval/success_once"] > 0}
    episodes = value.get("episodes")
    rows = value.get("results")
    if isinstance(episodes, bool) or not isinstance(episodes, int) or episodes < 1 or not isinstance(rows, list) or len(rows) != episodes:
        raise ValueError("Evaluation episode count and result rows disagree")
    if expected_task is not None and value.get("task") != expected_task:
        raise ValueError("Evaluation task differs from the selected profile")
    if expected_episodes is not None and episodes != expected_episodes:
        raise ValueError("Evaluation did not complete the requested episode count")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("success"), bool):
            raise ValueError("Evaluation rows must preserve explicit task success booleans")
        if isinstance(row.get("steps"), bool) or not isinstance(row.get("steps"), int) or row["steps"] < 1:
            raise ValueError("Evaluation episode has no positive step count")
        for key, number in row.items():
            if key not in ("success", "steps") and (isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number)):
                raise ValueError(f"Evaluation metric {key} must be finite")
    successes = sum(row["success"] for row in rows)
    rate = value.get("success_rate")
    if isinstance(value.get("successes"), bool) or not isinstance(value.get("successes"), int) or \
            isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or \
            value["successes"] != successes or not math.isclose(rate, successes / episodes, abs_tol=1e-12):
        raise ValueError("Evaluation success aggregates disagree with episode outcomes")
    return value


def rl(request):
    settings = request["training"]
    runtime_python = explicit_interpreter(settings["runtime_python"], "training.runtime_python")
    sim_runtime_python = explicit_interpreter(settings["sim_runtime_python"], "training.sim_runtime_python")
    from i4h_rl import cli
    from i4h_rl.backend_loader import load_backend
    from i4h_rl.contract import validate_workflow_contract
    from i4h_rl.profile import RLProfile
    import yaml

    root, output = Path(request["sdk_root"]), Path(request["output_dir"])
    settings, operation = request["training"], request["operation"]
    profile_path = Path(request["profile"])
    if sha(profile_path) != request["profile_sha256"]:
        raise ValueError("RL profile changed after request preparation")
    profile = RLProfile.load(profile_path)
    if profile.workflow != request["workflow"]:
        raise ValueError("Selected workflow and authored RL profile disagree")
    validate_workflow_contract(profile, root)
    backend = load_backend(profile.trainer)
    backend.validate_profile(profile, root)
    args = cli._parser().parse_args([profile.workflow])
    args.only_eval = operation == "evaluate"
    args.num_envs, args.epochs, args.episodes = settings["num_envs"], settings["epochs"], settings["episodes"]
    args.video, args.overrides = settings["video"], settings["overrides"]
    args.resume_dir, args.train_config = settings["resume_dir"], settings["train_config"]
    args.runtime_python = runtime_python or (request["arena_python"] if profile.trainer == "rsl_rl" else None)
    args.sim_runtime_python = sim_runtime_python
    args.patient_twin = request["patient_twin"]
    if operation == "train":
        # Upstream RSL-RL correctly rejects a starting checkpoint; RLinf's
        # starting policy is --model-path, while evaluate/export use --checkpoint.
        args.model_path = request["checkpoint"]
    else:
        args.rl_model_path = request["checkpoint"]
    artifacts = output / "artifacts"
    artifacts.mkdir(exist_ok=False)
    work = artifacts / ("export" if operation == "export" else "run")
    if operation == "export":
        args.output_dir = str(work)
    else:
        args.run_dir = str(work)
    report = {"status": "preflight_pass" if request["preflight"] else "validated",
              "engine": "i4h_rl", "backend": profile.trainer, "workflow": profile.workflow,
              "profile_sha256": sha(profile_path), "trainer_config_sha256": sha(profile.trainer_config),
              "profile_defaults": {"num_envs": profile.default_num_envs, "epochs": profile.default_epochs}}
    if request["preflight"]:
        if operation == "export":
            if profile.trainer == "rsl_rl":
                args.resolved_patient_twin = cli._resolve_patient_twin(args, profile, root)
                if args.train_config:
                    raise ValueError("--train-config is only valid when exporting an RLinf checkpoint")
            used = [name for name in ("resume_dir", "video", "overrides", "num_envs", "epochs", "episodes", "sim_runtime_python") if getattr(args, name)]
            if used:
                raise ValueError("export does not accept " + ", ".join(used))
            report["checkpoint_sha256"] = sha(args.rl_model_path) if Path(args.rl_model_path).is_file() else None
        else:
            args.dry_run = True
            cli._launch(args, profile, root)
        report["scientific_execution"] = False
        return report
    launch = cli._export if operation == "export" else cli._launch
    code = (portable_rl_call(launch, backend, request, args, profile, root)
            if profile.trainer == "rsl_rl" else launch(args, profile, root))
    if code:
        raise RuntimeError(f"Upstream {profile.trainer} {operation} returned exit {code}; preserve the full execution log")
    if profile.trainer == "rsl_rl":
        if operation == "train":
            report["checkpoint"] = validate_checkpoint(work / "model_final.pt")
            config = yaml.safe_load(nonempty(work / "agent.yaml").read_text())
            if not isinstance(config, dict) or not config:
                raise ValueError("Training produced no usable agent configuration")
            meta = read(nonempty(work / "run.json"))
            if meta.get("workflow") != profile.workflow or meta.get("trainer") != profile.trainer:
                raise ValueError("Training metadata differs from the selected workflow/backend")
            report["agent_configuration"] = config
            report["quality_scope"] = "A structurally valid learned checkpoint; policy quality requires evaluation."
        else:
            report["evaluation"] = validate_evaluation(work / "evaluation.json", expected_task=profile.eval_task_id,
                                                       expected_episodes=1 if operation == "export" else (args.episodes or 20))
            if operation == "export":
                import torch
                policy = torch.jit.load(str(nonempty(work / "policy.pt")), map_location="cpu")
                report["policy"] = tensor_inventory(policy.state_dict())
                manifest = read(nonempty(work / "policy.json"))
                if manifest.get("workflow") != profile.workflow or manifest.get("trainer") != profile.trainer:
                    raise ValueError("Exported policy manifest differs from the selected workflow")
    elif operation == "train":
        manifest = backend.checkpoint_bundle(work, expected_workflow=profile.workflow)
        if not manifest:
            raise ValueError("RLinf training produced no checkpoint.json bundle")
        weights = (work / manifest["weights"]).resolve()
        if not weights.is_relative_to(work.resolve()):
            raise ValueError("RLinf output weight path escapes its run bundle")
        report["checkpoint"] = validate_checkpoint(weights, rsl=False)
        report["quality_scope"] = "Finite checkpoint tensors; external RLinf task-quality qualification remains separate."
    elif operation == "evaluate":
        report["evaluation"] = validate_evaluation(work / "evaluation.json", backend="rlinf")
    else:
        from safetensors import safe_open
        index = read(nonempty(work / "model.safetensors.index.json"))
        weights = index.get("weight_map")
        if not isinstance(weights, dict) or not weights:
            raise ValueError("Exported model has no safetensors weight map")
        total = 0
        for filename in set(weights.values()):
            path = (work / filename).resolve()
            if not path.is_relative_to(work.resolve()):
                raise ValueError("Exported safetensors index escapes its artifact directory")
            with safe_open(str(nonempty(path)), framework="pt", device="cpu") as handle:
                keys = list(handle.keys())
                if {key for key, owner in weights.items() if owner == filename} != set(keys):
                    raise ValueError("Safetensors index disagrees with exported shard keys")
                for key in keys:
                    total += tensor_inventory({key: handle.get_tensor(key)})["parameter_elements"]
        read(nonempty(work / "config.json"))
        read(nonempty(work / "policy.json"))
        report["policy"] = {"parameter_elements": total, "all_weights_finite": True, "format": "safetensors"}
    return report


def recordings(path):
    import h5py
    path = Path(path)
    if path.is_file():
        return [path]
    result = []
    for candidate in sorted(path.rglob("*")):
        if candidate.is_symlink():
            raise ValueError(f"Dataset input uses a symbolic link: {candidate}")
        if candidate.is_file() and h5py.is_hdf5(candidate):
            result.append(candidate)
    if not result:
        raise ValueError(f"No HDF5 recordings found by file signature under {path}")
    return result


def inspect_recording(path):
    import h5py
    import numpy as np
    from i4h_common.episode import Episode, demo_names
    demos = []
    with h5py.File(path, "r") as handle:
        for name in demo_names(handle):
            episode = Episode(name, handle["data"][name])
            episode.validate()
            actions, states = episode.actions, episode.states
            if actions.ndim != 2 or actions.shape[0] != episode.num_samples:
                raise ValueError(f"{path}:{name}: action shape and declared frame count disagree")
            if not np.isfinite(actions).all() or (states is not None and not np.isfinite(states).all()):
                raise ValueError(f"{path}:{name}: state/action tensors contain NaN or infinity")
            cameras = {}
            for camera in episode.cameras:
                value = handle["data"][name][f"obs/{camera}"]
                if value.shape[0] != episode.num_samples or value.shape[-1] != 3:
                    raise ValueError(f"{path}:{name}: camera frame shape disagrees with actions")
                cameras[camera] = list(value.shape)
            demos.append({"name": name, "samples": episode.num_samples, "success": episode.success,
                          "recording_version": episode.recording_version, "action_shape": list(actions.shape),
                          "state_shape": None if states is None else list(states.shape), "cameras": cameras,
                          "segments": [{"node": v.node, "task_id": v.task_id, "start": v.start, "end": v.end} for v in episode.segments]})
    if not demos:
        raise ValueError(f"{path}: recording contains no episodes")
    return {"sha256": sha(path), "size_bytes": path.stat().st_size, "episodes": demos}


def validate_lerobot(root, *, expected_lengths, fps):
    import av
    import numpy as np
    import pyarrow.parquet as pq
    info = read(nonempty(root / "meta/info.json"))
    stats = read(nonempty(root / "meta/stats.json"))
    expected_episodes, expected_frames = len(expected_lengths), sum(expected_lengths)
    if info.get("total_episodes") != expected_episodes or info.get("total_frames") != expected_frames or info.get("fps") != fps:
        raise ValueError("LeRobot metadata totals/fps disagree with the selected input episodes")
    if not isinstance(stats, dict) or not stats:
        raise ValueError("Converted dataset has no normalization statistics")
    parquet_files = sorted(root.rglob("*.parquet"))
    if not parquet_files:
        raise ValueError("Converted dataset has no Parquet data")
    rows = 0
    observed_episodes = set()
    frame_counts = [0] * expected_episodes
    for path in parquet_files:
        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
            values = batch.to_pydict()
            for key in ("action", "observation.state", "timestamp", "episode_index", "frame_index"):
                if key not in values:
                    raise ValueError(f"Converted Parquet is missing {key}")
            for key in ("action", "observation.state", "timestamp"):
                if not np.isfinite(np.asarray(values[key], dtype=np.float64)).all():
                    raise ValueError(f"Converted {key} contains NaN or infinity")
            rows += batch.num_rows
            observed_episodes.update(values["episode_index"])
            for episode, frame, timestamp in zip(values["episode_index"], values["frame_index"], values["timestamp"], strict=True):
                if not isinstance(episode, int) or not 0 <= episode < expected_episodes:
                    raise ValueError("Converted frame has an invalid episode index")
                if frame != frame_counts[episode] or not math.isclose(timestamp, frame / fps, rel_tol=1e-5, abs_tol=1e-5):
                    raise ValueError("Converted frame indices/timestamps do not preserve the requested sample order/fps")
                frame_counts[episode] += 1
    if rows != expected_frames or observed_episodes != set(range(expected_episodes)) or frame_counts != expected_lengths:
        raise ValueError("Actual converted frame/episode rows disagree with metadata")
    videos = []
    for path in sorted((root / "videos").rglob("*")) if (root / "videos").exists() else []:
        if not path.is_file():
            continue
        count = 0
        width, height, rate = None, None, None
        with av.open(str(path)) as container:
            rate = float(container.streams.video[0].average_rate)
            for frame in container.decode(video=0):
                if frame.width < 1 or frame.height < 1:
                    raise ValueError(f"Invalid converted video dimensions: {path}")
                count += 1
                width, height = frame.width, frame.height
        if count == 0:
            raise ValueError(f"Converted video contains no decodable frames: {path}")
        videos.append({"path": str(path.relative_to(root)), "frames": count, "width": width, "height": height, "fps": rate})
    video_features = [name for name, feature in info.get("features", {}).items() if feature.get("dtype") == "video"]
    if video_features and (len(videos) != expected_episodes * len(video_features) or sum(x["frames"] for x in videos) != expected_frames * len(video_features)):
        raise ValueError("Decoded converted video counts disagree with episode/frame metadata")
    video_inventory = {item["path"]: item for item in videos}
    for episode, expected_length in enumerate(expected_lengths):
        for key in video_features:
            filename = info["video_path"].format(episode_chunk=episode // info["chunks_size"], episode_index=episode, video_key=key)
            video = video_inventory.get(filename)
            shape = info["features"][key]["shape"]
            if not video or video["frames"] != expected_length or video["height"] != shape[0] or video["width"] != shape[1] or not math.isclose(video["fps"], fps):
                raise ValueError("Decoded episode video disagrees with its declared frame count, dimensions or fps")
    return {"episodes": expected_episodes, "frames": rows, "fps": fps, "normalization_statistics_present": True,
            "finite_numeric_columns": True, "decoded_videos": videos, "features": info.get("features", {})}


def dataset(request):
    import numpy as np
    if sys.version_info[:2] != (3, 11) or int(np.__version__.split(".")[0]) >= 2:
        raise RuntimeError("Dataset operations require their isolated Python3.11/NumPy<2 environment; do not use Arena's interpreter")
    from i4h_tools.dataset import cli
    output = Path(request["output_dir"])
    sources = recordings(request["dataset"])
    options = request["dataset_options"]
    report = {"status": "preflight_pass" if request["preflight"] else "validated", "engine": "i4h_tools.dataset",
              "recordings": [{"path": str(path.relative_to(Path(request["input_dir"]))), **inspect_recording(path)} for path in sources]}
    if request["operation"] == "dataset-inspect":
        for path in sources:
            cli.inspect(path, show_segments=options["segments"])
            if options["actions"]:
                cli.actions(path, threshold=options["action_threshold"])
        return report
    from i4h_common.config import get_robot_config
    config = get_robot_config(options["robot"])
    report["robot"] = config.name
    selected = [demo for recording in report["recordings"] for demo in recording["episodes"]
                if not options["successful_only"] or demo["success"]]
    if not selected or any(demo["samples"] <= options["skip_frames"] for demo in selected):
        raise ValueError("Dataset filtering/skip_frames leaves no frames in one or more selected episodes")
    expected_frames = sum(demo["samples"] - options["skip_frames"] for demo in selected)
    if request["preflight"]:
        report.update({"selected_episodes": len(selected), "selected_frames": expected_frames, "scientific_execution": False})
        return report
    artifacts = output / "artifacts"
    artifacts.mkdir(exist_ok=False)
    target = artifacts / "dataset"
    written = cli.convert(sources, target, robot=options["robot"], repo_id=options["repo_id"],
                          fps=options["fps"], video_codec=options["video_codec"], skip_frames=options["skip_frames"],
                          successful_only=options["successful_only"], task=options["task"],
                          g1_wbc_policy_actions=options["g1_wbc_policy_actions"],
                          patient_twin=Path(request["patient_twin"]) if request["patient_twin"] else None)
    if written != len(selected):
        raise ValueError("Upstream converter reported a different episode count")
    report["converted_dataset"] = validate_lerobot(target, expected_lengths=[demo["samples"] - options["skip_frames"] for demo in selected], fps=options["fps"])
    return report


def execute(request):
    root = Path(request["sdk_root"])
    roots = [Path(value) for value in request["python_paths"]]
    roots += [root / name for name in ("rl", "tools/dataset", "common", "arena", "engine", "workflows")]
    sys.path[:0] = [str(path) for path in roots if path.is_dir()]
    os.environ["I4H_WORKFLOWS"] = str(root)
    os.environ["PYTHONPATH"] = os.pathsep.join(str(path) for path in roots if path.is_dir())
    os.environ.setdefault("HEADLESS", "1")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if request["operation"] in ("train", "evaluate", "export"):
        return rl(request)
    return dataset(request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = read(args.request)
    output = Path(request["output_dir"])
    try:
        report = execute(request)
        write(output / "training-validation.json", report)
        return 0
    except BaseException as error:
        traceback.print_exc()
        write(output / "training-engine-error.json", {"cause": str(error), "type": type(error).__name__})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
