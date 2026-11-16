import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import import_rides
import server


def bundle():
    return {'schema': 'LONG_VIEW_IMPORT_V1', 'source': 'example', 'activities': [{
        'activity': {'id': 'same-id', 'start_local': '2020-01-01T09:00:00',
                     'type': 'VirtualRide', 'duration_minutes': 120, 'name': 'Synthetic ride'},
        'recording': {'timeline': 'one_second_with_stops',
                      'rows': [[t, 140, 120, 85, 5] for t in range(600)]}}]}


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name)
        for name in ['streams', 'analysis']:
            (self.store/name).mkdir()
        self.data = patch.object(server, 'DATA', self.store)
        self.data.start()
        self.addCleanup(self.data.stop)
        self.cache = patch.object(server, 'CACHE', {})
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def test_reimport_is_idempotent_and_keeps_recording_on_metadata_only_sync(self):
        first = import_rides.import_bundle(bundle())
        incoming = bundle()
        incoming['activities'][0]['recording'] = None
        incoming['activities'][0]['activity']['name'] = 'Updated title'
        self.assertEqual(import_rides.import_bundle(incoming), first)
        self.assertEqual(len(server.catalog()), 1)
        self.assertEqual(server.catalog()[0]['name'], 'Updated title')
        self.assertEqual(len(server.read(server.recording_path(first[0]), {})['rows']), 600)

    def test_provider_ids_cannot_collide(self):
        first = import_rides.import_bundle(bundle())
        other = bundle()
        other['source'] = 'another-provider'
        self.assertNotEqual(import_rides.import_bundle(other), first)
        self.assertEqual(len(server.catalog()), 2)

    def test_null_power_is_preserved(self):
        incoming = bundle()
        incoming['activities'][0]['recording']['rows'][10][1] = None
        key = import_rides.import_bundle(incoming)[0]
        self.assertIsNone(server.read(server.recording_path(key), {})['rows'][10][1])
        self.assertEqual(server.load_analysis(server.catalog()[0])['missing_power_samples'], 1)

    def test_catalog_only_has_no_analysis(self):
        incoming = bundle()
        incoming['activities'][0]['recording'] = None
        import_rides.import_bundle(incoming)
        self.assertIsNone(server.load_analysis(server.catalog()[0]))
        self.assertEqual(server.bootstrap()['coverage']['modeled120'], 0)

    def test_ambiguous_timeline_is_rejected_before_any_writes(self):
        incoming = bundle()
        bad = copy.deepcopy(incoming['activities'][0])
        bad['activity']['id'] = 'bad'
        bad['recording']['timeline'] = 'sparse-smart-recording'
        incoming['activities'].append(bad)
        with self.assertRaises(ValueError):
            import_rides.import_bundle(incoming)
        self.assertEqual(server.catalog(), [])
        self.assertEqual(list((self.store/'streams').iterdir()), [])

    def test_invalid_samples_and_units_are_rejected(self):
        for value in [-1, float('nan'), float('inf'), True, '140 watts']:
            with self.subTest(value=value):
                incoming = bundle()
                incoming['activities'][0]['recording']['rows'][1][1] = value
                with self.assertRaises(ValueError):
                    import_rides.prepare_bundle(incoming)

    def test_recording_and_metadata_changes_invalidate_live_cache(self):
        incoming = bundle()
        import_rides.import_bundle(incoming)
        ride = server.catalog()[0]
        first = server.load_analysis(ride)
        for row in incoming['activities'][0]['recording']['rows']:
            row[1] = 150
        import_rides.import_bundle(incoming)
        self.assertNotEqual(server.load_analysis(ride)['recorded_work_kj'], first['recorded_work_kj'])
        # A different process can also replace the recording; the running server notices.
        key = ride['id']
        recording = server.read(server.recording_path(key), {})
        recording['rows'][0][1] = 300
        server.write(server.recording_path(key), recording)
        second = server.load_analysis(ride)
        self.assertEqual(second['recorded_work_kj'], 90.15)
        changed = dict(ride, type='Ride')
        self.assertNotEqual(second['reference_ftp'], server.load_analysis(changed)['reference_ftp'])


if __name__ == '__main__':
    unittest.main()
