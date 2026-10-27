"""Scientific controls; no customer, filename or fixture-specific execution gates."""

import hashlib
import json
from importlib.resources import files

from jsonschema import Draft202012Validator

SOURCE = "5b430a6d8d8c9cccc547b05b5e079d22b08ade9e"
ASSET_GENERATION = "v0.9.0/7cf86a1"
MODEL_ID = "isaac-healthcare"
OPERATION = "simulate"


def schema(name):
    return json.loads(files(__package__).joinpath(name + ".schema.json").read_text())


def checked(value, contract, label):
    errors = sorted(
        Draft202012Validator(contract).iter_errors(value), key=lambda e: str(e.path)
    )
    if errors:
        path = "/".join(map(str, errors[0].path)) or label
        raise ValueError(
            f"Invalid {label} field {path}; follow the published schema ({errors[0].validator})"
        )
    return value


def parameters(value):
    contract = schema("parameters")
    checked(value, contract, "parameters")
    result = {name: spec["default"] for name, spec in contract["properties"].items()}
    result.update(value)
    # JSON Schema integer includes 1.0; argparse's integer options require "1".
    for name in ("episodes", "attempts", "episode_steps"):
        if result[name] is not None:
            result[name] = int(result[name])
    return result


def scenarios(value):
    checked(value, schema("scenarios"), "scenarios")
    names = [row["name"] for row in value["scenarios"]]
    if len(set(names)) != len(names):
        raise ValueError("Scenario names must be unique within this simulation input")
    return [
        {
            "name": row["name"],
            "seed": int(row["seed"]) if row.get("seed") is not None else None,
        }
        for row in value["scenarios"]
    ]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024**2):
            result.update(block)
    return result.hexdigest()
