import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model


def recording(power, start=0):
    return {'rows': [[i+start, p, None, 85, 5] for i, p in enumerate(power)]}


def meta(indoor=False):
    return {'id': 'synthetic', 'type': 'VirtualRide' if indoor else 'Ride', 'duration_minutes': 30}


class ModelTests(unittest.TestCase):
    def test_actual_watts_never_scaled_by_environment(self):
        r = recording([140]*1200)
        a, b = model.analyze(meta(True), r), model.analyze(meta(False), r)
        self.assertEqual(a['curves'], b['curves'])
        self.assertNotEqual(a['reference_ftp'], b['reference_ftp'])

    def test_shared_aerobic_cost_and_different_threshold_cost(self):
        def slow(p, ftp):
            return model.fatigue(np.full(600, float(p)), ftp, model.DEFAULTS)[0][-1]
        self.assertAlmostEqual(slow(140, 185), slow(140, 203))
        self.assertGreater(slow(185, 185), slow(185, 203))

    def test_pause_is_zero_power_and_recovery(self):
        r = {'rows': recording([250]*180)['rows']+recording([140]*180, 360)['rows']}
        a = model.analyze(meta(), r)
        self.assertEqual(a['stop_seconds'], 180)
        self.assertEqual(a['elapsed_seconds'], 540)
        self.assertEqual(a['recorded_work_kj'], 70.2)
        early = next(p for p in a['timeline'] if p['minute'] == 3)
        after = next(p for p in a['timeline'] if p['minute'] == 6)
        self.assertLess(after['fast'], early['fast'])
        self.assertLess(after['slow'], early['slow'])

    def test_repeated_blocks_are_disjoint(self):
        a = model.analyze(meta(), recording([180]*1800))
        blocks = a['blocks']['300']
        self.assertEqual(len(blocks), 3)
        for i, x in enumerate(blocks):
            for y in blocks[i+1:]:
                self.assertTrue(x['start']+300 <= y['start'] or y['start']+300 <= x['start'])

    def test_late_efforts_need_prior_work(self):
        a = model.analyze(meta(), recording([140]*1200))
        self.assertIsNone(a['metrics']['late'])
        self.assertIsNotNone(a['metrics']['sustained'])

    def test_all_efforts_and_exact_rolling_power(self):
        power = np.arange(7200, dtype=float)/20
        a = model.analyze(meta(), recording(power.tolist()))
        curves = {c['seconds']: c for c in a['curves']}
        self.assertEqual(model.EFFORT_DURATIONS, [180,300,480,600,900,1200,1800,2700,3600])
        for d in model.EFFORT_DURATIONS:
            self.assertAlmostEqual(curves[d]['best'], round(float(np.mean(power[-d:])), 2))
            self.assertIn(str(d), a['work_curve'][0])
        self.assertIsNone(curves[2700]['repeated'])
        self.assertEqual(curves[2700]['repeat_count'], 2)

    def test_late_45_requires_work_before_window(self):
        a = model.analyze(meta(), recording([300]*1800+[140]*2700))
        c = next(c for c in a['curves'] if c['seconds'] == 2700)
        self.assertGreater(c['best'], 140)
        self.assertAlmostEqual(c['after_work']['500'], (133*300+2567*140)/2700, places=2)
        self.assertIsNone(c['after_work']['750'])

    def test_missing_samples_not_fabricated(self):
        r = recording([140]*1200)
        r['rows'][600][1] = None
        a = model.analyze(meta(), r)
        self.assertEqual(a['missing_power_samples'], 1)
        self.assertFalse(any(c['seconds'] == 1200 for c in a['curves']))

    def test_comparison_missing_is_not_zero(self):
        self.assertIsNone(model.compare(None, [100, 110])['delta'])
        self.assertIsNone(model.compare(100, [0, 0])['delta'])


if __name__ == '__main__':
    unittest.main()
