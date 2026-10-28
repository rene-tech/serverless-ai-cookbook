"""CPU media/contract checks. These tests do not claim neural inference."""

import csv
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location(
    "holoscan_video", Path(__file__).parents[1] / "src/holoscan_video.py"
)
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class VideoContractTest(unittest.TestCase):
    def test_rotation_metadata_does_not_change_encoded_geometry_or_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, rotated = root / "original.mp4", root / "rotated.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=160x96:rate=7",
                    "-frames:v",
                    "2",
                    "-c:v",
                    "libx264",
                    str(original),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-display_rotation:v:0",
                    "37",
                    "-i",
                    str(original),
                    "-c",
                    "copy",
                    str(rotated),
                ],
                check=True,
            )
            metadata = video.probe(rotated)
            self.assertNotEqual(metadata["display_rotation_degrees"], 0)
            self.assertEqual((metadata["width"], metadata["height"]), (160, 96))
            self.assertIsNotNone(metadata["display_matrix"])
            for name, clip in [("original", original), ("rotated", rotated)]:
                self.assertEqual(video.decode(clip, root / f"{name}.rgb", video.parameters({})), 2)
            self.assertEqual((root / "original.rgb").read_bytes(), (root / "rotated.rgb").read_bytes())
            np.save(root / "masks.npy", np.zeros((2, 7, 60, 107), dtype="<f4"), allow_pickle=False)
            with (root / "tracking.csv").open("w") as stream:
                writer = csv.writer(stream)
                writer.writerow(["frame_index", "tool_index", "probability", "x_normalized", "y_normalized"])
                writer.writerows([[frame, tool, 0.1, 0.3, 0.4] for frame in range(2) for tool in range(7)])
            video.render(
                root / "rotated.rgb",
                root / "masks.npy",
                root / "tracking.csv",
                root / "annotated.mp4",
                2,
                7,
                0.5,
            )
            annotation = video.probe(root / "annotated.mp4")
            self.assertEqual((annotation["width"], annotation["height"]), (854, 480))
            self.assertEqual(annotation["display_rotation_degrees"], 0)
            self.assertEqual(
                video.decode(root / "annotated.mp4", root / "annotated.rgb", video.parameters({})), 2
            )

    def test_json_integer_representations_normalize_before_frame_selection(self):
        raw = json.loads('{"frame_count": 3.0, "start_frame": 2e0, "frame_stride": 1.0}')
        normalized = video.parameters(raw)
        for name in raw:
            self.assertIs(type(normalized[name]), int)
            for invalid in (True, False, 1.5, float("nan"), float("inf"), "2", 2**32):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ValueError):
                    video.parameters({name: invalid})
        self.assertEqual(video.parameters({"start_frame": -0.0})["start_frame"], 0)
        self.assertEqual(video.parameters({"frame_count": 4294967295.0})["frame_count"], 4294967295)

    def test_temporal_parameters_are_explicit_and_not_filename_gated(self):
        self.assertEqual(
            video.parameters({"video_file": "new recording/changed name.mp4"})["frame_count"],
            0,
        )
        for invalid in (
            {"frame_stride": 0},
            {"frame_count": True},
            {"start_frame": -1},
            {"probability_threshold": float("nan")},
            {"video_file": "../private"},
            {"annotated_video": "true"},
            {"unknown": 1},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                video.parameters(invalid)

    def test_real_ffmpeg_decoder_and_selected_frame_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / "previously unseen clip.mkv"
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=320x240:rate=12",
                    "-frames:v",
                    "9",
                    "-c:v",
                    "ffv1",
                    str(clip),
                ],
                check=True,
            )
            self.assertEqual(video.probe(clip)["width"], 320)
            selected = video.decode(
                clip,
                root / "selected.rgb",
                video.parameters({"start_frame": 2, "frame_stride": 3}),
            )
            self.assertEqual(selected, 3)
            self.assertEqual((root / "selected.rgb").stat().st_size, 3 * 854 * 480 * 3)
            with self.assertRaisesRegex(ValueError, "only 3 selected"):
                video.decode(
                    clip,
                    root / "too-many.rgb",
                    video.parameters({"start_frame": 2, "frame_stride": 3, "frame_count": 4}),
                )
            (root / "bad.mp4").write_bytes(b"not a video")
            with self.assertRaisesRegex(ValueError, "could not be decoded"):
                video.probe(root / "bad.mp4")

    def test_semantic_validator_rejects_order_nonfinite_and_byte_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / "tracking.csv").open("w") as stream:
                writer = csv.writer(stream)
                writer.writerow(
                    [
                        "frame_index",
                        "tool_index",
                        "probability",
                        "x_normalized",
                        "y_normalized",
                    ]
                )
                writer.writerows([[0, tool, 0.8, 0.3, 0.4] for tool in range(7)])
            np.save(
                root / "masks.npy",
                np.zeros((1, 7, 60, 107), dtype="<f4"),
                allow_pickle=False,
            )
            values = video.parameters({"annotated_video": False})
            result = {
                "model": video.MODEL,
                "source_revision": video.SOURCE,
                "checkpoint_sha256": video.WEIGHT_SHA256,
                "frames_completed": 1,
                "inference": "on",
                "input_sha256": "a" * 64,
                "parameters": values,
                "files": {name: video.file_record(root / name) for name in ("tracking.csv", "masks.npy")},
            }
            (root / "result.json").write_text(json.dumps(result))
            self.assertEqual(video.validate_result(root)["frames_completed"], 1)
            with self.assertRaisesRegex(ValueError, "input identity"):
                video.validate_result(root, expected_input="b" * 64)
            values2 = {**values, "start_frame": 1}
            with self.assertRaisesRegex(ValueError, "parameter identity"):
                video.validate_result(root, expected_parameters=values2)
            with (root / "tracking.csv").open("a") as stream:
                stream.write("0,0,.8,.3,.4\n")
            with self.assertRaisesRegex(ValueError, "more frames"):
                video.validate_result(root)

    def test_mask_nan_and_truncated_stream_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mask = np.zeros((1, 7, 60, 107), dtype="<f4")
            mask[0, 0, 0, 0] = float("nan")
            mask.tofile(root / "masks.f32")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                video.package_masks(root / "masks.f32", root / "masks.npy", 1)
            (root / "masks.f32").write_bytes(b"short")
            with self.assertRaisesRegex(ValueError, "incomplete tensor"):
                video.package_masks(root / "masks.f32", root / "masks.npy", 1)


if __name__ == "__main__":
    unittest.main()
