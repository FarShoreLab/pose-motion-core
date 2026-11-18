import unittest

import numpy as np

from algorithms.tracking import (
    ConflictTracker, GalleryTargetPolicy, TargetPolicy,
    conflict_config, identity_config, offline_link,
)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.seed = [10., 20., 30., 60.]
        self.detections = [self.seed + [.95, 0]]

    def policy(self, version):
        cls = TargetPolicy if version == 'v1' else GalleryTargetPolicy
        return cls(identity_config(version), self.seed)

    def test_all_versions_require_the_caller_target(self):
        for version in ('v1', 'v2', 'v3'):
            with self.subTest(version=version):
                policy = self.policy(version)
                row = policy.step(0, self.detections, [[1, 0]], {0: 7})
                self.assertTrue(row['valid'])
                self.assertEqual(row['bbox_xyxy'], self.seed)
                with self.assertRaises(RuntimeError):
                    self.policy(version).step(
                        0, [[100, 100, 110, 140, .95, 0]], [[1, 0]], {0: 7})

    def test_persistent_numeric_id_does_not_accept_a_distractor(self):
        for version in ('v1', 'v2', 'v3'):
            with self.subTest(version=version):
                policy = self.policy(version)
                policy.step(0, self.detections, [[1, 0]], {0: 7})
                row = policy.step(1, self.detections, [[0, 1]], {0: 7})
                self.assertFalse(row['valid'])
                self.assertFalse(row['template_updated'])
                self.assertIsNone(row['bbox_xyxy'])

    def test_prediction_expires_and_never_becomes_an_observation(self):
        policy = self.policy('v3')
        policy.step(0, self.detections, [[1, 0]], {0: 7})
        for frame in range(1, 8):
            row = policy.step(frame, [], [], {})
            self.assertFalse(row['valid'])
            self.assertFalse(row['observed'])
            self.assertIsNone(row['bbox_xyxy'])
            self.assertEqual(row['display_bbox_xyxy'] is not None, frame <= 5)

    def test_recovery_requires_repeated_evidence(self):
        policy = self.policy('v3')
        policy.step(0, self.detections, [[1, 0]], {0: 7})
        policy.step(1, [], [], {})
        self.assertFalse(policy.step(2, self.detections, [[1, 0]], {0: 8})['valid'])
        self.assertTrue(policy.step(3, self.detections, [[1, 0]], {0: 8})['valid'])
        self.assertEqual(policy.template_updates, 0)


class ConflictTests(unittest.TestCase):
    seed = [10, 20, 30, 60]

    def tracker(self):
        return ConflictTracker(conflict_config(), self.seed)

    def step(self, tracker, frame):
        return tracker.step(
            frame, [[10 + frame, 20, 30 + frame, 60, .95, 0]], [[1., 0.]])

    def test_causal_prefix_and_offline_evidence_are_distinct(self):
        prefix, complete = self.tracker(), self.tracker()
        for frame in range(3):
            self.step(prefix, frame)
        for frame in range(6):
            row = self.step(complete, frame)
            self.assertEqual(row['future_frames_used'], 0)
            self.assertEqual(row['target_identity_status'], 'confirmed')
        for left, right in zip(prefix.records, complete.records):
            self.assertEqual(
                {k: v for k, v in left.items() if k != 'seconds'},
                {k: v for k, v in right.items() if k != 'seconds'})
        linked = offline_link(complete, conflict_config())
        self.assertEqual(linked['global_evidence_last_frame'], 5)
        self.assertEqual(linked['records'][0]['future_frames_used'], 5)
        self.assertEqual(linked['records'][0]['target_detection'], 0)

    def test_empty_frame_emits_no_target_observation(self):
        tracker = self.tracker()
        self.step(tracker, 0)
        row = tracker.step(1, np.empty((0, 6)), np.empty((0, 2)))
        self.assertEqual(row['target_geometry_status'], 'missing')
        self.assertIsNone(row['target_detection'])

    def test_policy_copies_do_not_share_mutable_state(self):
        left, right = conflict_config(), conflict_config()
        left['clear_anchor_frames'] = 99
        self.assertEqual(right['clear_anchor_frames'], 3)
        self.assertEqual(identity_config('v3')['gallery_similarity_min'], .65)


if __name__ == '__main__':
    unittest.main()
