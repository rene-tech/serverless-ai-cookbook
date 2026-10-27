"""Finite recorded-video runner for the real Holoscan 5 CAMMA LSTM graph.

The Python process prepares media and validates/publishes artifacts. Inference,
recurrent state, tensor transfer and postprocessing execute in the upstream C++
Holoscan graph, never in a substitute Python model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

MODEL = "holoscan-endoscopy"
SOURCE = "7d2e3b3c2b5d48bf0bc5caeba4d715b797ae3031"
WEIGHT_SHA256 = "d05733d49187f10975eafd762001f4535f5029fd071ca39779f953c7886a3c18"
WIDTH, HEIGHT = 854, 480
MASK_SHAPE = (7, 60, 107)
CLASSES = (
    "grasper",
    "bipolar",
    "hook",
    "scissors",
    "clipper",
    "irrigator",
    "specimen_bag",
)
DEFAULTS = {
    "video_file": "video.mp4",
    "frame_count": 0,
    "start_frame": 0,
    "frame_stride": 1,
    "probability_threshold": 0.5,
    "annotated_video": True,
}
FORMATS = "mov,matroska,avi,h264,hevc,mpegvideo,mpegts"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parameters(raw: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) - DEFAULTS.keys():
        raise ValueError("Unknown Holoscan parameter; use the published track-tools schema")
    values = {**DEFAULTS, **raw}
    for name in ("frame_count", "start_frame", "frame_stride"):
        v = values[name]
        minimum = 1 if name == "frame_stride" else 0
        # JSON Schema integers include integral numeric values such as 2.0 and 2e0.
        if type(v) not in (int, float) or not minimum <= v <= 2**32 - 1 or int(v) != v:
            raise ValueError(f"{name} must be an integer from {minimum} to 4294967295")
        values[name] = int(v)
    threshold = values["probability_threshold"]
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("probability_threshold must be a finite number between 0 and 1")
    if type(values["annotated_video"]) is not bool:
        raise ValueError("annotated_video must be a boolean")
    name = values["video_file"]
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("video_file must be a relative POSIX filename")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or path.as_posix() == ".":
        raise ValueError("video_file must be relative without parent traversal")
    values["video_file"] = path.as_posix()
    return values


def probe(video: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-format_whitelist",
        FORMATS,
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:stream_side_data=rotation,displaymatrix",
        "-of",
        "json",
        str(video),
    ]
    r = subprocess.run(command, capture_output=True, text=True)
    if r.returncode:
        raise ValueError(
            "Video could not be decoded; supply a readable MP4, MKV/WebM, AVI, H.264, HEVC or MPEG video"
        )
    streams = json.loads(r.stdout).get("streams", [])
    if not streams or min(streams[0].get("width", 0), streams[0].get("height", 0)) < 1:
        raise ValueError("Input contains no usable video stream")
    data = streams[0]
    for field in ("avg_frame_rate", "r_frame_rate"):
        try:
            numerator, denominator = map(int, data.get(field, "0/0").split("/"))
            fps = numerator / denominator
        except (ValueError, ZeroDivisionError):
            continue
        if fps > 0 and math.isfinite(fps):
            break
    else:
        raise ValueError("Video frame rate is missing; remux the recording with its known acquisition rate")
    display = next((item for item in data.get("side_data_list", []) if "rotation" in item), {})
    return {
        "width": data["width"],
        "height": data["height"],
        "fps": fps,
        "frame_count_metadata": data.get("nb_frames"),
        "duration_metadata": data.get("duration"),
        "display_rotation_degrees": display.get("rotation", 0),
        "display_matrix": display.get("displaymatrix"),
        "pixel_orientation": "encoded pixels; display rotation is recorded but not applied",
    }


def decode(video: Path, target: Path, values: dict) -> int:
    start, stride = values["start_frame"], values["frame_stride"]
    select = f"select=gte(n\\,{start})*not(mod(n-{start}\\,{stride})),scale={WIDTH}:{HEIGHT}:flags=bicubic"
    command = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-format_whitelist",
        FORMATS,
        "-noautorotate",
        "-i",
        str(video),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        select,
        "-fps_mode",
        "passthrough",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
    ]
    if values["frame_count"]:
        command += ["-frames:v", str(values["frame_count"])]
    command.append(str(target))
    r = subprocess.run(command, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        raise ValueError("Video conversion failed; check the encoding and available scratch disk")
    frame_bytes = WIDTH * HEIGHT * 3
    size = target.stat().st_size
    if not size or size % frame_bytes:
        raise ValueError("No complete selected frames; check start_frame, frame_stride and the video")
    count = size // frame_bytes
    if values["frame_count"] and count != values["frame_count"]:
        raise ValueError(
            f"Requested {values['frame_count']} frames but only {count} selected frames exist; "
            "use frame_count=0 for the remaining clip"
        )
    return count


def tracking_rows(path: Path, count: int):
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        for expected in range(count * 7):
            row = next(reader, None)
            if (
                row is None
                or int(row["frame_index"]) != expected // 7
                or int(row["tool_index"]) != expected % 7
            ):
                raise ValueError("Tracking output is incomplete or frame/tool order differs")
            values = [float(row[k]) for k in ("probability", "x_normalized", "y_normalized")]
            if not all(map(math.isfinite, values)) or not 0 <= values[0] <= 1:
                raise ValueError("Native model returned invalid probabilities or coordinates")
            yield row
        if next(reader, None) is not None:
            raise ValueError("Tracking output contains more frames than requested")


def package_masks(source: Path, output: Path, count: int):
    import numpy as np

    shape = (count, *MASK_SHAPE)
    if source.stat().st_size != math.prod(shape) * 4:
        raise ValueError("Native segmentation output has an incomplete tensor byte count")
    raw = np.memmap(source, mode="r", dtype="<f4", shape=shape)
    target = np.lib.format.open_memmap(output, mode="w+", dtype="<f4", shape=shape)
    for start in range(0, count, 16):
        block = raw[start : start + 16]
        if not np.isfinite(block).all():
            raise ValueError("Native model returned non-finite segmentation masks")
        target[start : start + 16] = block
    target.flush()
    del target, raw


def render(
    rgb: Path,
    masks_path: Path,
    table: Path,
    output: Path,
    count: int,
    fps: float,
    threshold: float,
):
    import numpy as np

    colors = np.array(
        [
            (0.12, 0.47, 0.71),
            (0.20, 0.63, 0.17),
            (0.89, 0.10, 0.11),
            (1, 0.50, 0),
            (0.42, 0.24, 0.60),
            (0.69, 0.35, 0.16),
            (0.65, 0.81, 0.89),
        ]
    )
    masks = np.load(masks_path, mmap_mode="r", allow_pickle=False)
    command = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    rows = iter(tracking_rows(table, count))
    ys, xs = np.arange(HEIGHT) * 60 // HEIGHT, np.arange(WIDTH) * 107 // WIDTH
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with rgb.open("rb") as stream:
            for frame in range(count):
                image = (
                    np.frombuffer(stream.read(WIDTH * HEIGHT * 3), np.uint8)
                    .reshape(HEIGHT, WIDTH, 3)
                    .astype(np.float32)
                )
                for tool in range(7):
                    row = next(rows)
                    if float(row["probability"]) > threshold:
                        alpha = ((np.clip(masks[frame, tool], 0.3, 0.99) - 0.3) / 0.69 * 0.7)[ys[:, None], xs]
                        image = image * (1 - alpha[:, :, None]) + colors[tool] * 255 * alpha[:, :, None]
                process.stdin.write(np.clip(image, 0, 255).astype(np.uint8).tobytes())
        process.stdin.close()
        if process.wait():
            raise ValueError("Annotated-video encoding failed; check output space and FFmpeg")
    except BaseException:
        process.kill()
        process.wait()
        raise


def file_record(path: Path) -> dict:
    return {"sha256": digest(path), "size_bytes": path.stat().st_size}


def graph_failure(transcript: str) -> str:
    """Keep observed native causes actionable without returning device/path internals."""
    causes = [
        (
            "libcuda.so.1: cannot open",
            (
                "Host CUDA driver library is unavailable; the operator must expose the "
                "NVIDIA driver to this container"
            ),
        ),
        (
            "CUDA driver version is insufficient",
            (
                "Host driver cannot initialize this runtime; the operator must select a "
                "compatible runtime or driver"
            ),
        ),
        (
            "no CUDA-capable device",
            "No CUDA device is available to the tracking graph; the operator must repair GPU assignment",
        ),
        (
            "invalid model probabilities or coordinates",
            (
                "The recurrent model returned invalid probabilities or coordinates; use the "
                "pinned FP32 runtime and retain this failing recording for investigation"
            ),
        ),
        (
            "segmentation masks contain non-finite",
            (
                "The recurrent model returned non-finite segmentation masks; retain the "
                "recording and contact the operator"
            ),
        ),
        (
            "failed to build TensorRT engine",
            (
                "TensorRT could not compile the pinned model; the operator must inspect "
                "engine-build diagnostics and available memory"
            ),
        ),
        (
            "pipeline timed out",
            (
                "The tracking graph exceeded its startup/stall allowance; inspect capacity "
                "and engine initialization before retrying"
            ),
        ),
    ]
    for token, message in causes:
        if token in transcript:
            return message
    return (
        "Holoscan graph execution failed before all selected frames completed; the "
        "operator must inspect the retained graph diagnostics before retrying"
    )


def validate_result(output: Path, *, expected_input=None, expected_parameters=None) -> dict:
    import numpy as np

    result = json.loads((output / "result.json").read_text())
    if (
        result.get("model") != MODEL
        or result.get("source_revision") != SOURCE
        or result.get("checkpoint_sha256") != WEIGHT_SHA256
    ):
        raise ValueError("Result model/source/checkpoint provenance differs")
    if expected_input is not None and result.get("input_sha256") != expected_input:
        raise ValueError("Result input identity differs")
    if expected_parameters is not None and result.get("parameters") != expected_parameters:
        raise ValueError("Result parameter identity differs")
    count = result.get("frames_completed")
    if type(count) is not int or count < 1 or result.get("inference") != "on":
        raise ValueError("No completed native model inference frames")
    for _ in tracking_rows(output / "tracking.csv", count):
        pass
    masks = np.load(output / "masks.npy", mmap_mode="r", allow_pickle=False)
    if masks.shape != (count, *MASK_SHAPE) or masks.dtype != np.dtype("<f4"):
        raise ValueError("Delivered segmentation tensor shape or dtype differs")
    for start in range(0, count, 16):
        if not np.isfinite(masks[start : start + 16]).all():
            raise ValueError("Delivered segmentation has non-finite values")
    names = {"tracking.csv", "masks.npy"} | (
        {"annotated.mp4"} if result["parameters"]["annotated_video"] else set()
    )
    if set(result.get("files", {})) != names:
        raise ValueError("Delivered artifact set differs from the request")
    for name in names:
        path = output / name
        if not path.is_file() or path.is_symlink() or result["files"][name] != file_record(path):
            raise ValueError("Delivered file bytes differ from the result inventory")
    return result


def run(
    video: Path,
    output: Path,
    values: dict,
    *,
    model: Path,
    binary: str,
    input_sha256=None,
    scratch=None,
) -> dict:
    started = time.monotonic()
    values = parameters(values)
    if not video.is_file():
        raise ValueError("Input video is missing; mount or upload the named video file")
    if not model.is_file() or digest(model) != WEIGHT_SHA256:
        raise ValueError("Pinned CAMMA ONNX model is missing or changed; prepare the 20230222 NGC model")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "result.json").exists():
        raise ValueError("Output already contains a result; use a new run directory")
    source = probe(video)
    with tempfile.TemporaryDirectory(prefix="holoscan-", dir=scratch) as temporary:
        work = Path(temporary)
        raw = work / "surgical_video.rgb"
        count = decode(video, raw, values)
        prepared = time.monotonic()
        native = work / "native"
        command = [
            binary,
            "--data",
            str(work),
            "--model",
            str(model),
            "--display",
            "false",
            "--inference",
            "true",
            "--count",
            str(count),
            "--period-ms",
            "1",
            "--engine-cache",
            str(work / "engines"),
            "--output-dir",
            str(native),
        ]
        with (work / "graph.log").open("w") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        transcript = (work / "graph.log").read_text(errors="replace")
        expected = f"expected={count} consumed={count} tracked={count} inference=on verdict=PASS"
        if completed.returncode or expected not in transcript:
            # Engine diagnostics are operator logs. Do not return local paths or device details in artifacts.
            print(transcript[-12000:], file=sys.stderr)
            raise RuntimeError(graph_failure(transcript))
        executed = time.monotonic()
        for _ in tracking_rows(native / "tracking.csv", count):
            pass
        shutil.copyfile(native / "tracking.csv", work / "tracking.csv")
        package_masks(native / "masks.f32", work / "masks.npy", count)
        names = ["tracking.csv", "masks.npy"]
        if values["annotated_video"]:
            render(
                raw,
                work / "masks.npy",
                work / "tracking.csv",
                work / "annotated.mp4",
                count,
                source["fps"] / values["frame_stride"],
                values["probability_threshold"],
            )
            names.append("annotated.mp4")
        packaged = time.monotonic()
        result = {
            "schema": "holoscan-endoscopy-result/v1",
            "model": MODEL,
            "operation": "track-tools",
            "source_revision": SOURCE,
            "checkpoint_sha256": WEIGHT_SHA256,
            "input_sha256": input_sha256 or digest(video),
            "parameters": values,
            "frames_completed": count,
            "inference": "on",
            "tool_classes": list(CLASSES),
            "source_video": source,
            "coordinates": {
                "space": "normalized encoded image before display rotation",
                "order": ["x", "y"],
                "original_pixel_mapping": "x * encoded source width, y * encoded source height",
                "display_pixel_mapping": (
                    "Apply the recorded source display matrix separately; "
                    "no display-coordinate claim is made"
                ),
            },
            "segmentation": {
                "shape": [count, *MASK_SHAPE],
                "dtype": "float32",
                "axes": ["frame", "tool", "y", "x"],
                "meaning": "native model mask values; overlapping tool channels are preserved",
            },
            "preprocessing": {
                "rgb": [HEIGHT, WIDTH, 3],
                "range": [0, 255],
                "resize": "bicubic stretch",
                "autorotation": False,
                "annotation_orientation": "encoded pixels, zero display rotation",
                "frame_selection": "source_index = start_frame + output_index * frame_stride",
                "recurrent_state": "zero at first selected frame; carried across selected frames only",
            },
            "runtime": {
                "holoscan": "5.0.0",
                "tensorrt": "10.16.0.72",
                "precision": "float32",
                "graph": [
                    "replayer",
                    "video_preprocessor",
                    "lstm_inference",
                    "postprocessor",
                    "tracking_sink",
                ],
            },
            "runtime_metrics": {
                "preparation_seconds": prepared - started,
                "graph_seconds": executed - prepared,
                "packaging_seconds": packaged - executed,
                "frames_completed": count,
                "frames_per_second_including_engine_build": count / (executed - prepared),
            },
            "limitations": [
                "Research tool tracking; not a diagnostic or clinical-control system",
                "Resizing and temporal subsampling can change predictions; no clinical accuracy claim",
                (
                    "Recorded-file processing only; live acquisition and end-to-end real-time "
                    "latency are unqualified"
                ),
            ],
            "files": {name: file_record(work / name) for name in names},
        }
        # All writes to durable mounted outputs are whole files; no rename/append semantics required.
        for name in names:
            with (
                (work / name).open("rb") as source_file,
                (output / name).open("wb") as target,
            ):
                shutil.copyfileobj(source_file, target, 1024 * 1024)
        (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return validate_result(output, expected_input=result["input_sha256"], expected_parameters=values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("/models/tool_loc_convlstm.onnx"))
    controls = parser.add_mutually_exclusive_group()
    controls.add_argument("--parameters-json", default="{}")
    controls.add_argument("--parameters-file", type=Path)
    parser.add_argument("--scratch-dir", type=Path)
    args = parser.parse_args()
    try:
        raw = args.parameters_file.read_text() if args.parameters_file else args.parameters_json
        result = run(
            args.input_video,
            args.output_dir,
            json.loads(raw),
            model=args.model,
            binary=os.environ.get("HOLOSCAN_ENDOSCOPY_BINARY", "endoscopy_tool_tracking"),
            scratch=args.scratch_dir,
        )
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Holoscan failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "frames_completed": result["frames_completed"],
                "artifacts": list(result["files"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
