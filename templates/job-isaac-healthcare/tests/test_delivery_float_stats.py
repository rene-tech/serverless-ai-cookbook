"""Cross-runtime camera statistics must not weaken scientific identity checks."""
import copy
import math
import unittest

from isaac_healthcare_runtime.audit import _recording_equal


class RecordingComparisonTests(unittest.TestCase):
    def setUp(self):
        self.reference = [{'samples': 75, 'task_success': True, 'cameras': {
            'sensor': {'frames': 75, 'sampled_standard_deviations': [53.384641071562065]}}}]

    def test_camera_reduction_roundoff(self):
        observed = copy.deepcopy(self.reference)
        observed[0]['cameras']['sensor']['sampled_standard_deviations'][0] = 53.38464107156206
        self.assertTrue(_recording_equal(self.reference, observed, ('episodes',)))

    def test_changes_beyond_roundoff_are_rejected(self):
        for value in (53.384642, float('nan'), float('inf')):
            with self.subTest(value=value):
                observed = copy.deepcopy(self.reference)
                observed[0]['cameras']['sensor']['sampled_standard_deviations'][0] = value
                self.assertFalse(_recording_equal(self.reference, observed, ('episodes',)))
        observed = copy.deepcopy(self.reference)
        value = observed[0]['cameras']['sensor']['sampled_standard_deviations'][0]
        observed[0]['cameras']['sensor']['sampled_standard_deviations'][0] += 9 * math.ulp(value)
        self.assertFalse(_recording_equal(self.reference, observed, ('episodes',)))

    def test_counts_outcomes_and_other_floats_remain_exact(self):
        for field, value in [('samples', 74), ('task_success', False)]:
            with self.subTest(field=field):
                observed = copy.deepcopy(self.reference)
                observed[0][field] = value
                self.assertFalse(_recording_equal(self.reference, observed, ('episodes',)))
        self.assertFalse(_recording_equal({'energy': 1.0}, {'energy': math.nextafter(1.0, 2.0)}))
        self.assertFalse(_recording_equal(self.reference, []))
        self.assertFalse(_recording_equal({'sha256': 'a'}, {'sha256': 'b'}))


if __name__ == '__main__':
    unittest.main()
