"""Contrats de conservation et compatibilité des imports préparés."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unittest
from xml.etree import ElementTree as ET
from bzhaventure.gpx_import import convert_gpx

GPX = b'''<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:s="urn:sensor" version="1.1" creator="test">
 <metadata><name>Test</name></metadata>
 <wpt lat="48" lon="2"><name>Eau</name></wpt>
 <trk><name>Course</name><trkseg>
  <trkpt lat="48" lon="2"><ele>10</ele><time>2026-01-01T00:00:00Z</time><extensions><s:hr>140</s:hr></extensions></trkpt>
  <trkpt lat="48" lon="2"><ele>10</ele><time>2026-01-01T00:05:00Z</time></trkpt>
  <trkpt lat="48.01" lon="2.01"><ele>20</ele><time>2026-01-01T00:10:00Z</time></trkpt>
 </trkseg><trkseg>
  <trkpt lat="48.02" lon="2.02"><ele>30</ele><time>2026-01-01T00:20:00Z</time></trkpt>
  <trkpt lat="48.03" lon="2.03"><ele>40</ele><time>2026-01-01T00:30:00Z</time></trkpt>
 </trkseg></trk>
</gpx>'''

class ImportTests(unittest.TestCase):
    def test_conservation_including_stationary_points_and_segments(self):
        data = GPX.replace(b">", b">" + b" " * 50)
        before = ET.fromstring(data)
        for mode in ("compact", "simulation", "original"):
            converted, report = convert_gpx(data, mode)
            after = ET.fromstring(converted)
            signature = lambda r: [(n.attrib,n.findtext("{*}ele"),n.findtext("{*}time")) for n in r.findall(".//{*}trkpt")]
            self.assertEqual(signature(before), signature(after))
            self.assertEqual(len(after.findall(".//{*}trkseg")), 2)
            self.assertEqual(after.findtext("{*}wpt/{*}name").strip(), "Eau")
            self.assertTrue(report["recordedCompatible"])
            self.assertEqual(report["pointCount"], 5)
            self.assertLessEqual(len(converted), len(data))
            if mode == "original": self.assertEqual(converted, data)
            elif mode == "compact": self.assertIsNotNone(after.find(".//{urn:sensor}hr"))
            else: self.assertIsNone(after.find(".//{urn:sensor}hr"))

    def test_missing_times_are_not_invented(self):
        root = ET.fromstring(GPX)
        for node in root.findall(".//{*}trkpt"):
            node.remove(node.find("{*}time"))
        converted, report = convert_gpx(ET.tostring(root), "simulation")
        self.assertFalse(report["recordedCompatible"])
        self.assertIsNone(ET.fromstring(converted).find(".//{*}time"))

    def test_http_conversion_then_recorded_simulation(self):
        import base64, json
        from email.message import Message
        from io import BytesIO
        from types import SimpleNamespace
        from bzhaventure.server import Dashboard
        def request(path, options):
            h = Dashboard.__new__(Dashboard)
            h.path = path
            h.server = SimpleNamespace()
            payload = json.dumps(options).encode()
            h.rfile = BytesIO(payload)
            h.headers = Message()
            h.headers["Content-Type"] = "application/json"
            h.headers["Content-Length"] = str(len(payload))
            h.headers["Host"] = "localhost"
            h.local_host = lambda: True
            responses = []
            h.send_json = lambda data, status=200: responses.append((data,status))
            h.do_POST()
            return responses[0]
        data, status = request("/api/gpx/convert", dict(gpx=base64.b64encode(GPX).decode(),mode="simulation",preview=True))
        self.assertIn("preview",data)
        self.assertEqual(data["preview"]["duration"],1800)
        self.assertEqual(status,200,data)
        self.assertTrue(data["report"]["recordedCompatible"])
        run, status = request("/api/prediction", dict(gpx=data["gpx"],mode="recorded",interval=1))
        self.assertEqual(status,200,run)
        self.assertEqual(run["duration"],1800)

    def test_invalid_input_and_mode(self):
        for data, mode in [(b"<xml/>","compact"),(b"<!DOCTYPE gpx><gpx/>","compact"),(GPX,"bad"),(b"<gpx/>","compact")]:
            with self.assertRaises(ValueError): convert_gpx(data, mode)

if __name__ == "__main__": unittest.main()
