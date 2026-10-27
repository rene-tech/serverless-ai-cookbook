"""CPU discovery and lint against the actual merged upstream registry."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .bootstrap import prepare_imports
from .arguments import merge_workflow_arguments
from .contract import digest, json_loads


def resolve(values):
    from i4h_arena.cli import _build, build_parser
    from i4h_engine.loader import load_workflow_module, resolve_workflow

    argv = ["--workflow", values["workflow"]]
    for name, flag in (("mode", "--mode"), ("dataset", "--dataset")):
        if values.get(name) is not None:
            argv.extend([flag, str(values[name])])
    argv.extend(["--episode", ",".join(map(str, values["replay_episodes"])),
                 "--idle-seconds", str(values["idle_seconds"])])
    args = build_parser().parse_args(argv)
    args.mode = args.mode or load_workflow_module(values['workflow']).default_mode

    def authored(name, mode, **kwargs):
        supplied = values.get("workflow_args", {})
        return resolve_workflow(name, mode, **merge_workflow_arguments(kwargs, supplied))

    return _build(args, authored)


def source_inventory(root):
    import sys

    result = {}
    # The source imported during graph construction is precisely the effective
    # implementation, including authored code, not an example-file allowlist.
    for name, module in tuple(sys.modules.items()):
        source = getattr(module, "__file__", None)
        if source is None:
            continue
        path = Path(source)
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if path.is_file():
            result[relative.as_posix()] = {"sha256": digest(path), "size_bytes": path.stat().st_size}
    return result


def inspect_context(context, values):
    prepare_imports(context)
    from i4h_engine.loader import available_workflows, load_workflow_module
    from i4h_engine.lint import lint_workflow
    from i4h_engine.registry import default_registry

    registry = default_registry()
    catalog = []
    for name in available_workflows():
        try:
            authored = load_workflow_module(name)
            catalog.append({"workflow": name, "scene": authored.scene,
                            "modes": sorted(authored.modes), "default_mode": authored.default_mode})
        except Exception as error:
            catalog.append({"workflow": name, "error": {"type": type(error).__name__, "message": str(error)}})
    report = {"workflows": catalog, "registry_errors": list(registry.errors),
              "tasks": [{"id": task.id, "runtime": task.runtime, "trainable": task.trainable,
                         "backend": asdict(task.backend) if task.backend else None}
                        for task in registry.tasks.values()],
              "selected": None}
    if values["workflow"] is not None:
        workflow = resolve(values)
        workflows = [workflow]
        if workflow.mode == 'replay':
            workflows.extend(resolve({**values, 'mode': 'replay', 'replay_episodes': [index]})
                             for index in values['replay_episodes'][1:])
        lint_reports = [lint_workflow(item, registry) for item in workflows]
        graph_nodes = [node for item in workflows for node in item.graph.nodes]
        scene = registry.scene(workflow.scene).for_mode(workflow.mode)
        if values["episode_steps"] is not None and values["episode_steps"] > scene.max_steps:
            raise ValueError(f"episode_steps exceeds the authored scene/mode cap {scene.max_steps}")
        backends = {}
        for node in graph_nodes:
            spec = node.spec or registry.tasks.get(node.task_id)
            if spec is not None and spec.runtime == "remote" and spec.backend is not None:
                key = (spec.backend.project, spec.backend.entry)
                python = Path(context["effective_root"]) / spec.backend.project / ".venv/bin/python"
                backends.setdefault(key, {**asdict(spec.backend), "preload": spec.id,
                                           "environment_present": python.is_file()})
        import sys

        source_files = {}
        authored = load_workflow_module(workflow.name)
        candidates = [Path(authored.module.__file__), scene.source]
        controller_modules = []
        for node in graph_nodes:
            spec = node.spec or registry.tasks.get(node.task_id)
            module_name = (spec.impl.split(":", 1)[0] if spec is not None and spec.impl
                           else type(node.ref).__module__ if not isinstance(node.ref, str) else None)
            if module_name is not None:
                controller_modules.append(module_name)
                module = sys.modules.get(module_name)
                if module is not None and getattr(module, "__file__", None):
                    candidates.append(Path(module.__file__))
        # Scene implementations are resolved as source files without importing
        # Isaac on this CPU-only path.
        scene_module = scene.impl.split(":", 1)[0]
        for source_root in context["python_paths"]:
            candidate = Path(source_root).joinpath(*scene_module.split(".")).with_suffix(".py")
            if candidate.is_file():
                candidates.append(candidate)
                break
        for path in candidates:
            if path is None or not path.is_file():
                continue
            for prefix, origin in ((Path(context["effective_root"]), "sdk"), (Path(context["project_dir"]), "project")):
                try:
                    name = origin + "/" + path.relative_to(prefix).as_posix()
                except ValueError:
                    continue
                source_files[name] = {"sha256": digest(path), "size_bytes": path.stat().st_size}
                break
        report["selected"] = {
            "workflow": workflow.name, "mode": workflow.mode, "scene": scene.name,
            "scene_step_cap": scene.max_steps, "episode_step_cap": values["episode_steps"] or scene.max_steps,
            "control_hz": scene.control_hz, "action_space": scene.action_space,
            "dof": scene.dof, "cameras": list(scene.cameras) if values["cameras"] else [],
            "declared_cameras": list(scene.cameras), "envs": values["envs"],
            "recorded_environment": 0, "physics_requested": values["physics"],
            "lint": {"ok": all(item.ok for item in lint_reports),
                     "issues": [asdict(issue) for item in lint_reports for issue in item.issues]},
            "replay_source_episodes": list(values['replay_episodes']) if workflow.mode == 'replay' else [],
            "backends": list(backends.values()),
            "controller_modules": sorted(set(controller_modules)), "sources": source_files,
        }
    report["sources"] = source_inventory(Path(context["effective_root"]))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = json_loads(args.context.read_bytes())
    result = inspect_context(value["project"], value["parameters"])
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
