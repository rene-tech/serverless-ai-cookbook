"""Scientific controls; no customer, filename or fixture-specific execution gates."""

import hashlib
import json
from copy import deepcopy
from importlib.resources import files

from jsonschema import Draft202012Validator

SOURCE = "5b430a6d8d8c9cccc547b05b5e079d22b08ade9e"
ASSET_GENERATION = "v0.9.0/7cf86a1"
MODEL_ID = "isaac-healthcare"
OPERATIONS = ("inspect", "lint", "simulate", "replay", "train", "evaluate", "export", "dataset-inspect", "dataset-convert")


def json_loads(value):
    """Reject duplicate keys rather than silently accepting a different request."""
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = item
        return result

    return json.loads(value, object_pairs_hook=pairs,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"Invalid JSON number: {token}")))


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
    result = {name: deepcopy(spec["default"]) for name, spec in contract["properties"].items() if "default" in spec}
    result.update(deepcopy(value))
    # JSON Schema integer includes 1.0; argparse's integer options require "1".
    for name in ("episodes", "attempts", "episode_steps", "envs", "seed"):
        if result[name] is not None:
            result[name] = int(result[name])
    result["replay_episodes"] = [int(value) for value in result["replay_episodes"]]
    for group in ("training", "dataset_options"):
        if group in result:
            for key, value in result[group].items():
                types = contract["properties"][group]["properties"][key].get("type", [])
                if "integer" in types and value is not None:
                    result[group][key] = int(value)
    return result


def scenarios(value, default_seed=None):
    checked(value, schema("scenarios"), "scenarios")
    names = [row["name"] for row in value["scenarios"]]
    if len(set(names)) != len(names):
        raise ValueError("Scenario names must be unique within this simulation input")
    return [
        {
            "name": row["name"],
            "seed": (int(row["seed"]) if row["seed"] is not None else None) if "seed" in row else default_seed,
        }
        for row in value["scenarios"]
    ]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024**2):
            result.update(block)
    return result.hexdigest()
