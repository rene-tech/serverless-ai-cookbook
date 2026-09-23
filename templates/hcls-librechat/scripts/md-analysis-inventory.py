#!/usr/bin/env python3
"""Inventory the separate CPU analysis environment; no simulation or API calls."""
import importlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys


EXPECTED = {
    "numpy": ("numpy", "1.26.4"),
    "scipy": ("scipy", "1.16.3"),
    "MDAnalysis": ("MDAnalysis", "2.10.0"),
    "ParmEd": ("parmed", "4.3.1"),
    "matplotlib": ("matplotlib", "3.10.7"),
    "Pillow": ("PIL", "12.3.0"),
    "netCDF4": ("netCDF4", "1.6.5"),
}


def inventory():
    versions = {}
    for distribution, (module, expected) in EXPECTED.items():
        importlib.import_module(module)
        actual = importlib.metadata.version(distribution)
        if actual != expected:
            raise RuntimeError(f"{distribution}: expected {expected}, found {actual}")
        versions[distribution] = actual
    programs = {}
    for name in ("ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        if not executable:
            raise RuntimeError(f"Required renderer program is missing: {name}")
        result = subprocess.run([executable, "-version"], check=True, capture_output=True, text=True)
        programs[name] = {"path": executable, "version": result.stdout.splitlines()[0]}
    return {
        "status": "passed", "scope": "dependency-imports-and-renderer-inventory-only",
        "interpreter": sys.executable, "python": platform.python_version(),
        "packages": versions, "programs": programs,
        "customer_ready": False, "scientific_correctness_assessed": False,
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, sort_keys=True))
