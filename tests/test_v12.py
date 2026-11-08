"""Sélection persistante des références et cohérence de la chronologie exportée."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_v11 import gpx_bytes, runtime
from bzhaventure.analysis import manual_model
from bzhaventure.export import export_points
from bzhaventure.gpx import read_gpx
from bzhaventure.prediction import predict
from bzhaventure.server import initialize
from bzhaventure.storage import Store


class SelectionTests(unittest.TestCase):
    def test_native_selection_changes_training_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            refs = root / 'references'
            refs.mkdir()
            (refs / 'one.gpx').write_bytes(gpx_bytes(1))
            (refs / 'two.gpx').write_bytes(gpx_bytes(2, 30))
            store = Store(root / 'local.sqlite3')
            key = store.reference_inventory(refs)[0]['key']
            store.select_reference(key, False, refs)
            self.assertEqual(len(store.reference_sources(refs)), 1)
            reopened = Store(store.path)
            self.assertFalse(next(s for s in reopened.reference_inventory(refs) if s['key'] == key)['enabled'])
            with patch('bzhaventure.analysis.REFERENCES', refs), patch('bzhaventure.server.REFERENCES', refs), redirect_stdout(StringIO()):
                server = runtime(reopened)
                initialize(server)
                self.assertEqual(server.startup.snapshot()['status'], 'ready')
                self.assertEqual(len(server.references['courses']), 1)
                reopened.select_reference(key, True, refs)
                initialize(server)
                self.assertEqual(len(server.references['courses']), 2)
            with self.assertRaises(ValueError):
                reopened.select_reference('file:unknown', False, refs)

    def test_imported_selection_and_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / 'local.sqlite3')
            activity = dict(id='test', source='gpx', name='Import', kind='running', date='2026-05-01', distance=3000, reference=True)
            store.save_activity(activity, gpx_bytes())
            store.select_reference('activity:test', False, root)
            self.assertEqual(store.reference_sources(root), [])
            self.assertFalse(store.reference_inventory(root)[0]['enabled'])
            store.select_reference('activity:test', True, root)
            self.assertEqual(len(store.reference_sources(root)), 1)


class ExportTests(unittest.TestCase):
    def test_original_points_segments_and_final_time_preserved(self):
        from io import BytesIO
        data = gpx_bytes().replace(b'</trkseg>', b'</trkseg><trkseg><trkpt lat="49" lon="3"><ele>110</ele></trkpt><trkpt lat="49" lon="3.01"><ele>120</ele></trkpt></trkseg>', 1)
        course = read_gpx(BytesIO(data))
        model = manual_model(course, 'total', 36000)
        result = export_points(course, model)
        self.assertEqual([len(s) for s in result], [len(s[1]) for s in course])
        self.assertAlmostEqual(result[-1][-1][3], predict(course, model, 5000)[-1][1], places=6)
        self.assertAlmostEqual(result[1][0][3], result[0][-1][3], places=6)
        times = [p[3] for segment in result for p in segment]
        self.assertEqual(times, sorted(times))
        for segment, exported in zip(course, result):
            self.assertEqual([list(p[:3]) for p in segment[1]], [p[:3] for p in exported])


class GroupRankingTests(unittest.TestCase):
    def test_group_validation_never_uses_other_distance_classes(self):
        from io import BytesIO
        from bzhaventure.analysis import validate_references, pause_summary
        from datetime import datetime, timedelta, timezone
        points = []
        for i in range(81):
            stamp = (datetime(2026, 5, 3, tzinfo=timezone.utc)+timedelta(seconds=i*300)).isoformat()
            points.append(f'<trkpt lat="48" lon="{2+i*.02}"><ele>100</ele><time>{stamp}</time></trkpt>')
        long_data = ('<gpx><trk><trkseg>'+''.join(points)+'</trkseg></trk></gpx>').encode()
        data = [gpx_bytes(1), gpx_bytes(2,30), long_data]
        courses = [read_gpx(BytesIO(item), timed=True) for item in data]
        pauses = [pause_summary(BytesIO(item), course) for item,course in zip(data,courses)]
        _, report = validate_references(['short1','short2','long'],courses,pauses,[])
        first, second, long = report['courses']
        self.assertEqual(first['groupReferenceCount'], 1)
        self.assertEqual(second['groupReferenceCount'], 1)
        self.assertIsNotNone(first['groupEstimated'])
        self.assertEqual(long['groupReferenceCount'], 0)
        self.assertIsNone(long['groupEstimated'])
        self.assertIsNotNone(long['estimated'])
