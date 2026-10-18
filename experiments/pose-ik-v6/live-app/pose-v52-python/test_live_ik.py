"""Synthetic stage contract tests only. These are not live timing/accuracy results."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from live_ik import LiveIK, HumanIK
from opensim_ik import KEYS, mp_points

class LiveIKContractTests(unittest.TestCase):
    def test_exact_frame_calibration_raw_integrity_and_loss(self):
        truth = HumanIK()
        full = [{'x':0.0,'y':0.0,'z':0.0,'visibility':.95,'presence':.95} for _ in range(33)]
        for i,p in zip(KEYS,mp_points(truth.fk())):
            full[i].update(p)
        landmarks = [{'x':.5,'y':.5,'z':0.,'visibility':.95,'presence':.95} for _ in range(33)]
        with tempfile.TemporaryDirectory() as temp:
            pipeline = LiveIK(Path(temp))
            def submit(frame,epoch='session:1',states=None):
                raw={'frame_id':frame,'epoch':epoch,'source_pts_ms':float(frame*40),'input_sha256':str(frame),'landmarks':[copy.deepcopy(landmarks)],'world_landmarks':[copy.deepcopy(full)]}
                original=copy.deepcopy(raw)
                pipeline.remember_raw(raw)
                body={'frame_id':frame,'epoch':epoch,'source_pts_ms':float(frame*40),'source_unwrapped_pts_ms':float(frame*40),'clip':'unit-synthetic','observation_states':states or ['measured']*33}
                out=pipeline.fit(body)
                self.assertEqual(raw,original)
                return out,body
            for i in range(1,31):
                out,body=submit(i)
                self.assertEqual(out['status'],'calibrating')
                self.assertEqual(out['calibration_count'],i)
                self.assertTrue(all(x is None for x in out['world']))
                self.assertEqual(out['new_measurement'],False)
            lengths=copy.deepcopy(pipeline.model.lengths)
            self.assertEqual(len(out['calibration']['frames']),30)
            out,body=submit(31)
            self.assertEqual(out['status'],'fit')
            self.assertEqual(out['frame_id'],31)
            self.assertTrue(all(out['states'][i]=='fitted' for i in KEYS))
            with self.assertRaises(ValueError):pipeline.fit(body)
            out,body=submit(32,epoch='session:2')
            self.assertEqual(pipeline.model.lengths,lengths)
            self.assertEqual(out['calibration_count'],30)
            self.assertEqual(out['calibration'],None)
            states=['measured']*33;states[13]='lost'
            out,body=submit(33,epoch='session:2',states=states)
            self.assertEqual(out['states'][13],'inferred_unobserved')
            self.assertEqual(out['observation_states'][13],'lost')
            self.assertFalse(out['effective_observed_mask'][13])
            out,body=submit(34,epoch='session:2',states=['lost']*33)
            self.assertEqual(out['status'],'no_observation')
            self.assertTrue(all(x is None for x in out['world']))
            with self.assertRaises(ValueError):pipeline.fit({**body,'frame_id':999})
            pipeline.close()
            audit=[json.loads(l) for l in pipeline.audit_path.read_text().splitlines()]
            self.assertEqual(len(audit),68)
            self.assertEqual(sum(r['kind']=='raw_mediapipe_output' for r in audit),34)
            self.assertTrue(all(len(r['data']['world_landmarks'][0])==33 for r in audit if r['kind']=='raw_mediapipe_output'))

if __name__=='__main__':unittest.main()
