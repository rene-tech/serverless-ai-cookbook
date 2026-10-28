"""CPU real-recorder gate; run with Arena's dependencies, never needs Kit/GPU.

By default this imports the installed runner. I4H_TEST_RUNNER_SOURCE may select
the reviewed patched source during a source-only test; that is not an installed
image qualification.
"""

import importlib.util
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import torch
from i4h_arena import runner
from i4h_arena.recording.hdf5 import EpisodeRecorder
from i4h_engine.graph import TaskGraph
from i4h_engine.status import Status, WorkflowStatus
from i4h_engine.task import Task

if source := os.environ.get("I4H_TEST_RUNNER_SOURCE"):
    spec = importlib.util.spec_from_file_location("reviewed_arena_runner", source)
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)


class ControlledTask(Task):
    def __init__(self, mode, closed):
        super().__init__(name="controlled")
        self.mode, self.closed, self.ticks = mode, closed, 0

    def on_enter(self, ctx, inputs):
        self.ticks = 0

    def tick(self, ctx):
        self.ticks += 1
        if self.mode == "empty":
            return Status.SUCCESS
        if self.mode == "failure":
            raise ValueError("actual task failed before the first sample")
        if self.ticks == 3:
            if self.mode in ("SIGINT", "SIGTERM"):
                signal.raise_signal(getattr(signal, self.mode))
            else:
                return Status.SUCCESS
        return Status.RUNNING

    def on_abort(self, ctx):
        self.closed.write_text("task aborted through the engine\n")


def simulation_at(path, mode, *, keep=True):
    simulation = object.__new__(runner.SimulationRunner)
    task = ControlledTask(mode, path / "task-closed")
    workflow = SimpleNamespace(
        name="controlled",
        mode="teleop",
        scene="owned-cpu-scene",
        graph=TaskGraph().add(task),
    )
    actuation = SimpleNamespace(
        tensor=lambda: torch.tensor([[1.0, 2.0, 3.0]]),
        numpy=lambda: np.array([[1.0, 2.0, 3.0]]),
    )
    simulation.app = SimpleNamespace(is_running=lambda: True)
    simulation.env = SimpleNamespace(
        step=lambda command: None, unwrapped=SimpleNamespace(step_dt=0.02)
    )
    simulation.scene = SimpleNamespace(
        on_reset=lambda env, view: None, make_actuation=lambda env, view: actuation
    )
    simulation._view = SimpleNamespace(
        on_step=lambda: None,
        joints=lambda: SimpleNamespace(pos=np.array([[0.1, 0.2, 0.3]])),
    )
    simulation._reset_env = lambda seed=None: None
    simulation.workflow, simulation.run_id = workflow, "owned-cpu-run"
    simulation.keys = simulation.bus = simulation.publisher = simulation.seed = None
    simulation._controls, simulation._sensor_windows = {}, ()
    simulation.episodes, simulation.attempts = 3, 2
    simulation._requested_max_steps, simulation.max_steps = 100, 100
    simulation.record_failures = keep
    simulation.recorder = EpisodeRecorder(path / "measurements.hdf5", workflow=workflow)
    return simulation, task


class GracefulRecording(unittest.TestCase):
    def execute(self, mode, *, keep=True):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)
        simulation, task = simulation_at(path, mode, keep=keep)
        before = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            summary = simulation.run()
        finally:
            simulation.recorder.close()  # Same outer-CLI finally as real launch.
        self.assertEqual(before, {s: signal.getsignal(s) for s in before})
        self.assertIsNone(runner._ACTIVE_RUNNER)
        return path, summary, task

    def test_sigint_and_sigterm_abort_and_close_real_partial_recording(self):
        for mode in ("SIGINT", "SIGTERM"):
            with self.subTest(mode=mode):
                path, summary, task = self.execute(mode)
                self.assertFalse(summary.complete)
                self.assertEqual(len(summary.episodes), 1)
                self.assertEqual(summary.episodes[0].status, WorkflowStatus.ABORTED)
                self.assertEqual(summary.episodes[0].detail, f"received {mode}")
                self.assertTrue((path / "task-closed").is_file())
                self.assertEqual(task.ticks, 3)
                with h5py.File(path / "measurements.hdf5", "r") as data:
                    demo = data["data/demo_0"]
                    self.assertFalse(bool(demo.attrs["success"]))
                    self.assertEqual(demo.attrs["status"], "aborted")
                    np.testing.assert_array_equal(demo["actions"][:], [[1, 2, 3]] * 3)
                    self.assertNotIn("_attempt", data["data"])

    def test_signal_respects_explicit_record_failures_false(self):
        path, summary, task = self.execute("SIGINT", keep=False)
        self.assertFalse(summary.complete)
        self.assertTrue((path / "task-closed").is_file())
        with h5py.File(path / "measurements.hdf5", "r") as data:
            self.assertEqual(list(data["data"]), [])

    def test_natural_completion_is_unchanged(self):
        path, summary, task = self.execute("natural")
        self.assertTrue(summary.complete)
        self.assertFalse((path / "task-closed").exists())
        with h5py.File(path / "measurements.hdf5", "r") as data:
            self.assertEqual(len(data["data"]), 3)
            self.assertTrue(
                all(bool(demo.attrs["success"]) for demo in data["data"].values())
            )

    def test_empty_valid_recording_is_not_a_product_failure(self):
        path, summary, task = self.execute("empty")
        self.assertTrue(summary.complete)
        with h5py.File(path / "measurements.hdf5", "r") as data:
            self.assertEqual(list(data["data"]), [])

    def test_real_task_failure_remains_failed_and_file_is_closed(self):
        path, summary, task = self.execute("failure")
        self.assertFalse(summary.complete)
        self.assertTrue(
            all(r.status == WorkflowStatus.FAILED for r in summary.episodes)
        )
        self.assertIn("actual task failed", summary.episodes[0].detail)
        with h5py.File(path / "measurements.hdf5", "r") as data:
            self.assertEqual(list(data["data"]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
