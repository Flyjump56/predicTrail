"""Vérifier l'accès HTTP au mode serveur avec deux sessions distinctes."""
from base64 import b64decode, b64encode
from http.client import HTTPResponse
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.parse import urlencode
import unittest
from zipfile import ZipFile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bzhaventure.hosted import AccountServer, HostedDashboard, main
from bzhaventure.accounts import Accounts, password_hash
from test_v11 import gpx_bytes


class BufferedSocket:
    def __init__(self, request):
        self.request = BytesIO(request)
        self.response = bytearray()

    def makefile(self, *args):
        return self.request

    def sendall(self, data):
        self.response.extend(data)


class HostedTests(unittest.TestCase):
    def test_existing_account_database_is_migrated(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "accounts.sqlite3"
            db = sqlite3.connect(database)
            try:
                db.executescript("""
                    CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                        admin INTEGER NOT NULL, salt BLOB NOT NULL, verifier BLOB NOT NULL);
                    CREATE TABLE sessions (digest TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
                """)
                salt = b"test-only-salt"
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                           ("original", "admin", 1, salt, password_hash("original-password", salt)))
                db.commit()
            finally:
                db.close()
            accounts = Accounts(temporary)
            self.assertEqual(accounts.statistics()[0]["login_count"], 0)
            token = accounts.login("admin", "original-password")
            self.assertTrue(accounts.user(token)["admin"])
            self.assertEqual(Accounts(temporary).statistics()[0]["login_count"], 1)

    def test_administration_and_private_workspaces(self):
        with TemporaryDirectory() as temporary:
            with AccountServer(("127.0.0.1", 0), temporary, "http://127.0.0.1", bind_and_activate=False) as server:
                password = "test-only-password"
                server.accounts.create("admin", password, first_admin=True)
                self.check_accounts(server, password)

    def check_accounts(self, server, password):
        def request(path, *, cookie="", form=None, data=None, origin=None, photo=None):
            headers = {"Host": server.host, "Cookie": cookie, "Origin": origin or server.origin}
            body = None
            if form is not None:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                body = urlencode(form)
                if photo is not None:
                    boundary = "profile-test"
                    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
                    body = b"".join(
                        f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
                        for key, value in form.items()
                    )
                    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="photo.png"\r\n'
                             'Content-Type: image/png\r\n\r\n').encode() + photo + f"\r\n--{boundary}--\r\n".encode()
            if data is not None:
                headers["Content-Type"] = "application/json"
                body = json.dumps(data)
            method = "GET" if body is None else "POST"
            payload = body if isinstance(body, bytes) else (body or "").encode()
            headers["Content-Length"] = str(len(payload))
            header_lines = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
            socket = BufferedSocket(f"{method} {path} HTTP/1.0\r\n{header_lines}\r\n".encode() + payload)
            HostedDashboard(socket, ("127.0.0.1", 12345), server)
            socket.request = BytesIO(socket.response)
            response = HTTPResponse(socket)
            response.begin()
            payload = response.read()
            if not response.getheader("Content-Type", "").startswith(("image/","application/vnd.openxmlformats-")):
                payload = payload.decode("utf-8")
            return response.status, response.getheader("Set-Cookie"), payload

        def login(username):
            status, cookie, _ = request("/connexion", form=dict(username=username, password=password))
            self.assertEqual(status, 303)
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=Strict", cookie)
            cookie = cookie.split(";")[0]
            _, _, page = request("/", cookie=cookie)
            account = re.search(r'data-account="([0-9a-f]+)"', page)[1]
            return cookie, "/compte/" + account

        def wait_for_operation(prefix, cookie):
            deadline = monotonic() + 15
            while monotonic() < deadline:
                status, _, body = request(prefix + "/api/operation", cookie=cookie)
                self.assertEqual(status, 200)
                result = json.loads(body)
                if result["status"] != "loading":
                    return result
                sleep(.05)
            self.fail("Initialisation du compte trop longue.")

        self.assertEqual(request("/api/state")[0], 401)
        admin_cookie, admin_prefix = login("admin")
        self.assertEqual(request("/administration", cookie=admin_cookie,
                                 form=dict(username="coureur", password=password))[0], 200)
        runner_cookie, runner_prefix = login("coureur")
        self.assertNotEqual(admin_prefix, runner_prefix)
        runner_id = runner_prefix.rsplit("/", 1)[-1]
        admin_id = admin_prefix.rsplit("/", 1)[-1]
        admin_dashboard = request("/", cookie=admin_cookie)[2]
        runner_dashboard = request("/", cookie=runner_cookie)[2]
        self.assertIn('id="admin-reference-map"', admin_dashboard)
        self.assertIn('id="tab-administration"', admin_dashboard.split("<nav ", 1)[1].split("</nav>", 1)[0])
        self.assertNotIn('id="admin-reference-map"', runner_dashboard)
        self.assertNotIn('id="tab-administration"', runner_dashboard)
        self.assertIn('href="/parametres-compte"', runner_dashboard)
        self.assertIn('id="account-course-stats"', runner_dashboard)
        status, _, settings = request("/parametres-compte", cookie=runner_cookie)
        self.assertEqual(status, 200)
        self.assertIn("<dd>coureur</dd>", settings)
        self.assertEqual(request("/parametres-compte")[0], 303)
        self.assertEqual(request(runner_prefix + "/api/admin/reference-map?account=" + admin_id,
                                 cookie=runner_cookie)[0], 403)
        self.assertEqual(request(runner_prefix + "/api/admin/operations", cookie=runner_cookie)[0], 403)
        self.assertEqual(json.loads(request(admin_prefix + "/api/admin/operations", cookie=admin_cookie)[2]), {"operations": {}})
        self.assertEqual(request(admin_prefix + "/api/admin/reference-map?account=unknown",
                                 cookie=admin_cookie)[0], 404)
        self.assertEqual(request("/administration", cookie=runner_cookie)[0], 403)
        self.assertEqual(request("/administration", cookie=runner_cookie,
                                 form=dict(username="intrus", password=password))[0], 403)
        self.assertEqual(request(admin_prefix + "/api/state", cookie=runner_cookie)[0], 403)
        self.assertEqual(request(runner_prefix + "/api/local", cookie=admin_cookie)[0], 403)
        self.assertEqual(request(runner_prefix + "/api/state", cookie=runner_cookie,
                                 data={}, origin="https://example.invalid")[0], 403)
        self.assertEqual(request(runner_prefix + "/api/backup/restore", cookie=runner_cookie, data={})[0], 403)

        wait_for_operation(admin_prefix, admin_cookie)
        wait_for_operation(runner_prefix, runner_cookie)
        planning_path = runner_prefix + "/api/planning"
        self.assertIsNone(json.loads(request(planning_path, cookie=runner_cookie)[2])["planning"])
        status, _, payload = request(planning_path + "/trace", cookie=runner_cookie,
                                     data={"gpx":b64encode(gpx_bytes(2)).decode()})
        self.assertEqual(status, 200)
        source = json.loads(payload)["sourceId"]
        plan = {"types":[{"name":"Course","minutes":60}],
                "sessions":[{"date":"2027-05-10","type":"Course","minutes":45,"note":"Endurance"}],
                "goal":{"name":"Trail","date":"2027-06-05","sourceId":source,"filename":"trail.gpx"}}
        status, _, payload = request(planning_path, cookie=runner_cookie, data={"planning":plan,"revision":None})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(request(planning_path, cookie=runner_cookie)[2]), json.loads(payload))
        self.assertEqual(request(planning_path, cookie=runner_cookie, data={"planning":plan,"revision":None})[0], 409)
        self.assertIsNone(json.loads(request(admin_prefix + "/api/planning", cookie=admin_cookie)[2])["planning"])
        self.assertEqual(request(admin_prefix + "/api/source?id="+source, cookie=admin_cookie)[0], 404)
        state = dict(runs=[], settings={"manual-total": "08:42"}, waypoints=[], tourDisabled=True)
        self.assertEqual(request(admin_prefix + "/api/state", cookie=admin_cookie, data={"state": state})[0], 200)
        self.assertEqual(json.loads(request(admin_prefix + "/api/state", cookie=admin_cookie)[2])["state"]["settings"], state["settings"])
        self.assertIsNone(json.loads(request(runner_prefix + "/api/state", cookie=runner_cookie)[2])["state"])

        admin = server.runtimes[admin_prefix.rsplit("/", 1)[-1]]
        runner = server.runtimes[runner_prefix.rsplit("/", 1)[-1]]
        self.assertNotEqual(admin.store.path, runner.store.path)
        self.assertIsNot(admin.garmin, runner.garmin)
        upload = {"name": "Trace privée", "gpx": b64encode(gpx_bytes(1)).decode()}
        self.assertEqual(request(admin_prefix + "/api/local/upload", cookie=admin_cookie, data=upload)[0], 202)
        update = wait_for_operation(admin_prefix, admin_cookie)
        self.assertEqual(update["status"], "ready", update)
        self.assertIsNotNone(admin.model)
        self.assertIsNone(runner.model)
        own_courses = json.loads(request(admin_prefix + "/api/reference-map", cookie=admin_cookie)[2])["courses"]
        other_courses = json.loads(request(runner_prefix + "/api/reference-map", cookie=runner_cookie)[2])["courses"]
        self.assertEqual([course["name"] for course in own_courses], ["Trace privée"])
        self.assertEqual(other_courses, [])
        user_upload = {"name": "Trace du coureur", "gpx": b64encode(gpx_bytes(2)).decode()}
        self.assertEqual(request(runner_prefix + "/api/local/upload", cookie=runner_cookie, data=user_upload)[0], 202)
        self.assertEqual(wait_for_operation(runner_prefix, runner_cookie)["status"], "ready")
        status, _, calendar = request(planning_path + "/references", cookie=runner_cookie)
        self.assertEqual(status, 200)
        self.assertEqual([course["name"] for course in json.loads(calendar)["courses"]], ["Trace du coureur"])
        status, _, workbook = request(planning_path + "/export", cookie=runner_cookie)
        self.assertEqual(status, 200)
        with ZipFile(BytesIO(workbook)) as archive:
            calendar_xml = archive.read("xl/worksheets/sheet1.xml").decode()
            self.assertIn("Trace du coureur", calendar_xml)
            self.assertIn("Endurance", calendar_xml)
            self.assertNotIn("Trace privée", calendar_xml)
        self.assertEqual(request(planning_path + "/print", cookie=runner_cookie)[0], 400)
        status, _, report = request(planning_path + "/print?start=2027-05-10&end=2027-05-10", cookie=runner_cookie)
        self.assertEqual(status, 200)
        self.assertIn("Bilan hebdomadaire", report)
        self.assertIn("Endurance", report)
        self.assertIn("45 min (0 h 45 min)", report)
        self.assertNotIn("Trace du coureur", report)
        status, _, report = request(planning_path + "/print?start=2027-05-10&end=2027-05-16&layout=calendar",
                                    cookie=runner_cookie)
        self.assertEqual(status, 200)
        self.assertIn('class="calendar"', report)
        self.assertIn("Endurance", report)
        self.assertEqual(request(planning_path + "/export", cookie=admin_cookie)[0], 403)
        self.assertNotIn("trace", json.loads(calendar)["courses"][0])
        self.assertEqual(request(planning_path + "/references", cookie=admin_cookie)[0], 403)
        status, _, payload = request(admin_prefix + "/api/admin/operations", cookie=admin_cookie)
        self.assertEqual(status, 200)
        operations = json.loads(payload)["operations"]
        self.assertEqual(operations[runner_id]["status"], "ready")
        self.assertEqual(operations[runner_id]["progress"], 1)
        self.assertNotIn("result", operations[runner_id])
        for endpoint in ("references", "reference-map"):
            status, _, payload = request(admin_prefix + "/api/admin/" + endpoint + "?account=" + runner_id,
                                         cookie=admin_cookie)
            self.assertEqual(status, 200)
            self.assertEqual([course["name"] for course in json.loads(payload)["courses"]], ["Trace du coureur"])
        self.assertEqual(request(admin_prefix + "/api/admin/reference-map?account=" + runner_id,
                                 cookie=admin_cookie, data={})[0], 404)
        self.assertEqual(request(runner_prefix + "/api/reference-gpx", cookie=runner_cookie,
                                 data={"key": own_courses[0]["key"], "mode": "original"})[0], 400)
        statistics = {row["username"]: row for row in server.accounts.statistics()}
        self.assertEqual(statistics["admin"]["model_count"], 1)
        groups = json.loads(statistics["admin"]["model_groups"])
        self.assertEqual(len(groups), 20)
        self.assertEqual(sum(group["exact"] for group in groups), 1)
        populated = next(group["profile"] for group in groups if group["exact"])
        self.assertTrue(all(group["used"] == int(group["profile"] == populated) for group in groups))
        self.assertEqual(statistics["coureur"]["model_count"], 1)
        self.assertEqual(statistics["coureur"]["login_count"], 1)
        last_login = statistics["coureur"]["last_login"]
        with patch("bzhaventure.accounts.time", return_value=last_login + 60):
            self.assertEqual(request(runner_prefix + "/api/state", cookie=runner_cookie)[0], 200)
        with patch("bzhaventure.accounts.time", return_value=last_login + 3600):
            self.assertEqual(request(runner_prefix + "/api/state", cookie=runner_cookie)[0], 200)
        stats = {row["username"]: row for row in server.accounts.statistics()}
        self.assertAlmostEqual(stats["coureur"]["active_seconds"], 360, delta=1)

        status, _, backup = request(admin_prefix + "/api/backup/create", cookie=admin_cookie, data={"state": state})
        self.assertEqual(status, 200, backup)
        backup_path = json.loads(backup)["url"]
        self.assertNotEqual(request(runner_prefix + backup_path, cookie=runner_cookie)[0], 200)
        self.assertEqual(request("/inscription", form={"username":"autonome","password":password,
                                                       "confirmation":password,"admin":"1"})[0], 200)
        photo = b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH1sAAAAASUVORK5CYII=")
        profile = dict(username="avec-photo", password=password, confirmation=password,
                       gender="nonbinary", **{"birth-date": "1990-05-16"})
        self.assertEqual(request("/inscription", form=profile, photo=b"<svg/>")[0], 400)
        self.assertEqual(request("/inscription", form=profile, photo=photo)[0], 200)
        profile_cookie, _ = login("avec-photo")
        settings = request("/parametres-compte", cookie=profile_cookie)[2]
        self.assertIn("Non binaire", settings)
        self.assertIn("1990-05-16", settings)
        self.assertEqual(request("/photo-profil", cookie=profile_cookie)[2], photo)
        self.assertEqual(request("/parametres-compte", cookie=profile_cookie,
                                 form={"gender":"nonbinary","birth-date":"1990-05-16","remove-photo":"yes"}, photo=b"")[0], 200)
        self.assertEqual(request("/photo-profil", cookie=profile_cookie)[0], 404)
        self.assertEqual(request("/administration", cookie=admin_cookie,
                                 form={"action":"profile","username":"avec-photo","gender":"nonbinary","birth-date":"1990-05-16"},
                                 photo=photo)[0], 200)
        self.assertEqual(request("/photo-profil", cookie=profile_cookie)[2], photo)
        self.assertEqual(request("/parametres-compte", cookie=profile_cookie,
                                 form={"username": "admin", "gender": "woman", "birth-date": "1992-02-29"})[0], 200)
        self.assertIn("1992-02-29", request("/parametres-compte", cookie=profile_cookie)[2])
        self.assertNotIn("1992-02-29", request("/parametres-compte", cookie=admin_cookie)[2])
        edit = {"action": "profile", "username": "avec-photo", "gender": "other", "birth-date": ""}
        self.assertEqual(request("/administration", cookie=profile_cookie, form=edit)[0], 403)
        self.assertEqual(request("/administration", cookie=admin_cookie, form={**edit, "birth-date": "2999-01-01"})[0], 400)
        self.assertEqual(request("/administration", cookie=admin_cookie, form=edit)[0], 200)
        settings = request("/parametres-compte", cookie=profile_cookie)[2]
        self.assertIn("<dd>Autre</dd>", settings)
        self.assertIn("<dd>Non renseignée</dd>", settings)
        self.assertEqual(request("/photo-profil", cookie=admin_cookie)[0], 404)
        self.assertEqual(request("/photo-profil")[0], 404)
        own_cookie, own_prefix = login("autonome")
        self.assertEqual(request("/administration", cookie=own_cookie)[0], 403)
        self.assertEqual(request("/mot-de-passe-oublie", form={"username":"autonome"})[0], 200)
        admin_page = request("/administration", cookie=admin_cookie)[2]
        self.assertIn("Demande de réinitialisation", admin_page)
        self.assertIn("Traces dans le modèle", admin_page)
        self.assertIn("Détail par modèle", admin_page)
        self.assertIn("Calculs et progression", admin_page)
        self.assertIn("Utilisées du profil", admin_page)
        self.assertNotIn("Trace privée", admin_page)
        self.assertEqual(request("/administration", cookie=admin_cookie,
                                 form={"action":"reset","username":"autonome"})[0], 400)
        with patch("bzhaventure.hosted.secrets.token_urlsafe", return_value="provisoire-pour-test"):
            reset = request("/administration", cookie=admin_cookie,
                            form={"action":"reset","username":"autonome","confirm":"yes"})
        self.assertEqual(reset[0], 200)
        self.assertIn("provisoire-pour-test", reset[2])
        self.assertEqual(request(own_prefix + "/api/state", cookie=own_cookie)[0], 401)
        status, cookie, _ = request("/connexion", form={"username":"autonome","password":"provisoire-pour-test"})
        self.assertEqual(status, 303)
        temporary_cookie = cookie.split(";")[0]
        self.assertEqual(request("/", cookie=temporary_cookie)[0], 303)
        self.assertEqual(request(own_prefix + "/api/state", cookie=temporary_cookie)[0], 403)
        self.assertEqual(request("/mot-de-passe", cookie=temporary_cookie,
                                 form={"password":"provisoire-pour-test","new-password":password})[0], 303)
        own_cookie, _ = login("autonome")
        self.assertEqual(request("/", cookie=own_cookie)[0], 200)
        self.assertEqual(request("/mot-de-passe", cookie=admin_cookie,
                                 form={"password": password, "new-password": "different-test-password"})[0], 303)
        self.assertEqual(request(admin_prefix + "/api/state", cookie=admin_cookie)[0], 401)
        self.assertEqual(request("/connexion", form=dict(username="admin", password=password))[0], 401)
        self.assertEqual(request("/deconnexion", cookie=runner_cookie, form={})[0], 303)
        self.assertEqual(request(runner_prefix + "/api/state", cookie=runner_cookie)[0], 401)

        token = json.loads(backup)["token"]
        archive = admin.store.path.parent / "sauvegardes" / (token + ".zip")
        with patch.object(sys, "argv", ["lancer_serveur.py", "--data-dir", str(server.directory),
                                         "--restore-account", "coureur", "--archive", str(archive)]):
            main()
        self.assertEqual([row["name"] for row in runner.store.list_activities()], ["Trace privée"])
        self.assertEqual(runner.store.get_app_state()["settings"], state["settings"])
