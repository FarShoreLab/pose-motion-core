import json
from pathlib import Path
import unittest
import numpy as np
from target_policy import TargetPolicy


class IdentityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path(__file__).with_name('policy-v1.json').read_text())
        self.box = self.config['initialization']['seed_bbox_xyxy']
        self.other = [400, 150, 450, 300]
        self.red, self.blue = np.array([1., 0., 0.]), np.array([0., 1., 0.])
        self.det = np.array([self.box + [.9, 0], self.other + [.9, 0]])
        self.policy = TargetPolicy(self.config)
        self.policy.step(0, self.det, [self.red, self.blue], {0: 2, 1: 1})

    def test_same_numeric_id_cannot_replace_identity(self):
        row = self.policy.step(1, self.det[:1], [self.blue], {0: 2})
        self.assertFalse(row['valid'])
        self.assertIn('immutable_anchor_mismatch', row['candidates'][0]['reasons'])
        self.assertEqual(self.policy.template_updates, 0)

    def test_bounded_prediction_remains_invalid_and_expires(self):
        for frame in range(1, 8):
            row = self.policy.step(frame, [], [], {})
            self.assertFalse(row['valid'])
            self.assertIsNone(row['bbox_xyxy'])
            self.assertEqual(row['display_bbox_xyxy'] is not None, frame <= 5)

    def test_reacquisition_requires_two_observations(self):
        self.policy.step(1, [], [], {})
        first = self.policy.step(2, self.det[:1], [self.red], {0: 9})
        second = self.policy.step(3, self.det[:1], [self.red], {0: 9})
        self.assertFalse(first['valid'])
        self.assertTrue(second['valid'])
        self.assertEqual(second['state'], 'reacquired')
        self.assertEqual(second['track_id'], 9)

    def test_overlap_prevents_template_update(self):
        for frame in range(1, 10):
            self.policy.step(frame, self.det, [self.red, self.blue], {0: 2, 1: 1})
        det = np.array([self.box + [.95, 0], self.box + [.95, 0]])
        row = self.policy.step(10, det, [self.red, self.blue], {0: 2, 1: 1})
        self.assertTrue(row['valid'])
        self.assertFalse(row['template_updated'])
        self.assertFalse(self.policy.anchor.flags.writeable)
        np.testing.assert_array_equal(self.policy.anchor, self.red)

    def test_wrong_initial_box_is_not_auto_replaced(self):
        p = TargetPolicy(self.config)
        with self.assertRaises(RuntimeError):
            p.step(0, np.array([self.other + [.9, 0]]), [self.blue], {0: 1})


if __name__ == '__main__':
    unittest.main()
