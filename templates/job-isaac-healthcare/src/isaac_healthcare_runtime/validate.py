"""Validate upstream HDF5 recordings without confusing task failure with corrupt output."""

from pathlib import Path

import h5py
import numpy as np
from PIL import Image

from .contract import digest


def _text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def validate_recording(path, values, previews=None):
    records = []
    with h5py.File(path, "r") as source:
        data = source["data"]
        if _text(data.attrs.get("workflow", "")) != values["workflow"]:
            raise ValueError("Recording belongs to a different workflow")
        if _text(data.attrs.get("mode", "")) != "rule-based":
            raise ValueError("Recording did not execute the rule-based workflow")
        for name in sorted(
            data,
            key=lambda x: int(x.removeprefix("demo_")) if x.startswith("demo_") else -1,
        ):
            if not name.startswith("demo_"):
                raise ValueError("Recording contains an unfinished attempt")
            demo = data[name]
            steps = int(demo.attrs.get("num_samples", 0))
            if not 1 <= steps <= (values["episode_steps"] or 600):
                raise ValueError(
                    "Recording has missing samples or exceeds the requested scene cap"
                )
            if int(demo.attrs.get("recording_version", 0)) != 1:
                raise ValueError(
                    "Recording lacks the upstream v1 termination/reset boundary"
                )
            for field in ("actions", "obs/joint_pos"):
                array = demo[field][()]
                if array.shape != (steps, 6) or not np.isfinite(array).all():
                    raise ValueError(
                        f"Recording {field} must contain finite six-joint trajectories"
                    )
            if "initial_state" not in demo or "segments" not in demo:
                raise ValueError(
                    "Recording omits replay initial state or workflow task segmentation"
                )
            segments = demo["segments"][()]
            for row in segments:
                if not 0 <= int(row["start"]) <= int(row["end"]) <= steps:
                    raise ValueError("Workflow segment lies outside its recording")
            cameras = {}
            if not values["cameras"] and any(
                camera in demo["obs"] for camera in ("room", "wrist")
            ):
                raise ValueError("Recording contains images although cameras were disabled")
            for camera in ("room", "wrist") if values["cameras"] else ():
                frames = demo[f"obs/{camera}"]
                if (
                    frames.shape[0] != steps
                    or frames.ndim != 4
                    or frames.shape[-1] != 3
                ):
                    raise ValueError(
                        f"Camera {camera} frame count/shape differs from its trajectory"
                    )
                if frames.dtype != np.uint8:
                    raise ValueError(f"Camera {camera} must contain uint8 RGB images")
                # Check several actual rendered frames without loading a whole recording.
                indices = sorted({0, steps // 2, steps - 1})
                if not any(float(frames[index].std()) > 0 for index in indices):
                    raise ValueError(f"Camera {camera} returned only uniform images")
                cameras[camera] = {
                    "frames": steps,
                    "height": frames.shape[1],
                    "width": frames.shape[2],
                }
                if previews is not None:
                    previews.mkdir(parents=True, exist_ok=True)
                    for index in indices:
                        Image.fromarray(frames[index]).save(
                            previews / f"{name}-{camera}-{index:04d}.png"
                        )
            success = bool(demo.attrs.get("success", False))
            status = _text(demo.attrs.get("status", "unknown"))
            records.append(
                {
                    "demo": name,
                    "samples": steps,
                    "task_success": success,
                    "status": status,
                    "cameras": cameras,
                    "segments": len(segments),
                }
            )
    if not records:
        raise ValueError("Simulator did not record any completed attempt")
    successful = sum(row["task_success"] for row in records)
    if (
        successful > values["episodes"]
        or len(records) > values["episodes"] * values["attempts"]
    ):
        raise ValueError(
            "Recording episode counts exceed the requested scientific workload"
        )
    return {
        "sha256": digest(Path(path)),
        "size_bytes": Path(path).stat().st_size,
        "episodes": records,
        "successful_episodes": successful,
        "requested_episodes": values["episodes"],
        "task_complete": successful == values["episodes"],
        "samples": sum(row["samples"] for row in records),
    }
