"""Diagnostics de connexion : erreurs visibles, sans divulgation des secrets."""
from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bzhaventure.garmin import GarminConnection


class GarminDiagnosticsTests(unittest.TestCase):
    def test_missing_dependency_has_explicit_launcher_guidance(self):
        with patch('bzhaventure.garmin.version', side_effect=PackageNotFoundError), \
             patch('bzhaventure.garmin.sys.version_info', (3, 15)):
            result = GarminConnection().status()
        self.assertFalse(result['available'])
        self.assertIn('absent', result['message'])
        self.assertIn('Demarrer-BZHAventure.cmd', result['message'])

    def test_wrong_connector_version_is_reported(self):
        with patch('bzhaventure.garmin.version', return_value='9.0.0'), \
             patch('bzhaventure.garmin.find_spec', return_value=object()), \
             patch('bzhaventure.garmin.sys.version_info', (3, 15)):
            result = GarminConnection().status()
        self.assertFalse(result['available'])
        self.assertIn('9.0.0', result['message'])
        self.assertIn('0.2.38', result['message'])

    def test_http_and_network_errors_are_distinct_and_sanitized(self):
        for status, expected in [(401,'authentification'),(403,'403'),(429,'limite')]:
            error = RuntimeError('password=SECRET token=PRIVATE')
            error.error = SimpleNamespace(response=SimpleNamespace(status_code=status))
            message = GarminConnection.connection_error(error)
            self.assertIn(expected, message)
            self.assertNotIn('SECRET', message)
            self.assertNotIn('PRIVATE', message)
        timeout = type('ReadTimeout', (Exception,), {})('secret')
        self.assertIn('délai', GarminConnection.connection_error(timeout))

    def test_failed_login_clears_credentials_and_session(self):
        client = SimpleNamespace(password='SECRET')
        def fail(*args, **kwargs):
            raise RuntimeError('password=SECRET')
        client.garth = SimpleNamespace(login=fail)
        connection = GarminConnection(factory=lambda **kwargs: client)
        with self.assertRaises(ValueError) as error:
            connection.connect('test@example.com', 'SECRET')
        self.assertNotIn('SECRET', str(error.exception))
        self.assertIsNone(client.password)
        self.assertIsNone(connection.client)
        self.assertIsNone(connection.account)
