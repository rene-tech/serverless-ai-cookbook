#!/usr/bin/env python3
"""Validate returned geometry/provenance and optionally compare a reference mask."""
import argparse
import json
from pathlib import Path

import nibabel as nib
import numpy as np

from monai_workflow.metadata import BUNDLE_REVISION, MODEL_ID, WEIGHTS_SHA256
from monai_workflow.runtime import digest, validate_mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--label", type=Path)
    parser.add_argument("--minimum-dice", type=float)
    args = parser.parse_args()
    result = json.loads((args.output_dir / "result.json").read_text())
    assert result["status"] == "succeeded" and result["model_id"] == MODEL_ID
    assert result["input_sha256"] == digest(args.input)
    assert result["bundle_revision"] == BUNDLE_REVISION
    assert result["bundle_files"]["models/model.pt"] == WEIGHTS_SHA256
    mask = args.output_dir / "segmentation.nii.gz"
    assert result["files"][mask.name] == {"sha256": digest(mask), "size_bytes": mask.stat().st_size}
    checked = validate_mask(args.input, mask, spatial_units=result["parameters"]["spatial_units"])
    assert result["validation"] == checked
    proof = {"geometry_preserved": True, "foreground_voxels": checked["foreground_voxels"]}
    if args.label:
        label = nib.load(args.label)
        predicted = nib.load(mask)
        assert label.shape == predicted.shape and np.allclose(label.affine, predicted.affine)
        left, right = np.asarray(predicted.dataobj) > 0, np.asarray(label.dataobj) > 0
        denominator = int(left.sum()) + int(right.sum())
        proof["dice"] = 1.0 if denominator == 0 else float(2 * np.count_nonzero(left & right) / denominator)
        proof["reference_foreground_voxels"] = int(right.sum())
        if args.minimum_dice is not None and proof["dice"] < args.minimum_dice:
            raise ValueError("Dice is below the predeclared qualification threshold")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
