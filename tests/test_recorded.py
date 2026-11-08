"""Comparaison des temps réels du GPX, sans modèle ni départ imposé."""
import base64
from datetime import datetime
from email.message import Message
from io import BytesIO
import json
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from test_v11 import gpx_bytes, runtime
from bzhaventure.gpx import read_gpx
from bzhaventure.recorded import recorded_run
from bzhaventure.server import Dashboard


class RecordedTests(unittest.TestCase):
    def test_source_times_and_segment_gaps_are_preserved(self):
        root = ET.fromstring(gpx_bytes(1))
        root.find('trk').append(ET.fromstring(gpx_bytes(2)).find('trk/trkseg'))
        course = read_gpx(BytesIO(ET.tostring(root)), timed=True)
        result = recorded_run(course, 1000)
        self.assertEqual(result['duration'], 86400+1600)
        self.assertEqual(result['model']['scope'], 'recorded')
        self.assertEqual(len(result['exportPoints']), 2)
        self.assertEqual(result['exportPoints'][1][0][3], 86400)
        self.assertEqual(datetime.fromisoformat(result['recordedStart']).day, 1)
        mark = result['marks'][1]
        axis, points, _ = course[0]
        expected = 1600*mark[0]/axis[-1]
        self.assertAlmostEqual(mark[1], expected, places=5)
        self.assertEqual(result['marks'][-1][1], result['duration'])

    def test_playback_sections_follow_recorded_times_and_relief_grid(self):
        course = read_gpx(BytesIO(gpx_bytes()), timed=True)
        result = recorded_run(course, 1000)
        sections = result['sections']
        self.assertTrue(sections)
        self.assertEqual(sections[0]['time'], 0)
        self.assertAlmostEqual(sections[-1]['endTime'], result['duration'])
        self.assertAlmostEqual(sections[-1]['endDistance'], result['distance'])
        for section in sections:
            self.assertGreaterEqual(section['endTime'], section['time'])
            self.assertGreater(section['endDistance'], section['distance'])
            self.assertGreaterEqual(section['speed'], 0)

    def test_recorded_api_bypasses_prediction_and_requires_timestamps(self):
        for timed in (True, False):
            data = gpx_bytes()
            if not timed:
                root = ET.fromstring(data)
                for point in root.findall('.//trkpt'):
                    point.remove(point.find('time'))
                data = ET.tostring(root)
            handler = Dashboard.__new__(Dashboard)
            handler.path = '/api/prediction'
            handler.server = runtime(None)  # Modèles indisponibles au démarrage.
            body = json.dumps(dict(gpx=base64.b64encode(data).decode(), mode='recorded', interval=1,
                                   totalSeconds=999, paceSeconds=1)).encode()
            handler.rfile = BytesIO(body)
            handler.headers = Message()
            handler.headers['Content-Type'] = 'application/json'
            handler.headers['Content-Length'] = str(len(body))
            responses = []
            handler.send_json = lambda payload, status=200: responses.append((payload,status))
            with patch('bzhaventure.server.predict', side_effect=AssertionError('Prédiction appelée')), \
                 patch('bzhaventure.server.manual_model', side_effect=AssertionError('Allure imposée')):
                handler.do_POST()
            payload, status = responses[0]
            self.assertEqual(status, 200 if timed else 400)
            if timed:
                self.assertEqual(payload['duration'], 1600)
            else:
                self.assertIn('horodatages', payload['error'])
