"""CPU contract/source checks. Synthetic artifacts are validator tests, not training proof."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get("I4H_TEST_SDK", "/opt/i4h"))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


RUN = module("training_run", HERE / "run.py")
BRIDGE = module("training_bridge", HERE / "bridge.py")


class InterpreterCases(unittest.TestCase):
    def test_none_preserves_upstream_default(self):
        self.assertIsNone(BRIDGE.explicit_interpreter(None, "training.runtime_python"))

    def test_virtualenv_symlink_identity_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "independent-policy-env/bin/python"
            path.parent.mkdir(parents=True)
            path.symlink_to(sys.executable)
            self.assertEqual(BRIDGE.explicit_interpreter(str(path), "training.runtime_python"), str(path))
            self.assertNotEqual(Path(BRIDGE.explicit_interpreter(str(path), "runtime")).resolve(), path)

    def test_relative_explicit_path_is_kept_in_its_selected_environment(self):
        relative = os.path.relpath(sys.executable)
        self.assertEqual(BRIDGE.explicit_interpreter(relative, "training.runtime_python"),
                         str(Path(relative).absolute()))

    def test_directory_and_nonexecutable_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "not-executable-python"
            script.write_text("#!/usr/bin/env python3\n")
            script.chmod(0o600)
            for value in (root, script, root / "absent-python"):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "will not fall back"):
                    BRIDGE.explicit_interpreter(str(value), "training.runtime_python")

    def test_explicit_model_and_simulator_are_validated_before_backend_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = str(Path(temporary) / "uninstalled-environment/bin/python")
            for field in ("runtime_python", "sim_runtime_python"):
                settings = {"runtime_python": None, "sim_runtime_python": None, field: missing}
                # No SDK or profile is needed to reject this invalid explicit
                # choice. An available Arena must not conceal the failure.
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "training\\." + field):
                    BRIDGE.rl({"training": settings, "arena_python": sys.executable})


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.sdk = self.root / "sdk"
        self.sdk.mkdir()
        (self.sdk / "DESIGN.md").write_text("User SDK project for CPU source preflight.\n")
        (self.sdk / "engine").mkdir()
        self.count = 0

    def call(self, operation, parameters, **kwargs):
        self.count += 1
        return RUN.run_operation(operation, input_dir=self.project, sdk_root=self.sdk,
                                 output_dir=self.root / f"output-{self.count}", parameters=parameters,
                                 arena_python=sys.executable, dataset_python=sys.executable, **kwargs)


class RLPreflightCases(ProjectCase):
    def setUp(self):
        super().setUp()
        import yaml
        shutil.copytree(UPSTREAM / "rl/i4h_rl", self.sdk / "rl/i4h_rl")
        name = "unseen_owned_workflow_731"
        self.name = name
        profile = yaml.safe_load((UPSTREAM / "rl/profiles/ultrasound_probe_reach.yaml").read_text())
        profile.update(workflow=name, scene=name, trainer_config="../config/custom.yaml")
        config = yaml.safe_load((UPSTREAM / "rl/config/ultrasound_probe_reach_ppo_rsl_rl.yaml").read_text())
        config["runner"]["experiment_name"] = name
        for path, value in [(self.sdk / f"rl/profiles/{name}.yaml", profile),
                            (self.sdk / "rl/config/custom.yaml", config),
                            (self.sdk / f"arena/i4h_arena/scenes/manifest/{name}.yaml", {"dof": 6, "cameras": []})]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(value))
        source = self.sdk / f"workflows/i4h_workflows/user-specialty/{name}.py"
        source.parent.mkdir(parents=True)
        source.write_text("# User workflow source; CPU preflight does not execute a simulator.\n")

    def test_unseen_project_and_explicit_parameters(self):
        result = self.call("train", {"workflow": self.name, "training": {"epochs": 3, "num_envs": 2}}, preflight=True)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["validation"]["workflow"], self.name)
        self.assertFalse(result["scientific_execution"])
        log = (self.root / "output-1/training-execution.log").read_text()
        self.assertIn("max epochs: 3", log)
        self.assertIn("parallel envs: 2", log)

    def test_valid_explicit_interpreter_reaches_real_upstream_preflight(self):
        result = self.call("train", {"workflow": self.name, "training": {
            "runtime_python": sys.executable, "epochs": 2}}, preflight=True)
        self.assertEqual(result["status"], "prepared")
        self.assertFalse(result["scientific_execution"])
        self.assertIn("max epochs: 2", (self.root / "output-1/training-execution.log").read_text())

    def test_missing_explicit_interpreters_fail_in_isolated_bridge_without_fallback(self):
        missing = str(self.root / "not-installed/bin/python")
        for field in ("runtime_python", "sim_runtime_python"):
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "will not fall back"):
                self.call("train", {"workflow": self.name, "training": {field: missing}}, preflight=True)
            cause = json.loads((self.root / f"output-{self.count}/training-engine-error.json").read_text())
            self.assertEqual(cause["type"], "ValueError")
            self.assertIn("training." + field, cause["cause"])

    def test_scene_contract_mismatch_actionable(self):
        path = self.sdk / f"arena/i4h_arena/scenes/manifest/{self.name}.yaml"
        path.write_text("dof: 7\ncameras: []\n")
        with self.assertRaisesRegex(RuntimeError, "action_dof=6.*dof=7"):
            self.call("train", {"workflow": self.name}, preflight=True)

    def test_bool_is_not_integer(self):
        with self.assertRaisesRegex(ValueError, "epochs must have type"):
            self.call("train", {"workflow": self.name, "training": {"epochs": True}}, preflight=True)

    def test_input_escape_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not traverse"):
            self.call("evaluate", {"workflow": self.name, "checkpoint": "../outside.pt"}, preflight=True)

    def test_upstream_rsl_resume_error_retained(self):
        (self.project / "resume").mkdir()
        with self.assertRaisesRegex(RuntimeError, "RSL-RL resume is not yet supported"):
            self.call("train", {"workflow": self.name, "training": {"resume_dir": "resume"}}, preflight=True)

    def test_upstream_evaluation_video_error_retained(self):
        (self.project / "checkpoint.pt").write_bytes(b"not-loaded-during-preflight")
        with self.assertRaisesRegex(RuntimeError, "evaluation video is not yet supported"):
            self.call("evaluate", {"workflow": self.name, "checkpoint": "checkpoint.pt", "training": {"video": True}}, preflight=True)

    def test_exit_zero_without_artifacts_is_not_success(self):
        class ExitZero:
            returncode = 0
        with patch.object(RUN.subprocess, "run", return_value=ExitZero()):
            with self.assertRaisesRegex(RuntimeError, "missing semantic result"):
                self.call("train", {"workflow": self.name})


class DatasetCases(ProjectCase):
    def setUp(self):
        super().setUp()
        shutil.copytree(UPSTREAM / "common/i4h_common", self.sdk / "common/i4h_common")
        shutil.copytree(UPSTREAM / "tools/dataset/i4h_tools", self.sdk / "tools/dataset/i4h_tools")
        descriptor = self.sdk / "arena/i4h_arena/embodiments/manifest/new_robot.yaml"
        descriptor.parent.mkdir(parents=True)
        descriptor.write_text("name: new_robot\naction_names: [q0, q1]\nstate_names: [q0, q1]\n")

    def recording(self, name="recording-with-unseen-name.bin", *, bad=False, success=False, frames=11):
        import h5py
        import numpy as np
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(path, "w") as handle:
            demo = handle.create_group("data/demo_42")
            demo.attrs.update(num_samples=frames, success=success)
            values = np.arange(frames * 2, dtype=np.float32).reshape(frames, 2)
            if bad:
                values[2, 1] = np.nan
            demo.create_dataset("actions", data=values)
            demo.create_dataset("obs/joint_pos", data=np.zeros((frames, 2), dtype=np.float32))
            demo.create_dataset("obs/custom_camera", data=np.zeros((frames, 4, 6, 3), dtype=np.uint8))
        return str(path.relative_to(self.project))

    def test_real_upstream_inspection_retains_unsuccessful_episode(self):
        name = self.recording()
        result = self.call("dataset-inspect", {"dataset": name, "dataset_options": {"segments": True}})
        demo = result["validation"]["recordings"][0]["episodes"][0]
        self.assertEqual(demo["samples"], 11)
        self.assertFalse(demo["success"])
        self.assertEqual(demo["cameras"]["custom_camera"], [11, 4, 6, 3])

    def test_directory_signature_discovery(self):
        self.recording("group/alpha.unknown")
        self.recording("group/beta.dat", frames=7)
        (self.project / "group/notes.json").write_text("{}")
        result = self.call("dataset-inspect", {"dataset": "group"})
        self.assertEqual(len(result["validation"]["recordings"]), 2)

    def test_nonfinite_actions_fail_with_cause(self):
        name = self.recording(bad=True)
        with self.assertRaisesRegex(RuntimeError, "state/action tensors contain NaN or infinity"):
            self.call("dataset-inspect", {"dataset": name})

    def test_unseen_descriptor_conversion_preflight(self):
        name = self.recording(success=True, frames=17)
        result = self.call("dataset-convert", {"dataset": name, "dataset_options": {
            "robot": "new_robot", "skip_frames": 3, "fps": 24, "successful_only": True}}, preflight=True)
        self.assertEqual(result["validation"]["robot"], "new_robot")
        self.assertEqual(result["validation"]["selected_frames"], 14)

    def test_filter_cannot_silently_produce_empty_dataset(self):
        name = self.recording(success=False)
        with self.assertRaisesRegex(RuntimeError, "leaves no frames"):
            self.call("dataset-convert", {"dataset": name, "dataset_options": {
                "robot": "new_robot", "successful_only": True}}, preflight=True)


class CheckpointCases(unittest.TestCase):
    def test_current_rsl5_checkpoint_serialization_and_nan(self):
        import torch
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "any-checkpoint-name.pt"
            value = {"actor_state_dict": {"w": torch.arange(6, dtype=torch.float32).reshape(2, 3)},
                     "critic_state_dict": {"w": torch.ones((1, 3))}, "optimizer_state_dict": {}, "iter": 8}
            torch.save(value, path)
            checked = BRIDGE.validate_checkpoint(path)
            self.assertEqual(checked["iteration"], 8)
            self.assertEqual(checked["parameter_elements"], 9)
            value["actor_state_dict"]["w"][0, 0] = float("nan")
            torch.save(value, path)
            with self.assertRaisesRegex(ValueError, "non-finite model weights"):
                BRIDGE.validate_checkpoint(path)

    def test_evaluation_preserves_failure_and_rejects_forged_totals(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evaluation.json"
            value = {"task": "unseen_scene", "episodes": 2, "successes": 0, "success_rate": 0.0,
                     "results": [{"success": False, "steps": 7}, {"success": False, "steps": 9}]}
            path.write_text(json.dumps(value))
            self.assertEqual(BRIDGE.validate_evaluation(path, expected_task="unseen_scene", expected_episodes=2)["successes"], 0)
            value["successes"] = 2
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "aggregates disagree"):
                BRIDGE.validate_evaluation(path)


if __name__ == "__main__":
    unittest.main()
