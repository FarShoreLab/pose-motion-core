import unittest
import numpy as np
from association import partial_assignments,joint_assignment

class JointAssignmentTests(unittest.TestCase):
    def test_swap_not_left_right(self):
        result=joint_assignment([[.8,.1],[.1,.8]],.35)
        self.assertEqual(result['best']['pairs'],[[0,1],[1,0]])
        self.assertGreater(result['global_gap'],.1)
    def test_unmatched_birth_death(self):
        result=joint_assignment([[.1,.9,.9],[.9,.95,.95]],.35)
        self.assertEqual(result['best']['pairs'],[[0,0]])
        self.assertEqual(result['best']['unmatched_before'],[1])
        self.assertEqual(result['best']['unmatched_after'],[1,2])
    def test_empty_future_no_fake_observation(self):
        result=joint_assignment(np.empty((2,0)),.35)
        self.assertEqual(result['best']['pairs'],[])
        self.assertIsNone(result['global_gap'])
    def test_global_tie_stays_ambiguous(self):
        result=joint_assignment([[.1,.1],[.1,.1]],.35)
        self.assertAlmostEqual(result['global_gap'],0)
    def test_unrelated_ambiguity_does_not_prove_all_edges(self):
        result=joint_assignment([[.1,.9,.9],[.9,.1,.1],[.9,.1,.1]],.35)
        self.assertAlmostEqual(result['global_gap'],0)
        certainty={tuple(r['pair']):r['global_exclusion_gap'] for r in result['pair_certainty']}
        self.assertGreater(certainty[(0,0)],.1)
    def test_against_exhaustive_partial_matching(self):
        rng=np.random.default_rng(42)
        for n,m in [(0,0),(0,3),(3,0),(2,3),(3,2),(3,3),(4,4)]:
            for _ in range(5):
                costs=rng.random((n,m));all_=partial_assignments(costs,.35);result=joint_assignment(costs,.35)
                self.assertAlmostEqual(result['best']['cost'],all_[0]['cost'])
                if len(all_)>1:self.assertAlmostEqual(result['second_best']['cost'],all_[1]['cost'])

if __name__=='__main__':unittest.main()
