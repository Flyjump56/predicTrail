"""Carte complète, annulation Garmin et surveillance des processus de validation."""
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import multiprocessing
from pathlib import Path
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch

from test_v11 import FakeGarmin, gpx_bytes
from bzhaventure.analysis import pause_summary
from bzhaventure.garmin import GarminConnection
from bzhaventure.gpx import read_gpx
from bzhaventure.reference_map import reference_map
from bzhaventure.server import Dashboard, StartupStatus
from bzhaventure.storage import Store, validate_filters
from bzhaventure.validation import supervised_build


def stalled_worker(connection, arguments):
    connection.send(('progress', ('validation', 'Étape volontairement bloquée', .3)))
    time.sleep(30)


def heartbeat_worker(connection, arguments):
    while True:
        connection.send(('progress', ('validation', 'Toujours en calcul', .3)))
        time.sleep(.05)


class MonitoringTests(unittest.TestCase):
    def test_total_deadline_applies_even_when_worker_keeps_reporting(self):
        with self.assertRaisesRegex(ValueError, 'surveillance'):
            supervised_build((), lambda *args:None, stall_seconds=10, total_seconds=.8, worker=heartbeat_worker)

    def test_worker_exit_without_result_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'sans résultat'):
            supervised_build((), lambda *args:None, worker=empty_worker)

    def test_stalled_process_is_terminated_without_blocking_parent(self):
        before = {p.pid for p in multiprocessing.active_children()}
        started = time.monotonic()
        with self.assertRaisesRegex(ValueError, 'surveillance'):
            supervised_build((), lambda *args: None, stall_seconds=.8, total_seconds=10, worker=stalled_worker)
        self.assertLess(time.monotonic()-started, 8)
        self.assertEqual(before, {p.pid for p in multiprocessing.active_children()})

    def test_real_validation_result_is_published_by_supervisor(self):
        course = read_gpx(BytesIO(gpx_bytes()), timed=True)
        pause = pause_summary(BytesIO(gpx_bytes()), course)
        events = []
        model, result = supervised_build((['Test'], [course], [pause], []), lambda *args: events.append(args), stall_seconds=15)
        self.assertEqual(len(result['courses']), 1)
        self.assertEqual(len(model.courses), 1)
        self.assertTrue(any(e[0] == 'validation' for e in events))

    def test_status_reports_time_since_last_progress(self):
        status = StartupStatus()
        with patch('bzhaventure.server.monotonic', return_value=status.started+35):
            state = status.snapshot()
        self.assertTrue(state['slow'])
        self.assertEqual(state['lastProgressAgo'], 35)
        with redirect_stdout(StringIO()):
            status.update('ready', 'Prêt', 1)
        self.assertFalse(status.snapshot()['slow'])


class MapTests(unittest.TestCase):
    def test_map_includes_unselected_native_and_imported_courses(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            refs = root/'references'
            refs.mkdir()
            (refs/'native.gpx').write_bytes(gpx_bytes(1))
            store = Store(root/'local.sqlite3')
            key = store.reference_inventory(refs)[0]['key']
            store.select_reference(key, False, refs)
            store.save_activity(dict(id='import',source='gpx',name='Import exclu',kind='running',
                date='2026-05-02',distance=3000,reference=False),gpx_bytes(2))
            report = reference_map(store,refs)
            self.assertEqual(len(report['courses']), 2)
            self.assertTrue(all(not c['enabled'] for c in report['courses']))
            self.assertTrue(all(len(c['trace'][0]) > 1 for c in report['courses']))
            for course in report['courses']:
                self.assertTrue(course['summary']['profile'])
                self.assertEqual([row['name'] for row in course['terrain']], ['Montée', 'Plat', 'Descente'])
                self.assertAlmostEqual(sum(row['distance'] for row in course['terrain']), course['summary']['distance'])
                self.assertAlmostEqual(sum(row['actual'] for row in course['terrain']) + course['unassigned'], course['duration'])
                self.assertIn('unobserved', course['pauses'])
            self.assertEqual(store.reference_sources(refs), [])
            self.assertEqual(report['skipped'], [])


class CancelImportTests(unittest.TestCase):
    def test_stop_endpoint_signals_without_accessing_locked_garmin_session(self):
        operation = StartupStatus()
        operation.state['kind'] = 'garmin'
        operation.cancel_event = Event()
        handler = Dashboard.__new__(Dashboard)
        handler.server = type('Server', (), {'operation':operation})()
        replies = []
        handler.send_json = lambda result, status=200: replies.append(result)
        handler.manage('/api/garmin/stop', {})
        self.assertTrue(operation.cancel_event.is_set())
        self.assertTrue(replies[0]['stopping'])

    def test_stop_keeps_completed_imports_during_the_next_download(self):
        connection = GarminConnection(factory=FakeGarmin)
        connection.connect('test@example.com','test-only')
        connection.complete_mfa('123456')
        cancel = Event()
        second_download = Event()
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/'local.sqlite3')
            save = store.save_activity
            download = connection.client.download_activity
            def download_and_wait(*args, **kwargs):
                if connection.client.downloads:
                    second_download.set()
                    if not cancel.wait(5):
                        raise RuntimeError("Le premier GPX n'a pas été traité pendant le téléchargement suivant.")
                return download(*args, **kwargs)
            def save_and_stop(*args):
                if not second_download.wait(5):
                    raise RuntimeError("Le téléchargement suivant n'a pas démarré.")
                result = save(*args)
                cancel.set()
                return result
            with patch.object(store,'save_activity',side_effect=save_and_stop), \
                 patch.object(connection.client,'download_activity',side_effect=download_and_wait):
                result = connection.import_activities(store,validate_filters({}),True,lambda *args:None,cancel)
            self.assertTrue(result['cancelled'])
            self.assertEqual(result['imported'], 1)
            self.assertEqual(len(store.list_activities()), 1)
            self.assertEqual(len(connection.client.downloads), 2)

    def test_stop_interrupts_activity_list_between_pages(self):
        cancel = Event()
        class Paginated(FakeGarmin):
            garmin_connect_activities = '/activities'
            def connectapi(self, path, params):
                cancel.set()
                return self.get_activities_by_date()
        connection = GarminConnection(factory=Paginated)
        connection.connect('test@example.com','test-only')
        connection.complete_mfa('123456')
        with tempfile.TemporaryDirectory() as folder:
            result = connection.import_activities(Store(Path(folder)/'db.sqlite3'),validate_filters({}),True,lambda *args:None,cancel)
        self.assertTrue(result['cancelled'])
        self.assertEqual(connection.client.downloads, [])


def empty_worker(connection, arguments):
    connection.close()
