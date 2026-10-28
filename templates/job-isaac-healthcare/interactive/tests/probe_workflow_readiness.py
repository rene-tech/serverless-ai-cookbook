"""Actual CPU Arena engine/recorder readiness hook, with no simulator or GPU."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from test_graceful_recording import simulation_at


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        marker = root / "startup-ready.json"
        simulation, task = simulation_at(root, "natural")
        phases = []
        simulation._reset_env = lambda seed=None: phases.append("reset")
        simulation.scene.on_reset = lambda env, view: phases.append("scene")
        original = simulation.scene.make_actuation
        first_record = []
        def actuation(env, view):
            if not first_record:
                assert not marker.exists()
            else:
                assert marker.read_bytes() == first_record[0]
            phases.append("actuation")
            return original(env, view)
        simulation.scene.make_actuation = actuation
        old_tick = task.tick
        def tick(ctx):
            value = json.loads(marker.read_text())
            assert phases[-3:] == ["reset", "scene", "actuation"]
            assert value["event"] == "workflow_started" and value["session_id"] == "ordinary-authored-session"
            assert value["pid"] == os.getpid()
            if not first_record:
                first_record.append(marker.read_bytes())
            return old_tick(ctx)
        task.tick = tick
        with patch.dict(os.environ, {"I4H_WORKFLOW_READY_FILE": str(marker), "I4H_WORKFLOW_READY_SESSION": "ordinary-authored-session"}):
            try:
                result = simulation.run()
            finally:
                simulation.recorder.close()
        assert result.complete and len(result.episodes) == 3
        assert list(root.glob("*.tmp")) == []
        print("actual engine workflow_started follows reset/actuation; natural completion and recorder close preserved")


if __name__ == "__main__":
    run()
