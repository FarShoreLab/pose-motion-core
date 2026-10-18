import unittest
from epoch_clock import EpochClock

class EpochClockTests(unittest.TestCase):
    def advance(self, clock, source, fps):
        mapped=clock.map(source,fps)
        self.assertEqual(mapped['model_timestamp_ms'],mapped['source_pts_rounded_ms']+mapped['model_epoch_offset_ms'])
        clock.commit(source,mapped['model_timestamp_ms'])
        return mapped

    def test_cold_resets_clock_on_new_epoch(self):
        c=EpochClock('cold');c.prepare('a')
        self.assertEqual(self.advance(c,12600,5)['model_timestamp_ms'],12600)
        c.prepare('b')
        self.assertEqual(self.advance(c,0,5)['model_timestamp_ms'],0)

    def test_warm_loop_keeps_monotonic_model_clock(self):
        c=EpochClock('warm');c.prepare('a')
        self.advance(c,12600,5);self.advance(c,12800,5);c.prepare('b')
        x=self.advance(c,0,5)
        self.assertEqual(x['model_timestamp_ms'],13000)
        self.assertEqual(x['model_epoch_offset_ms'],13000)
        self.assertEqual(self.advance(c,200,5)['model_timestamp_ms'],13200)

    def test_new_source_fps_and_nonzero_pts(self):
        c=EpochClock('warm');c.prepare('a');self.advance(c,5000,5);c.prepare('b')
        x=self.advance(c,1234.567,60000/1001)
        self.assertEqual(x['model_timestamp_ms'],5017)
        self.assertEqual(x['epoch_source_pts_start_ms'],1234.567)
        self.assertEqual(self.advance(c,1251.25,60000/1001)['model_timestamp_ms'],5033)

    def test_duplicate_source_rejected(self):
        c=EpochClock('warm');c.prepare('a');self.advance(c,100,30)
        with self.assertRaises(ValueError):c.map(100,30)
        with self.assertRaises(ValueError):c.map(99,30)

    def test_prepare_same_epoch_does_not_reset(self):
        c=EpochClock('warm');c.prepare('a');self.advance(c,1000,30)
        self.assertFalse(c.prepare('a'))
        with self.assertRaises(ValueError):c.map(0,30)

    def test_failed_inference_not_committed(self):
        c=EpochClock('warm');c.prepare('a')
        self.assertEqual(c.map(500,30),c.map(500,30))
        self.assertEqual(c.last_model_ms,-1)

    def test_rounded_collision_rejected(self):
        c=EpochClock('warm');c.prepare('a');self.advance(c,100.01,240)
        with self.assertRaises(ValueError):c.map(100.02,240)

if __name__=='__main__':unittest.main()
