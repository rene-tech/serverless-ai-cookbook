"""Explicit project imports also work under Python's isolated (-I) mode."""

import os
import sys


def prepare_imports(context):
    os.environ["I4H_WORKFLOWS"] = context["effective_root"]
    os.environ["I4H_PROJECT_ROOT"] = context["project_dir"]
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    # Prepend only this invocation's verified directories; retain installed deps.
    sys.path[:0] = context["python_paths"]
    if context.get("asset_root"):
        os.environ["I4H_ASSET_PATH"] = context["asset_root"]
