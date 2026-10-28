"""Qualify the unchanged portable CLI with offline execution and scoped transfers."""

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from isaac_healthcare_runtime.contract import OPERATIONS, json_loads

PYTHON = "/opt/i4h/arena/.venv/bin/python"
CODE = Path(__file__).resolve().parent


def verify_installation(output, *, code=None):
    """Check the exact installed source/dependencies before any scientific work."""
    code = CODE if code is None else Path(code)
    expected = json.loads((code / "runtime-sources.json").read_bytes())
    if expected.get("schema") != "isaac-healthcare-runtime-source-contract/v1":
        raise RuntimeError("Required execution-source ownership contract is missing")
    for name, row in expected["files"].items():
        source = Path(name)
        if not source.is_absolute() or not row.get("owner"):
            raise RuntimeError("Execution source lacks an absolute path or declared owner")
        try:
            observed = hashlib.sha256(source.read_bytes()).hexdigest()
        except OSError as error:
            raise RuntimeError("Required runtime source is unavailable (" + row["owner"] + "): " + name) from error
        if observed != row["sha256"]:
            raise RuntimeError("Installed runtime source differs (" + row["owner"] + "): " + name)
    distributions = json.loads((code / "distributions.json").read_bytes())
    actual = {d.metadata["Name"].lower().replace("_", "-"): d.version
              for d in importlib.metadata.distributions()}
    if actual != {name: row["version"] for name, row in distributions["distributions"].items()}:
        raise RuntimeError("Installed native package versions differ from the reviewed inventory")
    subprocess.run([PYTHON, "-I", "/opt/isaac-healthcare/scripts/verify_runtime.py"], check=True)
    source_check = {
        "files_verified": len(expected["files"]), "distribution_count": len(actual),
        "source_owners": sorted({row["owner"] for row in expected["files"].values()}),
        "mutable_build_files_required": False, "uid": os.getuid(), "source_check": "passed",
        "portable_image": expected["portable_image"],
    }
    (output / "installed-source-check.json").write_text(json.dumps(source_check, indent=2) + "\n")
    print(json.dumps({"event": "isaac-runtime-source-check", **source_check}), flush=True)
    return source_check


def run():
    incoming = Path(os.environ["ISAAC_PROVIDER_INPUT"]) / "input.tar"
    output = Path(os.environ["ISAAC_PROVIDER_OUTPUT"])
    verify_installation(output)
    with tempfile.TemporaryDirectory(prefix="isaac-bundle-") as temporary:
        root = Path(temporary)
        with tarfile.open(incoming, "r:") as archive:
            names = set()
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or "\\" in member.name:
                    raise ValueError("Bundle paths must be relative POSIX paths")
                if not member.isfile() or member.name in names:
                    raise ValueError("Bundle must contain unique regular files")
                names.add(member.name)
            archive.extractall(root, filter="data")
        request = json_loads((root / "request.json").read_bytes())
        if (request.get('schema') != 'isaac-healthcare-bundle/v2'
                or set(request) != {'schema', 'operation', 'scenarios', 'project'}
                or request['operation'] not in OPERATIONS
                or not isinstance(request['scenarios'], bool)
                or not isinstance(request['project'], bool)):
            raise ValueError('Invalid general Isaac bundle request')
        expected_names = {'request.json', 'parameters.json'}
        if request['scenarios']:
            expected_names.add('scenarios.json')
        if request['project']:
            expected_names.add('project.tar')
        if names != expected_names:
            raise ValueError('Bundle inputs differ from their explicit request')
        source = root / "scenarios.json" if request['scenarios'] else None
        project = root / "project.tar" if request['project'] else None
        parameters = root / "parameters.json"
        command = [PYTHON, "-I", "/opt/isaac-healthcare/scripts/run_serverless.py",
                   "--operation", request['operation'], "--parameters", str(parameters),
                   "--output-prefix", str(output / "science")]
        input_args = []
        if source is not None:
            input_args.extend(['--input', str(source)])
        if project is not None:
            input_args.extend(['--project', str(project)])
        command.extend(input_args)
        # The transfer parent retains network access. Only this fresh child and
        # the normal simulator descendants inherit the additional kernel filter.
        result = subprocess.run([PYTHON, "-I", str(CODE / "offline_exec.py"),
                                 "--receipt", str(output / "offline-execution.json"),
                                 "--", *command], check=False, close_fds=True)
        if result.returncode:
            return result.returncode
        subprocess.run([PYTHON, "-I", str(CODE / "validate_artifacts.py"),
                        '--operation', request['operation'], *input_args, "--parameters", str(parameters),
                        "--result", str(output / "science/result.json"),
                        "--archive", str(output / "science/simulation.tar"),
                        "--output", str(output / "semantic-validation.json")], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(run())
