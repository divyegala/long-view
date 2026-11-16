import sys
import unittest
from unittest.mock import patch
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

    def test_late_efforts_need_an_hour_and_a_complete_effort(self):
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
            self.assertEqual(curves[d]['after_hours']['0'], curves[d]['best'])
            self.assertNotIn('p90', curves[d])
        self.assertIsNone(curves[2700]['repeated'])
        self.assertEqual(curves[2700]['repeat_count'], 2)

    def test_late_45_uses_elapsed_cutoff_and_requires_full_duration(self):
        a = model.analyze(meta(), recording([300]*1800+[140]*7200))
        c = next(c for c in a['curves'] if c['seconds'] == 2700)
        self.assertGreater(c['best'], 140)
        self.assertEqual(c['after_hours']['1'], 140)
        self.assertIsNone(c['after_hours']['2'])
        self.assertEqual(a['metrics']['late'], 140)

    def test_hourly_eligibility_does_not_depend_on_absolute_watts(self):
        for scale in [1, 2]:
            a = model.analyze(meta(), recording([100*scale]*3600+[150*scale]*300))
            c = next(c for c in a['curves'] if c['seconds'] == 300)
            self.assertEqual(c['after_hours']['1'], 150*scale)

    def test_stops_advance_hour_cutoff_and_stay_zero_power(self):
        a = model.analyze(meta(), {'rows': recording([140]*1800)['rows']+recording([150]*1800, 3600)['rows']})
        c = next(c for c in a['curves'] if c['seconds'] == 300)
        self.assertEqual(a['stop_seconds'], 1800)
        self.assertEqual(c['after_hours']['1'], 150)
        self.assertEqual(a['elapsed_hours'], [0, 1])

    def test_hour_boundary_requires_every_second_of_selected_duration(self):
        for count, expected in [(179, None), (180, 150)]:
            a = model.analyze(meta(), recording([100]*3600+[150]*count))
            c = next(c for c in a['curves'] if c['seconds'] == 180)
            self.assertEqual(c['after_hours']['1'], expected)

    def test_high_starting_load_is_retained_alongside_other_bands(self):
        power = [140]*300+[150]*300+[160]*300
        slow = np.r_[np.zeros(300), np.full(300, 45), np.full(301, 90)]
        with patch.object(model, 'fatigue', return_value=(slow, np.zeros(901))):
            a = model.analyze(meta(), recording(power))
        c = next(c for c in a['curves'] if c['seconds'] == 180)
        self.assertEqual(set(c['fatigue_levels']), {'low', 'moderate', 'high'})
        self.assertEqual(c['fatigue_levels']['high'], 160)
        self.assertTrue(all(value is not None for value in c['fatigue_levels'].values()))

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
