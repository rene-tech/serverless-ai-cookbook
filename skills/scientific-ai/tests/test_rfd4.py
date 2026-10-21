"""Portable examples match the candidate hosted contract, not upstream CLI options."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "rfd4-proteina"
CONTRACT = json.loads((SKILL / "references/hosted-contract.json").read_text())
EXAMPLE = json.loads((SKILL / "examples/parameters.json").read_text())
VALIDATOR = Draft202012Validator(CONTRACT["parameters"])


def test_rfd4_example_preserves_every_declared_default():
    VALIDATOR.validate(EXAMPLE)
    assert EXAMPLE == {
        name: value["default"] for name, value in CONTRACT["parameters"]["properties"].items()
    }
    mapping = json.loads((ROOT / "manifest.json").read_text())["skills"]
    assert mapping["rfd4-proteina"] == [CONTRACT["model_id"]]
    assert mapping["rfdiffusion"] == ["rfdiffusion"]
    assert CONTRACT["tool_name"] == "submit_rfd4_proteina"
    assert CONTRACT["operation"] == "generate"
    assert CONTRACT["input"] == {
        "name": "annotated-cif", "semantic_type": "rfd4-proteina-annotated-cif/v1",
        "media_type": "chemical/x-cif", "compression": "none",
    }


@pytest.mark.parametrize("change", [
    {"num_replicates": 0}, {"batch_size": 0}, {"nsteps": 0},
    {"seed": -1}, {"seed": 4294967296}, {"seed": 1.5},
    {"partial_trajectory_fraction_steps": 0}, {"partial_trajectory_fraction_steps": 1.1},
    {"save_trajectory_every": -1}, {"recycle_strategy": "invented"},
    {"metrics_tags": ["unconditional_refolding"]},
    {"inputs": "/operator/private.yaml"}, {"ckpt_path": "/other/model"},
    {"generation.args.nsteps": 4},
])
def test_rfd4_does_not_turn_upstream_flags_into_hosted_parameters(change):
    assert list(VALIDATOR.iter_errors({**EXAMPLE, **change}))


@pytest.mark.parametrize("change", [
    {"num_replicates": 4, "batch_size": 2},
    {"partial_trajectory_fraction_steps": 0.5},
    {"recycle_strategy": "thinking_high", "nsteps": 90},
    {"compile": False, "save_trajectory_every": 10, "save_chain_of_interest": True},
])
def test_rfd4_explicit_supported_options_are_not_restricted_to_the_example(change):
    VALIDATOR.validate({**EXAMPLE, **change})
