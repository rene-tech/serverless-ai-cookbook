"""CPU tests exercise scientific validation boundaries; they are not simulator evidence."""

import json

import h5py
import numpy as np
import pytest

from isaac_healthcare_runtime.contract import parameters, scenarios
from isaac_healthcare_runtime.runtime import command
from isaac_healthcare_runtime.validate import validate_recording


def recording(path, success=False, cameras=True):
    with h5py.File(path, "w") as f:
        data = f.create_group("data")
        data.attrs.update(workflow="scissor_pick_and_place", mode="rule-based")
        demo = data.create_group("demo_0")
        demo.attrs.update(
            num_samples=3,
            recording_version=1,
            success=success,
            status="succeeded" if success else "timed_out",
        )
        demo.create_dataset("actions", data=np.ones((3, 6), dtype=np.float32))
        demo.create_dataset("obs/joint_pos", data=np.ones((3, 6), dtype=np.float32))
        demo.create_dataset(
            "initial_state/rigid_object/scissors/root_pose", data=np.ones((1, 7))
        )
        dtype = np.dtype([("start", "<i8"), ("end", "<i8")])
        demo.create_dataset("segments", data=np.array([(0, 3)], dtype=dtype))
        if cameras:
            for name in ("room", "wrist"):
                demo.create_dataset(
                    f"obs/{name}",
                    data=np.arange(3 * 4 * 4 * 3, dtype=np.uint8).reshape(3, 4, 4, 3),
                )


def test_arbitrary_names_seeds_and_explicit_parameters_do_not_change_execution(
    tmp_path,
):
    values = parameters(
        {"episodes": 2, "attempts": 3, "episode_steps": 72, "cameras": False}
    )
    row = scenarios(
        {
            "schema": "isaac-healthcare-scenarios/v1",
            "scenarios": [{"name": "../../a new name", "seed": 1987}],
        }
    )[0]
    argv = command(values, row, tmp_path)
    assert row["name"] not in argv
    assert argv[argv.index("--episodes") + 1] == "2"
    assert argv[argv.index("--episode-steps") + 1] == "72"
    assert argv[argv.index("--seed") + 1] == "1987"
    assert "--no-cameras" in argv
    defaults = command(parameters({}), {"name": "unseen", "seed": None}, tmp_path)
    assert "--episode-steps" not in defaults and "--presets" not in defaults


@pytest.mark.parametrize(
    "value",
    [
        {"episode_steps": 601},
        {"episode_steps": 0},
        {"episodes": True},
        {"episodes": 0},
        {"physics": "newton"},
        {"hidden_tuning": True},
    ],
)
def test_reject_unsupported_or_invalid_controls(value):
    with pytest.raises(ValueError, match="Invalid"):
        parameters(value)


def test_duplicate_scenario_names_rejected():
    with pytest.raises(ValueError, match="unique"):
        scenarios(
            {
                "schema": "isaac-healthcare-scenarios/v1",
                "scenarios": [{"name": "same"}, {"name": "same"}],
            }
        )


def test_task_timeout_remains_a_valid_unsuccessful_recording(tmp_path):
    path = tmp_path / "recording.hdf5"
    recording(path)
    report = validate_recording(path, parameters({}), tmp_path / "previews")
    assert report["task_complete"] is False
    assert report["successful_episodes"] == 0
    assert report["episodes"][0]["status"] == "timed_out"
    assert len(list((tmp_path / "previews").glob("*.png"))) == 6


def test_nonfinite_trajectory_and_empty_render_are_rejected(tmp_path):
    path = tmp_path / "recording.hdf5"
    recording(path, success=True)
    with h5py.File(path, "a") as f:
        f["data/demo_0/actions"][1, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        validate_recording(path, parameters({}))
    recording(path, success=True)
    with h5py.File(path, "a") as f:
        f["data/demo_0/obs/wrist"][:] = 0
    with pytest.raises(ValueError, match="uniform"):
        validate_recording(path, parameters({}))


def test_explicit_camera_disable_has_no_images(tmp_path):
    path = tmp_path / "recording.hdf5"
    values = parameters({"cameras": False})
    recording(path, cameras=False)
    assert validate_recording(path, values)["episodes"][0]["cameras"] == {}
    recording(path, cameras=True)
    with pytest.raises(ValueError, match="cameras were disabled"):
        validate_recording(path, values)


def test_missing_or_extra_frames_and_stale_reset_schema_fail(tmp_path):
    path = tmp_path / "recording.hdf5"
    recording(path)
    with h5py.File(path, "a") as f:
        f["data/demo_0"].attrs["recording_version"] = 0
    with pytest.raises(ValueError, match="reset"):
        validate_recording(path, parameters({}))
    recording(path)
    with h5py.File(path, "a") as f:
        f["data/demo_0"].attrs["num_samples"] = 4
    with pytest.raises(ValueError, match="trajectories"):
        validate_recording(path, parameters({}))


def test_schema_examples_are_valid():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    scenarios(json.loads((root / "examples/scenarios.json").read_text()))
    parameters(json.loads((root / "examples/parameters.json").read_text()))


def test_schema_integer_equivalent_numbers_reach_integer_cli_options(tmp_path):
    values = parameters({"episodes": 1.0, "attempts": 2.0, "episode_steps": 60.0})
    row = scenarios(
        {
            "schema": "isaac-healthcare-scenarios/v1",
            "scenarios": [{"name": "equivalent JSON numbers", "seed": 17.0}],
        }
    )[0]
    argv = command(values, row, tmp_path)
    for flag in ("--episodes", "--attempts", "--episode-steps", "--seed"):
        assert str(int(argv[argv.index(flag) + 1])) == argv[argv.index(flag) + 1]


def test_full_failure_diagnostics_stay_in_operator_channel(
    tmp_path, monkeypatch, capsys
):
    import sys

    from isaac_healthcare_runtime import runtime

    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    directory = tmp_path / "output/simulation/scenario-000000"
    directory.mkdir(parents=True)
    code, log = runtime.execute(
        [
            sys.executable,
            "-c",
            "print('GPU placement diagnostics'); print('RuntimeError: missing asset'); raise SystemExit(3)",
        ],
        directory,
    )
    assert code == 3
    assert log.parent == tmp_path / "output/.operator"
    assert "RuntimeError: missing asset" in log.read_text()
    assert "GPU placement diagnostics" in capsys.readouterr().out
    assert not (directory / "simulator.log").exists()


def test_result_archive_preserves_science_and_excludes_device_logs(
    tmp_path, monkeypatch
):
    import tarfile

    from isaac_healthcare_runtime import runtime

    manifest = tmp_path / "assets.json"
    manifest.write_text('{"files": [], "asset_generation": "test-only"}')
    monkeypatch.setattr(runtime, "ASSET_MANIFEST", manifest)
    patch_manifest = tmp_path / "upstream-patches.json"
    patch_manifest.write_text('{"schema": "isaac-healthcare-upstream-patches/v1", "patches": []}')
    monkeypatch.setattr(runtime, "PATCH_MANIFEST", patch_manifest)
    monkeypatch.setenv("ACCEPT_EULA", "Y")

    def execute(argv, directory):
        recording(directory / "demos.hdf5", success=True)
        (directory / ".runtime").mkdir()
        operator = directory.parent.parent / ".operator"
        operator.mkdir()
        log = operator / "scenario-000000.log"
        log.write_text(
            "GPU placement diagnostics\n"
            "scissor_pick_and_place [rule-based] run=synthetic-test: "
            "1/1 episodes succeeded (1 attempts); 1 new demonstrations saved\n"
        )
        return 0, log

    monkeypatch.setattr(runtime, "execute", execute)
    source = tmp_path / "scenario.json"
    source.write_text(
        json.dumps(
            {
                "schema": "isaac-healthcare-scenarios/v1",
                "scenarios": [{"name": "ordinary new scenario", "seed": 891}],
            }
        )
    )
    report = runtime.run(source, {}, tmp_path / "output")
    assert report["task_complete"] is True
    assert "GPU" not in json.dumps(report)
    with tarfile.open(tmp_path / "output/simulation.tar") as archive:
        assert "assets.json" in archive.getnames()
        assert "upstream-patches.json" in archive.getnames()
        assert not any(
            "operator" in name or "simulator.log" in name for name in archive.getnames()
        )
        scientific_log = archive.extractfile("scenario-000000/workflow.log").read()
        assert (
            b"ordinary new scenario" in scientific_log and b"GPU" not in scientific_log
        )
