"""Cache incrémental, modes manuels, repères et import Garmin simulé."""
import base64
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from email.message import Message
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

from test_core import synthetic_course
from bzhaventure.analysis import manual_model, pause_summary
from bzhaventure.garmin import GarminConnection
from bzhaventure.gpx import read_gpx
from bzhaventure.models import SegmentedModel
from bzhaventure.prediction import predict
from bzhaventure.server import Dashboard, StartupStatus, initialize
from bzhaventure.storage import Store, decode, digest, validate_filters


def gpx_bytes(number=1, seconds=20):
    start = datetime(2026, 5, number, tzinfo=timezone.utc)
    points = []
    for i in range(81):
        when = (start + timedelta(seconds=i * seconds)).isoformat()
        points.append(f'<trkpt lat="48" lon="{2 + i * .0005}"><ele>100</ele><time>{when}</time></trkpt>')
    return ("<gpx><trk><trkseg>" + "".join(points) + "</trkseg></trk></gpx>").encode()


def runtime(store):
    server = type("Runtime", (), {})()
    server.startup = StartupStatus()
    server.store = store
    return server


class CacheTests(unittest.TestCase):
    def test_cold_warm_modified_and_removed_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            references = root / "references"
            references.mkdir()
            first = references / "first.gpx"
            second = references / "second.gpx"
            first.write_bytes(gpx_bytes(1))
            second.write_bytes(gpx_bytes(2))
            store = Store(root / "local.sqlite3")
            with patch("bzhaventure.analysis.REFERENCES", references), patch("bzhaventure.server.REFERENCES", references):
                with redirect_stdout(StringIO()):
                    cold = runtime(store)
                    initialize(cold)
                    self.assertEqual(cold.startup.snapshot()["status"], "ready")
                    self.assertFalse(cold.references["cache"]["restored"])
                    warm = runtime(store)
                    with patch("bzhaventure.analysis.read_gpx", side_effect=AssertionError("GPX relu")):
                        initialize(warm)
                    self.assertEqual(warm.startup.snapshot()["status"], "ready")
                    self.assertTrue(warm.references["cache"]["restored"])
                    self.assertEqual(cold.references["error"], warm.references["error"])
                    previous = first.stat().st_mtime
                    first.write_bytes(gpx_bytes(1, 30))
                    os.utime(first, (previous + 2, previous + 2))
                    modified = runtime(store)
                    with patch("bzhaventure.analysis.read_gpx", wraps=read_gpx) as reader:
                        initialize(modified)
                    self.assertEqual(modified.startup.snapshot()["status"], "ready")
                    self.assertEqual(reader.call_count, 1)
                    self.assertEqual(modified.references["cache"]["reused"], 1)
                    second.unlink()
                    removed = runtime(store)
                    initialize(removed)
                    self.assertEqual(removed.startup.snapshot()["status"], "ready")
                    self.assertEqual(len(removed.references["courses"]), 1)

    def test_same_contents_touched_file_reuses_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "course.gpx"
            path.write_bytes(gpx_bytes())
            store = Store(root / "local.sqlite3")
            sources = store.reference_sources(root)
            store.load_reference(sources[0], lambda data: ("analysis", "pause"))
            fingerprint = store.manifest(sources)
            previous = path.stat().st_mtime
            os.utime(path, (previous + 2, previous + 2))
            updated = store.reference_sources(root)
            self.assertIsNone(store.manifest(updated))
            def should_not_run(data):
                raise AssertionError("Analyse répétée")
            value, _, _, reused = store.load_reference(updated[0], should_not_run)
            self.assertTrue(reused)
            self.assertEqual(value, ("analysis", "pause"))
            self.assertEqual(store.manifest(updated), fingerprint)

    def test_corrupted_cache_is_recomputed_and_untrusted_type_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "course.gpx").write_bytes(gpx_bytes())
            store = Store(root / "local.sqlite3")
            source = store.reference_sources(root)[0]
            store.load_reference(source, lambda data: "first")
            with store.connection() as db:
                db.execute("UPDATE reference_cache SET checksum='incorrect'")
            value, _, _, reused = store.load_reference(source, lambda data: "second")
            self.assertFalse(reused)
            self.assertEqual(value, "second")
        payload = pickle.dumps(eval)
        with self.assertRaises(pickle.UnpicklingError):
            decode(payload, digest(payload))

    def test_model_cache_discards_validation_banks(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "local.sqlite3")
            model = SegmentedModel([synthetic_course(), synthetic_course(pace=.6)], validate=False)
            model.evaluation_cache["temporary"] = "data"
            store.save_models("one", (model, {}))
            restored, _ = store.load_models("one")
            self.assertEqual(restored.evaluation_cache, {})
            self.assertGreater(restored.global_model(5), 0)


class ManualTests(unittest.TestCase):
    def test_total_pace_and_custom_points(self):
        course = synthetic_course()
        model = manual_model(course, "total", total_seconds=36000)
        marks = predict(course, model, 7000, [
            dict(km=3.125, comment="Eau <script>"),
            dict(km=7, comment="Ravitaillement"),
            dict(km=20, comment="Fin"),
        ])
        self.assertAlmostEqual(marks[-1][1], 36000)
        point = next(mark for mark in marks if mark[0] == 3125)
        self.assertAlmostEqual(point[1], 36000 * 3125 / 20000)
        self.assertIn("Eau <script>", point[5])
        self.assertEqual(sum(mark[0] == 7000 for mark in marks), 1)
        pace = manual_model(course, "pace", pace_seconds=390)
        self.assertAlmostEqual(predict(course, pace, 10000)[-1][1], 20 * 390)
        with self.assertRaises(ValueError):
            predict(course, pace, 10000, [dict(km=21)])

    def test_manual_endpoint_works_before_model_startup(self):
        handler = Dashboard.__new__(Dashboard)
        handler.path = "/api/prediction"
        handler.server = runtime(None)
        body = json.dumps(dict(gpx=base64.b64encode(gpx_bytes()).decode(), mode="total",
                               totalSeconds=7200, interval=1,
                               waypoints=[dict(km=.123, comment="Eau")])).encode()
        handler.rfile = BytesIO(body)
        handler.headers = Message()
        handler.headers["Content-Type"] = "application/json"
        handler.headers["Content-Length"] = str(len(body))
        responses = []
        handler.send_json = lambda payload, status=200: responses.append((payload, status))
        handler.do_POST()
        payload, status = responses[0]
        self.assertEqual(status, 200, payload)
        self.assertAlmostEqual(payload["duration"], 7200)
        self.assertIsNone(payload["pauses"]["duration"])
        self.assertEqual(payload["model"]["scope"], "manual")
        self.assertTrue(any(mark[0] == 123 for mark in payload["marks"]))


class FakeGarmin:
    class ActivityDownloadFormat:
        GPX = "GPX"

    def __init__(self, **kwargs):
        self.garth = self
        self.password = kwargs["password"]
        self.downloads = []

    def login(self, email, password, **kwargs):
        return "needs_mfa", {"pending": True}

    def resume_login(self, state, code):
        if code != "123456":
            raise ValueError("Invalid code")

    def get_activities_by_date(self, *args, **kwargs):
        return [
            dict(activityId=1, activityName="Trail", activityType=dict(typeKey="trail_running"),
                 startTimeLocal="2026-05-01 08:00:00", distance=20000),
            dict(activityId=2, activityName="Vélo", activityType=dict(typeKey="e_bike_mountain"),
                 startTimeLocal="2026-05-02 08:00:00", distance=30000),
            dict(activityId=3, activityName="Marche", activityType=dict(typeKey="walking"),
                 startTimeLocal="2026-05-03 08:00:00", distance=10000),
        ]

    def download_activity(self, activity_id, dl_fmt=None):
        self.downloads.append(activity_id)
        return gpx_bytes(int(activity_id))


class ImportTests(unittest.TestCase):
    def test_garmin_mfa_filters_deduplication_and_local_delete(self):
        connection = GarminConnection(factory=FakeGarmin)
        self.assertTrue(connection.connect("user@example.com", "password")["mfa"])
        self.assertIsNone(connection.client.password)
        with self.assertRaises(ValueError):
            connection.complete_mfa("wrong")
        self.assertTrue(connection.complete_mfa("123456")["connected"])
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "local.sqlite3")
            filters = validate_filters(dict(kind="all", minKm=5, maxKm=40,
                                           minDate="2026-05-01", maxDate="2026-05-03"))
            report = connection.import_activities(store, filters, True, lambda *args: None)
            self.assertEqual(report["imported"], 3)
            rows = store.list_activities()
            self.assertEqual(sum(row["reference"] for row in rows), 1)
            second = connection.import_activities(store, filters, True, lambda *args: None)
            self.assertEqual(second["existing"], 3)
            self.assertEqual(len(connection.client.downloads), 3)
            original = connection.client.get_activities_by_date
            edited = original()[0]
            edited["activityName"] = "Trail corrigé"
            edited["lastModifiedDate"] = "2026-06-01"
            connection.client.get_activities_by_date = lambda *args, **kwargs: [edited]
            update = connection.import_activities(store, filters, True, lambda *args: None)
            self.assertEqual(update["imported"], 1)
            self.assertTrue(any(row["name"] == "Trail corrigé" for row in store.list_activities()))
            store.save_models("test", ("model", {}))
            removed = store.delete_activities(validate_filters(dict(kind="cycling", minKm=25, maxKm=35)))
            self.assertEqual(removed, 1)
            self.assertIsNotNone(store.load_models("test"))
            self.assertEqual(len(store.list_activities()), 2)
            self.assertEqual(store.delete_activities(), 2)
            self.assertEqual(store.list_activities(), [])
            self.assertIsNone(store.load_models("test"))
        self.assertFalse(connection.disconnect()["connected"])

    def test_filters_reject_reversed_or_nonfinite_bounds(self):
        for filters in [dict(minKm=20, maxKm=10), dict(minKm="NaN"),
                        dict(minDate="2026-05-03", maxDate="2026-05-01")]:
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                validate_filters(filters)


if __name__ == "__main__":
    unittest.main()
