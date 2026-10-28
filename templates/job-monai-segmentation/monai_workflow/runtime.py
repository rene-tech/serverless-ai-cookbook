"""Finite pretrained MONAI inference; identical portable and Scientific AI engine."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from .metadata import (
    BUNDLE, BUNDLE_REVISION, BUNDLE_VERSION, MODEL_ID, SOURCE, WEIGHTS_SHA256, parameters,
)


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b""):
            checksum.update(block)
    return checksum.hexdigest()


def verify_bundle(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("models/model.pt") != WEIGHTS_SHA256:
        raise ValueError("Installed MONAI checkpoint manifest differs; rebuild the pinned runtime")
    for name, expected in manifest.items():
        if digest(root / name) != expected:
            raise ValueError("Installed MONAI bundle failed its integrity check; rebuild the pinned runtime")
    metadata = json.loads((root / "configs/metadata.json").read_text())
    if metadata["version"] != BUNDLE_VERSION:
        raise ValueError("Installed MONAI bundle version differs; rebuild the pinned runtime")
    return manifest


def load_image(path, spatial_units):
    import nibabel as nib
    import numpy as np

    try:
        image = nib.load(path)
        if not isinstance(image, (nib.Nifti1Image, nib.Nifti2Image)) or len(image.shape) != 3:
            raise ValueError("Expected one 3D NIfTI CT volume; convert multi-frame data to one volume")
        array = image.get_fdata(dtype=np.float32)
    except (OSError, nib.filebasedimages.ImageFileError, EOFError) as error:
        raise ValueError("Cannot read the input NIfTI volume; upload a complete .nii or .nii.gz file") from error
    if not array.size or not np.isfinite(array).all():
        raise ValueError("CT voxels must be nonempty and finite; repair NaN or infinite intensities")
    affine = image.affine
    if not np.isfinite(affine).all() or abs(float(np.linalg.det(affine[:3, :3]))) <= 0:
        raise ValueError("NIfTI affine is singular or nonfinite; supply valid image geometry")
    units = image.header.get_xyzt_units()[0] if spatial_units == "header" else spatial_units
    if units not in {"mm", "meter", "micron"}:
        raise ValueError(
            "NIfTI spatial units are unspecified; set spatial_units to mm, meter or micron after verifying them"
        )
    factor = {"mm": 1.0, "meter": 1000.0, "micron": 0.001}[units]
    geometry = {
        "shape": list(image.shape), "affine": affine.tolist(),
        "spacing": list(map(float, nib.affines.voxel_sizes(affine))),
        "axis_codes": list(nib.aff2axcodes(affine)),
        "xyzt_units": list(image.header.get_xyzt_units()),
        "qform_code": int(image.header["qform_code"]),
        "sform_code": int(image.header["sform_code"]),
        "effective_spatial_units": units,
        "millimeters_per_coordinate_unit": factor,
    }
    return image, array, geometry


def validate_mask(input_path, mask_path, *, spatial_units="header"):
    import nibabel as nib
    import numpy as np

    original, _, geometry = load_image(input_path, spatial_units)
    try:
        mask = nib.load(mask_path)
        data = np.asarray(mask.dataobj)
    except (OSError, ValueError, nib.filebasedimages.ImageFileError) as error:
        raise ValueError("Segmentation output is not a readable NIfTI volume") from error
    if mask.shape != original.shape or not np.allclose(mask.affine, original.affine, atol=1e-5, rtol=1e-6):
        raise ValueError("Segmentation output does not preserve the input shape and affine")
    if mask.header.get_xyzt_units() != original.header.get_xyzt_units():
        raise ValueError("Segmentation output changed the input spatial or time units")
    for form in ("qform", "sform"):
        lhs, lc = getattr(original, "get_" + form)(coded=True)
        rhs, rc = getattr(mask, "get_" + form)(coded=True)
        if int(lc) != int(rc) or (lhs is not None and not np.allclose(lhs, rhs, atol=1e-5, rtol=1e-6)):
            raise ValueError("Segmentation output changed an input coordinate form")
    labels, counts = np.unique(data, return_counts=True)
    if not np.isfinite(data).all() or not set(labels.tolist()) <= {0, 1}:
        raise ValueError("Segmentation output contains noninteger or unknown spleen labels")
    foreground = int(np.count_nonzero(data))
    voxel_mm3 = abs(float(np.linalg.det(original.affine[:3, :3]))) * geometry["millimeters_per_coordinate_unit"]**3
    return {
        "geometry_preserved": True, "geometry": geometry,
        "labels": {str(int(k)): int(v) for k, v in zip(labels, counts)},
        "foreground_voxels": foreground, "foreground_volume_mm3": foreground * voxel_mm3,
    }


def run(input_path, output_dir, options=None, *, bundle_dir="/opt/monai/bundle", device="cuda"):
    import monai
    import nibabel as nib
    import numpy as np
    import torch
    from monai.bundle import ConfigParser
    from monai.inferers import sliding_window_inference

    started = time.monotonic()
    values = parameters({} if options is None else options)
    bundle_dir, output_dir, input_path = Path(bundle_dir), Path(output_dir), Path(input_path)
    manifest = verify_bundle(bundle_dir)
    if device not in {"cuda", "cpu"}:
        raise ValueError("Select cpu or cuda explicitly")
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA execution was requested but no CUDA device is available; assign a compatible GPU")
    if device == "cpu" and values["precision"] == "float16":
        raise ValueError("CPU float16 is not supported by this pipeline; select float32 or CUDA")
    if device == "cuda" and values["precision"] == "bfloat16" and not torch.cuda.is_bf16_supported():
        raise ValueError("The assigned GPU does not support bfloat16; select float32 or float16")
    torch.set_num_threads(int(os.environ.get("MONAI_CPU_THREADS", "8")))
    monai.utils.set_determinism(seed=123)
    original, array, geometry = load_image(input_path, values["spatial_units"])
    output_dir.mkdir(parents=True, exist_ok=True)
    if any((output_dir / name).exists() for name in ("segmentation.nii.gz", "result.json")):
        raise ValueError("Output files already exist; choose an unused per-run output directory")
    config = json.loads((bundle_dir / "configs/inference.json").read_text())
    config["bundle_root"] = str(bundle_dir)
    # Use the pinned bundle's exact preprocessing and inverse/argmax operations.
    # NIfTI writing is separate to preserve both coordinate forms and units.
    config["postprocessing"]["transforms"] = config["postprocessing"]["transforms"][:-1]
    parser = ConfigParser(config)
    preprocess = parser.get_parsed_content("preprocessing")
    postprocess = parser.get_parsed_content("postprocessing")
    network = parser.get_parsed_content("network_def")
    state = torch.load(bundle_dir / "models/model.pt", map_location="cpu", weights_only=True)
    network.load_state_dict(state, strict=True)
    network.to(device).eval()
    loaded = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="monai-input-") as temporary:
        mm_affine = original.affine.copy()
        mm_affine[:3, :] *= geometry["millimeters_per_coordinate_unit"]
        mm_image = nib.Nifti1Image(array, mm_affine)
        mm_image.header.set_xyzt_units("mm")
        normalized = Path(temporary) / "image.nii"
        nib.save(mm_image, normalized)
        item = preprocess({"image": str(normalized)})
        prepared = time.monotonic()
        precision = values["precision"]
        autocast = (torch.autocast(device, dtype=getattr(torch, precision))
                    if precision != "float32" else nullcontext())
        with torch.inference_mode(), autocast:
            # Stitch on host RAM: GPU memory follows patch batch, not entire volume.
            item["pred"] = sliding_window_inference(
                item["image"].unsqueeze(0), (96, 96, 96), values["sw_batch_size"], network,
                overlap=values["overlap"], sw_device=device, device="cpu", mode="constant",
            )[0].float()
        if device == "cuda":
            torch.cuda.synchronize()
        inferred = time.monotonic()
        restored = postprocess(item)["pred"].detach().cpu().numpy()[0]
    if tuple(restored.shape) != original.shape:
        raise ValueError("Inverse bundle transform did not recover the original NIfTI shape")
    header = original.header.copy()
    header.set_data_dtype(np.uint8)
    header.set_slope_inter(1, 0)
    output = original.__class__(restored.astype(np.uint8), original.affine, header=header)
    for form in ("qform", "sform"):
        matrix, code = getattr(original, "get_" + form)(coded=True)
        getattr(output, "set_" + form)(matrix, int(code))
    destination = output_dir / "segmentation.nii.gz"
    nib.save(output, destination)
    semantic = validate_mask(input_path, destination, spatial_units=values["spatial_units"])
    elapsed = time.monotonic() - started
    result = {
        "schema": "scientific-ai/monai-spleen-ct-result/v1", "status": "succeeded",
        "model_id": MODEL_ID, "operation": "segment", "input_sha256": digest(input_path),
        "source_revision": SOURCE, "bundle": BUNDLE, "bundle_version": BUNDLE_VERSION,
        "bundle_revision": BUNDLE_REVISION, "bundle_files": manifest, "parameters": values,
        "label_names": {"0": "background", "1": "spleen"},
        "validation": semantic,
        "files": {"segmentation.nii.gz": {"sha256": digest(destination), "size_bytes": destination.stat().st_size}},
        "runtime": {"monai": monai.__version__, "torch": torch.__version__, "device": device},
        "timings_s": {"load": loaded-started, "preprocess": prepared-loaded,
                      "inference": inferred-prepared, "total": elapsed},
        "runtime_metrics": {"volumes_completed": 1, "voxels_segmented": int(array.size), "compute_seconds": inferred-prepared},
        "intended_use": "Research example; the upstream bundle is not intended for diagnosis.",
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, default=Path("/opt/monai/bundle"))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--parameters-json", default="{}")
    args = parser.parse_args()
    try:
        result = run(args.input, args.output_dir, parameters(json.loads(args.parameters_json)),
                     bundle_dir=args.bundle_dir, device=args.device)
    except (ValueError, OSError, RuntimeError) as error:
        # Standard worker propagation retains this cause, step and actionable guidance.
        print(json.dumps({"status": "failed", "step": "MONAI segmentation", "message": str(error)}), flush=True)
        raise SystemExit(2) from None
    print(json.dumps({"status": result["status"], "volumes_completed": 1,
                      "foreground_voxels": result["validation"]["foreground_voxels"]}), flush=True)


if __name__ == "__main__":
    main()
