"""Check the bundled automatic-mask example after artifact SHA verification."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

import numpy as np
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("result", type=Path)
parser.add_argument("--input", type=Path, default=Path("automatic-example-input.tar.gz"))
args = parser.parse_args()
with tarfile.open(args.input, "r:gz") as archive:
    settings = json.load(archive.extractfile("settings.json"))
    raw = archive.extractfile(settings["media_path"]).read()
with Image.open(io.BytesIO(raw)) as image:
    rgb = np.asarray(image.convert("RGB"))
assert rgb.shape == (240, 320, 3), "This checker is for the bundled example only"
with zipfile.ZipFile(args.result) as archive:
    assert archive.testzip() is None
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["tool_version"] == "sam2.1-hiera-large-665f8e2a"
    assert manifest["mode"] == "automatic-image"
    assert manifest["input_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (manifest["height"], manifest["width"]) == rgb.shape[:2]
    assert manifest["automatic_options"] == settings["automatic_options"]
    assert manifest["native_postprocessing_executed"] is True
    annotations = json.loads(archive.read("automatic/annotations.json"))
    assert 0 < len(annotations) == manifest["native_mask_count"] <= 384
    mode = manifest["native_output_mode"]
    masks = []
    for annotation in annotations:
        segmentation = annotation["segmentation"]
        if mode == "binary_mask":
            with archive.open(segmentation["artifact"]) as stream:
                mask = np.load(stream, allow_pickle=False)
            assert mask.dtype == np.bool_
        else:
            from pycocotools import mask as coco
            assert segmentation["size"] == [240, 320]
            if mode == "uncompressed_rle":
                assert isinstance(segmentation["counts"], list)
                segmentation = coco.frPyObjects(segmentation, 240, 320)
            else:
                assert mode == "coco_rle" and isinstance(segmentation["counts"], str)
            mask = coco.decode(segmentation).astype(bool)
        assert mask.shape == (240, 320)
        assert int(mask.sum()) == annotation["area"]
        assert all(np.isfinite(annotation[name]).all() for name in
                   ("bbox", "predicted_iou", "stability_score", "crop_box", "point_coords"))
        masks.append(mask)
    with Image.open(io.BytesIO(archive.read("mask.png"))) as image:
        labels = np.asarray(image)
    assert labels.shape == (240, 320)
    assert set(np.unique(labels)) <= {0, *(item["object_id"] for item in manifest["objects"])}
matches = []
for color in ([54, 227, 196], [232, 113, 255], [255, 204, 72]):
    truth = np.all(rgb == color, axis=-1)
    score, index = max((float(np.logical_and(truth, mask).sum()) /
                        max(1, int(np.logical_or(truth, mask).sum())), i)
                       for i, mask in enumerate(masks))
    assert score >= 0.7, "A known colored object is missing from complete native masks"
    matches.append({"native_annotation_index": index, "visible_object_iou": score})
assert len({item["native_annotation_index"] for item in matches}) == 3
print(json.dumps({"status": "PASS_BUNDLED_SYNTHETIC_EXAMPLE", "native_masks": len(masks),
                  "output_mode": mode, "known_object_matches": matches}))
