import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('epoch_clock', Path(__file__).resolve().parents[1] / 'epoch_clock.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EpochClockTests(unittest.TestCase):
    def test_warm_epoch_keeps_model_time_monotonic_and_rejects_duplicate_source(self):
        clock = module.EpochClock('warm')
        clock.prepare('session:1')
        first = clock.map(120, 25)
        clock.commit(120, first['model_timestamp_ms'])
        with self.assertRaises(ValueError):
            clock.map(120, 25)
        clock.prepare('session:2')
        second = clock.map(0, 25)
        self.assertEqual(second['model_timestamp_ms'], 160)
        self.assertEqual(second['epoch_source_pts_start_ms'], 0)

    def test_cold_epoch_resets_model_time(self):
        clock = module.EpochClock('cold')
        clock.prepare('session:1')
        first = clock.map(120, 25)
        clock.commit(120, first['model_timestamp_ms'])
        clock.prepare('session:2')
        self.assertEqual(clock.map(0, 25)['model_timestamp_ms'], 0)


if __name__ == '__main__':
    unittest.main()
