"""Non-régression des calculs et de l'API après réorganisation des sources."""
from datetime import datetime, timedelta, timezone
from email.message import Message
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bzhaventure.analysis import (
    choose_model, estimate_pauses, pause_summary, predicted_sections, terrain_breakdown,
)
from bzhaventure.gpx import Course, adapt_course, blocks, describe_course, read_gpx
from bzhaventure.models import InclinationModel, SegmentedModel, fit_inclination, inclination_band
from bzhaventure.prediction import predict
from bzhaventure.server import Dashboard, STATIC_FILES, StartupStatus, initialize
from bzhaventure.settings import PROFILE_LABELS, SOURCE_SAMPLING


def synthetic_course(profile="mountain", length=20000, pace=0.5):
    """Créer une course reproductible sans dépendre des GPX personnels."""
    axis = [length * i / 400 for i in range(401)]

    def altitude(position):
        if profile == "flat":
            return 100
        if profile == "mixed":
            x = position/length*20000
            offset = 0
            for amplitude, half in [(600,3000),(400,1500),(400,1500)]+[(70,400)]*4:
                if x <= offset+2*half:
                    return 100+amplitude*max(0,1-abs((x-offset)/half-1))
                offset += 2*half
            return 100
        period, amplitude = {
            "rolling": (4000, 30),
            "intermediate": (4000, 200),
            "sawtooth": (400, 70),
            "mountain": (10000, 1000),
        }[profile]
        phase = (position % period) / period
        return 100 + amplitude * (1 - abs(2 * phase - 1))

    points = [(48, position / 100000, altitude(position), position * pace) for position in axis]
    return adapt_course([(axis, points, points)])


class GpxTests(unittest.TestCase):
    def test_four_relief_families(self):
        for profile in PROFILE_LABELS:
            with self.subTest(profile=profile):
                course = synthetic_course(profile)
                description = describe_course(course)
                self.assertEqual(description["profile"], profile)
                self.assertEqual(description["sampling"], SOURCE_SAMPLING[profile][1])
                self.assertAlmostEqual(sum(length for length, _, _ in blocks(course)), 20000)

    def test_tiny_segment_keeps_both_ends(self):
        course = adapt_course([([0, 0.05], [(48, 2, 10, 0), (48, 2.000001, 10, 1)], [])])
        self.assertEqual(len(course[0][2]), 2)
        self.assertAlmostEqual(sum(length for length, _, _ in blocks(course)), 0.05)

    def test_target_without_dates_and_reference_with_dates_required(self):
        xml = '<gpx><trk><trkseg><trkpt lat="48" lon="2"><ele>100</ele></trkpt><trkpt lat="48" lon="2.01"><ele>110</ele></trkpt></trkseg></trk></gpx>'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parcours.gpx"
            path.write_text(xml, encoding="utf-8")
            self.assertGreater(describe_course(read_gpx(path))["distance"], 0)
            with self.assertRaisesRegex(ValueError, "Horodatage"):
                read_gpx(path, timed=True)


class ModelTests(unittest.TestCase):
    def test_checkpoints_and_timeline_agree_on_adaptive_intervals(self):
        course = synthetic_course()
        bank = SegmentedModel([synthetic_course(pace=0.4), synthetic_course(pace=0.6)], validate=False)
        marks = predict(course, bank, 7000)
        sections = predicted_sections(course, bank)
        terrain = terrain_breakdown(course, bank)
        self.assertEqual([round(row[0]) for row in marks], [0, 7000, 14000, 20000])
        self.assertAlmostEqual(marks[-1][1], sections[-1]["endTime"])
        self.assertAlmostEqual(sum(row["estimated"] for row in terrain), marks[-1][1])
        self.assertTrue(all(b[1] > a[1] for a, b in zip(marks, marks[1:])))

    def test_unrepresented_profile_uses_positive_curve(self):
        bank = SegmentedModel([synthetic_course(), synthetic_course(pace=0.6)], validate=False)
        model = bank.select("flat", "medium", 75000)
        self.assertEqual(model.metadata["exactCount"], 0)
        self.assertEqual(model.metadata["localWeight"], 0)
        self.assertTrue(all(model(grade) > 0 for grade in (-100, 0, 100)))

    def test_inclination_selection_preserves_model_type(self):
        grades = [-50, -35, -20, -12, -5, 0, 5, 12, 20, 35, 50] * 20
        axis = [0]
        points = [(48, 2, 2000, 0, 0)]
        for grade in grades:
            axis.append(axis[-1] + 100)
            before = points[-1]
            pace = 0.5 + abs(grade) / 20 + (0.3 if grade > 3 else 0)
            points.append((48, 2 + axis[-1] / 100000, before[2] + grade,
                           before[3] + 100 * pace, axis[-1]))
        course = Course([(axis, [point[:4] for point in points], points)])
        model = fit_inclination([course])
        bank = type("Bank", (), {"inclination_model": lambda self: model})()
        selected = choose_model(bank, course, "inclination")
        self.assertIsInstance(selected, InclinationModel)
        self.assertEqual(selected(3.01), selected(7.99))
        self.assertEqual(selected(-3), selected(3))
        self.assertGreater(selected(12), selected(-12))
        self.assertIsNot(selected.metadata, model.metadata)
        self.assertEqual(inclination_band(-100), 0)
        self.assertEqual(inclination_band(100), 10)

    def test_pauses_follow_model_weights(self):
        bank = SegmentedModel([synthetic_course("mountain"), synthetic_course("rolling")], validate=False)
        course = synthetic_course("rolling")
        references = [
            dict(actual=10000, pauses=dict(duration=1000, unobserved=0)),
            dict(actual=10000, pauses=dict(duration=3000, unobserved=0)),
        ]
        global_pause = estimate_pauses(12000, choose_model(bank, course, "global"), references)
        manual = choose_model(bank, course, "rolling:short")
        manual_pause = estimate_pauses(12000, manual, references)
        self.assertAlmostEqual(global_pause["duration"], 1200)
        self.assertGreater(manual_pause["duration"], global_pause["duration"])
        self.assertEqual(manual_pause["referenceCount"], 1)
        unavailable = estimate_pauses(12000, manual, [
            dict(actual=10000, pauses=dict(duration=0, unobserved=10000))])
        self.assertIsNone(unavailable["duration"])


class ServerTests(unittest.TestCase):
    def handler(self, path):
        handler = Dashboard.__new__(Dashboard)
        handler.path = path
        handler.server = type("Server", (), {})()
        handler.server.startup = StartupStatus()
        return handler

    def test_web_assets_available_during_startup(self):
        for path in ["/", *STATIC_FILES]:
            with self.subTest(path=path):
                handler = self.handler(path)
                responses = []
                handler.reply = lambda body, kind, status=200: responses.append((body, kind, status))
                handler.do_GET()
                self.assertEqual(responses[0][2], 200)
                self.assertGreater(len(responses[0][0]), 0)

    def test_references_unavailable_until_ready(self):
        handler = self.handler("/api/references")
        responses = []
        handler.send_json = lambda body, status=200: responses.append((body, status))
        handler.do_GET()
        self.assertEqual(responses[-1][1], 503)
        handler.server.references = {"courses": []}
        handler.server.startup.update("ready", "Prêt", 1)
        handler.do_GET()
        self.assertEqual(responses[-1][1], 200)

    def test_startup_failure_visible(self):
        handler = self.handler("/")
        with patch("bzhaventure.server.load_references", side_effect=ValueError("Référence de test invalide")):
            initialize(handler.server)
        state = handler.server.startup.snapshot()
        self.assertEqual(state["status"], "error")
        self.assertIn("Référence de test", state["message"])

    def test_prediction_response_consistent(self):
        handler = self.handler("/api/prediction?pas-km=1&model=inclination")
        handler.server.startup.update("ready", "Prêt", 1)
        courses = [synthetic_course("flat", pace=0.5), synthetic_course("flat", pace=0.6)]
        handler.server.model = SegmentedModel(courses, validate=False)
        handler.server.references = {"courses": [
            dict(actual=10000, pauses=dict(duration=1000, unobserved=0)),
            dict(actual=10000, pauses=dict(duration=2000, unobserved=0)),
        ]}
        body = b'<gpx><trk><trkseg><trkpt lat="48" lon="2"><ele>100</ele></trkpt><trkpt lat="48" lon="2.1"><ele>100</ele></trkpt></trkseg></trk></gpx>'
        handler.rfile = BytesIO(body)
        handler.headers = Message()
        handler.headers["Content-Type"] = "application/gpx+xml"
        handler.headers["Content-Length"] = str(len(body))
        responses = []
        handler.send_json = lambda payload, status=200: responses.append((payload, status))
        handler.do_POST()
        result, status = responses[0]
        self.assertEqual(status, 200)
        self.assertAlmostEqual(result["duration"], result["marks"][-1][1])
        self.assertAlmostEqual(result["duration"], result["sections"][-1]["endTime"])
        self.assertAlmostEqual(result["duration"], result["movingDuration"] + result["pauses"]["duration"])

    def test_pause_estimate_excludes_recording_gaps(self):
        start = datetime(2026, 11, 7, tzinfo=timezone.utc)
        groups = [
            [(0, 0), (30, 0.001), (60, 0.001), (90, 0.001), (120, 0.001),
             (150, 0.002), (750, 0.002), (780, 0.002), (810, 0.003)],
            [(1000, 0.003), (1030, 0.003), (1060, 0.003), (1090, 0.004)],
        ]
        xml = "<gpx><trk>"
        for points in groups:
            xml += "<trkseg>"
            for seconds, longitude in points:
                date = (start + timedelta(seconds=seconds)).isoformat()
                xml += f'<trkpt lat="48" lon="{longitude}"><ele>100</ele><time>{date}</time></trkpt>'
            xml += "</trkseg>"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pauses.gpx"
            path.write_text(xml + "</trk></gpx>", encoding="utf-8")
            result = pause_summary(path, read_gpx(path, timed=True))
        self.assertEqual(result, dict(duration=150, count=2, unobserved=790))


if __name__ == "__main__":
    unittest.main()
