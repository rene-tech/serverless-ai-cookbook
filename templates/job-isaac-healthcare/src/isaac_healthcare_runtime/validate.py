"""Validate scene-shaped upstream recordings; task outcome remains upstream data."""

from pathlib import Path

import h5py
import numpy as np
from PIL import Image

from .contract import digest


def _text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def validate_hdf_closure(source):
    """Prove recording data stays in this file before reading attrs or values.

    Enumerating a group's direct links with getlink=True does not follow soft
    or external links. Only hard-linked object metadata is opened in the first
    pass. Object addresses make hard-link aliases/cycles finite; a separate
    iterative resolver handles internal soft links without asking HDF5 to
    dereference an unchecked path. Virtual datasets must have same-file sources
    and an acyclic dependency graph. No external payload is opened to check it.
    """
    def address(obj):
        return h5py.h5o.get_info(obj.id).addr

    root = address(source)
    objects, links, soft, virtual = {root: source}, {}, {}, {}
    pending = [root]
    while pending:
        key = pending.pop()
        obj = objects[key]
        if isinstance(obj, h5py.Dataset):
            if obj.id.get_create_plist().get_external_count():
                raise ValueError('Recording uses external raw dataset storage')
            if obj.is_virtual:
                sources = obj.virtual_sources()
                filename = Path(source.filename).absolute()
                for item in sources:
                    reference = _text(item.file_name)
                    # h5py normally rewrites a same-file source to '.'. Also
                    # accept its exact absolute name; no
                    # filesystem lookup or path traversal establishes identity.
                    if reference not in ('.', str(filename)):
                        raise ValueError('Recording virtual dataset references an external file')
                virtual[key] = [_text(item.dset_name) for item in sources]
            continue
        if not isinstance(obj, h5py.Group):
            continue  # A committed datatype is metadata in this same file.
        links[key] = {}
        for name in obj:
            link = obj.get(name, getlink=True)
            if isinstance(link, h5py.ExternalLink):
                raise ValueError('Recording contains an external HDF5 link')
            if isinstance(link, h5py.SoftLink):
                token = (key, name)
                soft[token] = link.path
                links[key][name] = ('soft', token)
            elif isinstance(link, h5py.HardLink):
                child = obj[name]  # Metadata-only open of a proven same-file hard link.
                child_key = address(child)
                links[key][name] = ('hard', child_key)
                if child_key not in objects:
                    objects[child_key] = child
                    pending.append(child_key)
            else:
                raise ValueError('Recording contains an unsupported HDF5 link type')

    resolved = {}

    def frame(path, parent, token=None):
        if not isinstance(path, str) or not path:
            raise ValueError('Recording contains an empty internal HDF5 path')
        # HDF5 reserves '.', not '..'; do not apply filesystem parent traversal
        # normalization to its object namespace.
        return [root if path.startswith('/') else parent,
                [part for part in path.split('/') if part and part != '.'], 0, token]

    def resolve(path, parent):
        stack, active = [frame(path, parent)], set()
        while stack:
            current, parts, position, token = stack[-1]
            if position == len(parts):
                stack.pop()
                if token is not None:
                    resolved[token] = current
                    active.remove(token)
                if not stack:
                    return current
                continue
            edge = links.get(current, {}).get(parts[position])
            if edge is None:
                raise ValueError('Recording contains a dangling internal HDF5 path')
            kind, target = edge
            if kind == 'hard' or target in resolved:
                stack[-1][0] = target if kind == 'hard' else resolved[target]
                stack[-1][2] += 1
            else:
                if target in active:
                    raise ValueError('Recording contains a cyclic soft-link dependency')
                active.add(target)
                stack.append(frame(soft[target], target[0], target))

    for token, path in soft.items():
        if token not in resolved:
            resolved[token] = resolve(path, token[0])
    dependencies = {}
    for key, paths in virtual.items():
        dependencies[key] = []
        for path in paths:
            target = resolve(path, root)
            if not isinstance(objects[target], h5py.Dataset):
                raise ValueError('Recording virtual source is not a dataset')
            dependencies[key].append(target)
    done = set()
    for start in dependencies:
        if start in done:
            continue
        active, stack = {start}, [(start, iter(dependencies[start]))]
        while stack:
            key, children = stack[-1]
            target = next(children, None)
            if target is None:
                done.add(key)
                active.remove(key)
                stack.pop()
            elif target in active:
                raise ValueError('Recording contains a cyclic virtual-dataset dependency')
            elif target in dependencies and target not in done:
                active.add(target)
                stack.append((target, iter(dependencies[target])))
    return {'objects': len(objects), 'soft_links': len(soft), 'virtual_datasets': len(virtual)}


def _finite(dataset, *, allow_missing=False):
    missing = 0
    for start in range(0, dataset.shape[0], 64):
        values = dataset[start:start + 64]
        if np.issubdtype(values.dtype, np.number):
            missing += int(np.count_nonzero(~np.isfinite(values)))
    if missing and not allow_missing:
        raise ValueError(f"Recording {dataset.name} contains nonfinite values")
    return missing


def validate_recording(path, values, previews=None, *, scene=None):
    """No workflow, joint count, image resolution or sensor name is built in.

    SceneSpec describes camera names and episode limits. Recorded arrays define
    action/joint dimensions: these need not equal each other for pose/IK tasks.
    Upstream diagnostics can contain NaN for measurements absent at some steps;
    their missing-value counts are retained rather than interpreted as physics.
    """
    scene = scene or {}
    records = []
    with h5py.File(path, "r") as source:
        validate_hdf_closure(source)
        data = source["data"]
        for key in ("workflow", "mode"):
            expected = scene.get(key) or values.get(key)
            if expected is not None and _text(data.attrs.get(key, "")) != expected:
                raise ValueError(f"Recording belongs to a different {key}")
        if scene.get("scene") and _text(data.attrs.get("scene", "")) != scene["scene"]:
            raise ValueError("Recording belongs to a different scene")
        for name in sorted(data):
            if not name.startswith("demo_"):
                raise ValueError("Recording contains an unfinished attempt")
            demo = data[name]
            recorded = demo.attrs.get("num_samples")
            steps = int(recorded) if recorded is not None else None
            cap = values.get("episode_steps") or scene.get("episode_step_cap")
            reason = None
            if steps is None:
                reason = "has no recorded sample count"
            elif steps < 1:
                reason = "is empty"
            elif cap is not None and steps > cap:
                reason = "exceeds the requested scene cap"
            if reason:
                raise ValueError(
                    f"Recording {reason}: episode={name!r}, samples={steps}, cap={cap!r}, "
                    f"workflow={_text(data.attrs.get('workflow', ''))!r}, "
                    f"mode={_text(data.attrs.get('mode', ''))!r}, scene={_text(data.attrs.get('scene', ''))!r}"
                )
            if int(demo.attrs.get("recording_version", 0)) != 1:
                raise ValueError("Recording lacks the upstream v1 termination/reset boundary")
            shapes = {}
            for field in ("actions", "obs/joint_pos"):
                array = demo[field]
                if array.ndim < 2 or array.shape[0] != steps:
                    raise ValueError(f"Recording {field} trajectory does not align with its samples")
                _finite(array)
                shapes[field] = list(array.shape)
            if "initial_state" not in demo or "segments" not in demo:
                raise ValueError("Recording omits replay initial state or workflow task segmentation")
            segments = demo["segments"][()]
            for row in segments:
                if not 0 <= int(row["start"]) <= int(row["end"]) <= steps:
                    raise ValueError("Workflow segment lies outside its recording")
            expected_cameras = scene.get("cameras")
            declared = scene.get("declared_cameras", expected_cameras or [])
            if not values["cameras"] and any(camera in demo["obs"] for camera in declared):
                raise ValueError("Recording contains images although cameras were disabled")
            if values["cameras"] and expected_cameras is not None:
                missing = set(expected_cameras) - set(demo["obs"])
                if missing:
                    raise ValueError(f"Recording omits declared scene sensors: {sorted(missing)}")
            sensors = {}
            for camera, frames in demo["obs"].items():
                if camera == "joint_pos":
                    continue
                if not isinstance(frames, h5py.Dataset) or frames.ndim < 1 or frames.shape[0] != steps:
                    raise ValueError(f"Sensor {camera} sample count differs from its trajectory")
                _finite(frames)
                indices = sorted({0, steps // 2, steps - 1})
                sensors[camera] = {"frames": steps, "shape": list(frames.shape[1:]),
                                   "dtype": str(frames.dtype),
                                   "sampled_standard_deviations": [float(frames[index].std()) for index in indices]}
                if frames.ndim >= 3:
                    sensors[camera].update(height=int(frames.shape[1]), width=int(frames.shape[2]))
                if previews is not None and frames.dtype == np.uint8 and frames.ndim == 4 and frames.shape[-1] in (3, 4):
                    previews.mkdir(parents=True, exist_ok=True)
                    # Dataset names are never filesystem paths.
                    import hashlib
                    label = hashlib.sha256(camera.encode()).hexdigest()[:12]
                    for index in indices:
                        Image.fromarray(frames[index]).save(previews / f"{name}-sensor-{label}-{index:06d}.png")
            diagnostics = {}
            if "diagnostics" in demo:
                for field, values_array in demo["diagnostics"].items():
                    if values_array.shape[0] != steps:
                        raise ValueError(f"Diagnostic {field} does not align with its samples")
                    diagnostics[field] = {"shape": list(values_array.shape),
                                          "nonfinite_values": _finite(values_array, allow_missing=True)}
            if "success" not in demo.attrs or "status" not in demo.attrs:
                raise ValueError("Recording omits upstream task outcome")
            records.append({"demo": name, "samples": steps,
                            "task_success": bool(demo.attrs["success"]),
                            "status": _text(demo.attrs["status"]),
                            "shapes": shapes, "cameras": sensors, "diagnostics": diagnostics,
                            "segments": len(segments)})
    successful = sum(row["task_success"] for row in records)
    if successful > values["episodes"] or len(records) > values["episodes"] * values["attempts"]:
        raise ValueError("Recording episode counts exceed the requested scientific workload")
    return {"sha256": digest(Path(path)), "size_bytes": Path(path).stat().st_size,
            "episodes": records, "successful_episodes": successful,
            "requested_episodes": values["episodes"],
            "task_complete": successful == values["episodes"],
            "samples": sum(row["samples"] for row in records)}
