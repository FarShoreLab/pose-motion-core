import json, math, unittest
from pathlib import Path
import numpy as np
from target_policy_v2 import GalleryTargetPolicy

class GalleryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.c=json.loads(Path(__file__).with_name('policy-v2.json').read_text())
        self.box=self.c['initialization']['seed_bbox_xyxy']
        self.d=np.array([self.box+[.95,0]])
        self.p=GalleryTargetPolicy(self.c)
        self.p.step(0,np.array([self.box+[.95,0],[400,150,450,300,.95,0]]),[[1,0,0],[0,1,0]],{0:2,1:1})
    def feature(self,angle):
        return [math.cos(math.radians(angle)),0,math.sin(math.radians(angle))]
    def test_pose_change_and_short_gap_do_not_create_anchor_deadlock(self):
        for f,angle in enumerate([20,40,60],1):
            self.assertTrue(self.p.step(f,self.d,[self.feature(angle)],{0:2})['valid'])
        self.p.step(4,[],[],{})
        self.assertFalse(self.p.step(5,self.d,[self.feature(60)],{0:2})['valid'])
        self.assertTrue(self.p.step(6,self.d,[self.feature(60)],{0:2})['valid'])
        np.testing.assert_array_equal(self.p.anchor,[1,0,0])
    def test_same_id_distractor_rejected_after_gallery_growth(self):
        self.p.step(1,self.d,[self.feature(20)],{0:2})
        r=self.p.step(2,self.d,[[0,1,0]],{0:2})
        self.assertFalse(r['valid'])
        self.assertFalse(r['template_updated'])
    def test_overlap_quarantines_observation_and_freezes_gallery(self):
        r=self.p.step(1,np.array([self.box+[.95,0],self.box+[.95,0]]),[[1,0,0],[0,1,0]],{0:2,1:1})
        self.assertFalse(r['valid'])
        self.assertEqual(r['state'],'ambiguous')
        self.assertEqual(self.p.template_updates,0)
    def test_prediction_expiry_does_not_create_valid_boxes(self):
        for f in range(1,9):
            r=self.p.step(f,[],[],{})
            self.assertFalse(r['valid'])
            self.assertIsNone(r['bbox_xyxy'])
            self.assertEqual(r['display_bbox_xyxy'] is not None,f<=5)

class GalleryV3Tests(GalleryPolicyTests):
    def setUp(self):
        super().setUp()
        self.c=json.loads(Path(__file__).with_name('policy-v3.json').read_text())
        self.p=GalleryTargetPolicy(self.c)
        self.p.step(0,np.array([self.box+[.95,0],[400,150,450,300,.95,0]]),[[1,0,0],[0,1,0]],{0:2,1:1})

if __name__=='__main__': unittest.main()
