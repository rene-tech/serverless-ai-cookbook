"""Run inside the exact built image; no random-weight model or network is used."""
import tempfile
from pathlib import Path
import unittest

import nibabel as nib
import numpy as np

from monai_workflow.runtime import load_image, validate_mask


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def image(self, name, data, units="mm", affine=None):
        affine = np.array([[-1.5, 0, 0, 35], [0, 2, 0, -61], [0, 0, 3, 5], [0, 0, 0, 1]]) if affine is None else affine
        image = nib.Nifti1Image(data, affine)
        image.header.set_xyzt_units(units, "sec")
        image.set_qform(affine, 1)
        image.set_sform(affine, 2)
        destination = self.root / name
        nib.save(image, destination)
        return destination

    def test_geometry_units_and_label_counts(self):
        original = self.image("original.nii.gz", np.zeros((9, 11, 13), dtype=np.float32))
        mask = np.zeros((9, 11, 13), dtype=np.uint8)
        mask[2:4, 3:5, 4:6] = 1
        destination = self.image("mask.nii.gz", mask)
        result = validate_mask(original, destination)
        self.assertEqual(result["foreground_voxels"], 8)
        self.assertAlmostEqual(result["foreground_volume_mm3"], 72)
        self.assertEqual(result["geometry"]["axis_codes"], ["L", "A", "S"])

    def test_meter_units_preserve_physical_volume(self):
        affine = np.diag([0.001, 0.002, 0.003, 1])
        original = self.image("meters.nii", np.zeros((3, 4, 5), dtype=np.float32), "meter", affine)
        mask = self.image("mask.nii", np.ones((3, 4, 5), dtype=np.uint8), "meter", affine)
        self.assertAlmostEqual(validate_mask(original, mask)["foreground_volume_mm3"], 360, places=3)

    def test_invalid_voxels_unknown_units_and_shifted_geometry(self):
        bad = np.zeros((4, 4, 4), dtype=np.float32)
        bad[0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            load_image(self.image("nan.nii", bad), "header")
        original = self.image("unknown.nii", np.zeros((4, 4, 4), dtype=np.float32), "unknown")
        with self.assertRaisesRegex(ValueError, "spatial units"):
            load_image(original, "header")
        load_image(original, "mm")
        mask = self.image("wrong.nii", np.zeros((4, 4, 4), dtype=np.uint8), "unknown", np.eye(4))
        with self.assertRaisesRegex(ValueError, "affine"):
            validate_mask(original, mask, spatial_units="mm")

    def test_reject_unknown_labels(self):
        original = self.image("original.nii", np.zeros((4, 4, 4), dtype=np.float32))
        mask = self.image("mask.nii", np.full((4, 4, 4), 2, dtype=np.uint8))
        with self.assertRaisesRegex(ValueError, "labels"):
            validate_mask(original, mask)


if __name__ == "__main__":
    unittest.main()
