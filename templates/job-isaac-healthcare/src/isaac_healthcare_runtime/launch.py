"""Load the invocation's project, then call upstream's unchanged Arena CLI."""

import os
import sys
from pathlib import Path

from .bootstrap import prepare_imports
from .contract import json_loads


def localize_constants(constants, *, base_root=Path('/opt/i4h-assets/v0.9.0-7cf86a1'), explicit_root=None):
    """Use audited source-URL provenance, including non-Healthcare assets.

    A supplied project asset root owns the Healthcare-relative tree. Its own
    manifest can also override any source URL; otherwise independent IsaacLab
    assets continue to use the pinned image closure. Missing project files do
    not silently fall back to a different geometry.
    """
    mapping = {}
    project_mapping = {}
    roots = [base_root]
    if explicit_root is not None and Path(explicit_root) != base_root:
        roots.append(Path(explicit_root))
    for root in roots:
        manifest = root / 'manifest.json'
        if not manifest.is_file():
            continue
        value = json_loads(manifest.read_bytes())
        for row in value.get('files', []):
            if row.get('source_url'):
                from .project import relative_path
                target = str(root.joinpath(*relative_path(row['path']).parts))
                mapping[row['source_url']] = target
                if explicit_root is not None and root == Path(explicit_root):
                    project_mapping[row['source_url']] = target
    original_root = constants.ASSET_PATH
    local_root = str(explicit_root or base_root).rstrip('/') + '/'
    for name, value in tuple(vars(constants).items()):
        if not isinstance(value, str):
            continue
        if value in project_mapping:
            replacement = project_mapping[value]
        elif explicit_root is not None and value.startswith(original_root):
            replacement = local_root + value.removeprefix(original_root)
        elif value in mapping:
            replacement = mapping[value]
        elif value.startswith(original_root):
            replacement = local_root + value.removeprefix(original_root)
        else:
            continue
        setattr(constants, name, replacement)


def main():
    arguments = list(sys.argv[1:])
    if "--context" in arguments:
        index = arguments.index("--context")
        context = json_loads(Path(arguments[index + 1]).read_bytes())
        del arguments[index:index + 2]
        prepare_imports(context["project"])
    else:
        context = {"parameters": {}}
    from i4h_arena.assets import constants
    from i4h_engine import loader
    from i4h_arena import cli

    localize_constants(constants, explicit_root=os.environ.get('I4H_ASSET_PATH'))
    supplied = context["parameters"].get("workflow_args", {})
    if supplied:
        original_resolve = loader.resolve_workflow

        def resolve(name, mode=None, **kwargs):
            from .arguments import merge_workflow_arguments
            return original_resolve(name, mode, **merge_workflow_arguments(kwargs, supplied))

        loader.resolve_workflow = resolve
    # Keep upstream scientific arguments intact while using SimulationApp's
    # supported portable-root option for writable per-scenario Kit state.
    workflow_args = arguments
    kit_arguments = context.get("kit_arguments", [])
    if not isinstance(kit_arguments, list) or not all(isinstance(value, str) for value in kit_arguments):
        raise ValueError("Operator Kit arguments must be a list of strings")
    sys.argv = [sys.argv[0], *kit_arguments]
    if kit_root := os.environ.get("ISAAC_HEALTHCARE_KIT_ROOT"):
        sys.argv.extend(["--portable-root", kit_root])
    from .replay import install_sequence
    install_sequence(cli)
    return cli.main(workflow_args)


if __name__ == "__main__":
    sys.exit(main())
