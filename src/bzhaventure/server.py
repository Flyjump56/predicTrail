"""Serveur HTTP local et initialisation asynchrone avec suivi d'avancement."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import base64
import binascii
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
import uuid
import json
import sys
from threading import Event, Lock, Thread
from time import monotonic
from urllib.parse import parse_qs, urlsplit
from xml.etree.ElementTree import ParseError

from .analysis import (choose_model, estimate_pauses, geometry, load_references, model_catalog,
                       manual_model, model_summary, pause_summary, predicted_sections, read_references,
                       summarize, terrain_breakdown, validate_references)
from .gpx_import import convert_gpx, MAX_SOURCE
from .gpx import describe_course, elapsed, read_gpx, resample_course
from .models import fit
from .prediction import predict
from .planning import planning_date, read_planning, save_planning
from .planning_report import planning_print, planning_xlsx, report_rows
from .export import export_points
from .recorded import recorded_run, recorded_sections
from .strategy import apply_strategy
from .reference_map import reference_map
from .validation import supervised_build, build_models, STALL_SECONDS
from .settings import HOST, LOGO, MAX_UPLOAD, PAGE, PORT, REFERENCES, WEB_DIR
from .garmin import GarminConnection
from .storage import Store, digest, validate_filters
from . import __version__
import platform
import zipfile
import shutil
import sqlite3
import os
from .backup import Backups, MAX_ARCHIVE, validate_state

MAX_REFERENCE_BATCH = 3 * MAX_UPLOAD
MAX_REFERENCE_FILES = 20

# Liste fermée des ressources servies par HTTP.
STATIC_FILES = {
    "/assets/logo-bzhaventure.png": (LOGO, "image/png"),
    "/assets/theme.jpg": (LOGO.parent / "thème.jpg", "image/jpeg"),
    "/assets/styles.css": (WEB_DIR / "styles.css", "text/css; charset=utf-8"),
    "/assets/backup.js": (WEB_DIR / "backup.js", "text/javascript; charset=utf-8"),
    "/assets/planning.js": (WEB_DIR / "planning.js", "text/javascript; charset=utf-8"),
    "/assets/app.js": (WEB_DIR / "app.js", "text/javascript; charset=utf-8"),
    "/assets/admin-progress.js": (WEB_DIR / "admin-progress.js", "text/javascript; charset=utf-8"),
}


class StartupStatus:
    """État de démarrage partagé entre le travail de fond et les requêtes HTTP."""
    def __init__(self):
        self.lock = Lock()
        self.started = monotonic()
        self.finished = None
        self.updated = self.started
        self.state = dict(status="loading", phase="initialization", message="Initialisation",
                          progress=0, completed=0, total=0)

    def update(self, phase, message, progress, completed=0, total=0, log=True):
        """Publier une progression croissante et afficher la même étape en console."""
        with self.lock:
            self.updated = monotonic()
            self.state.update(phase=phase, message=message,
                              progress=max(self.state["progress"], min(1, progress)),
                              completed=completed, total=total)
            if phase in ("ready", "empty", "error"):
                self.state["status"] = phase
                self.finished = monotonic()
        if log:
            print(f"[{progress:.0%}] {message}", flush=True)

    def snapshot(self):
        with self.lock:
            age = round((self.finished or monotonic())-self.updated, 1)
            return dict(self.state, elapsed=round((self.finished or monotonic()) - self.started, 1),
                        lastProgressAgo=age, slow=self.state["status"] == "loading" and age >= 30,
                        validationTimeout=STALL_SECONDS,
                        cancelRequested=getattr(self, "cancel_event", Event()).is_set())


class Dashboard(BaseHTTPRequestHandler):
    """API locale et distribution des fichiers web explicitement autorisés."""
    @property
    def runtime_context(self):
        return self.server

    @property
    def reference_directory(self):
        return getattr(self.runtime_context, "reference_directory", REFERENCES)

    def log_request(self, code="-", size="-"):
        if self.path != "/api/startup":
            super().log_request(code, size)

    def reply(self, body, content_type, status=200, *, attachment=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if attachment is not None:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload, status=200):
        self.reply(json.dumps(payload).encode("utf-8"), "application/json", status)

    def ready(self):
        """Répondre 503 tant que les modèles complets ne sont pas publiés."""
        startup = getattr(self.runtime_context, "startup", None)
        if startup is None or startup.snapshot()["status"] == "ready":
            return True
        self.send_json(dict(error="Initialisation en cours ou interrompue.", startup=startup.snapshot()), 503)
        return False

    def local_host(self):
        headers = getattr(self, "headers", None)
        host = headers.get("Host") if headers else None
        if host and urlsplit("http://" + host).hostname not in ("127.0.0.1", "localhost"):
            self.send_json(dict(error="Adresse locale attendue."), 403)
            return False
        return True

    def retain_gpx(self, store, body):
        key = digest(body)
        directory = store.path.parent / "parcours-importes"
        directory.mkdir(exist_ok=True)
        path = directory / (key + ".gpx")
        if not path.exists():
            temporary = directory / (uuid.uuid4().hex + ".tmp")
            try:
                temporary.write_bytes(body)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        return key

    def send_prediction(self,payload,body,options):
        store=getattr(self.runtime_context,"store",None)
        if store and options.get("retainSource"):
            payload["sourceId"] = self.retain_gpx(store, body)
        self.send_json(payload)

    def backups(self):
        store=getattr(self.runtime_context,"store",None)
        if store is None:raise ValueError("Stockage en cours d’initialisation.")
        return Backups(store,self.reference_directory)

    def do_GET(self):
        if not self.local_host():
            return
        parsed=urlsplit(self.path)
        if parsed.path=="/api/backup/list":
            try:self.send_json(dict(backups=self.backups().list_backups(),automatic=getattr(self.runtime_context,"backup_state",None)))
            except ValueError as error:self.send_json(dict(error=str(error)),503)
        elif parsed.path == "/api/planning":
            store = getattr(self.runtime_context, "store", None)
            if store is None:
                self.send_json(dict(error="Stockage en cours d’initialisation."), 503)
            else:
                self.send_json(read_planning(store))
        elif parsed.path in ("/api/planning/export", "/api/planning/print"):
            store = getattr(self.runtime_context, "store", None)
            if store is None:
                self.send_json(dict(error="Stockage en cours d’initialisation."), 503)
                return
            parameters = parse_qs(parsed.query)
            printing = parsed.path.endswith("/print")
            start = end = None
            layout = "list"
            if printing:
                try:
                    start = date.fromisoformat(planning_date(parameters.get("start", [None])[0]))
                    end = date.fromisoformat(planning_date(parameters.get("end", [None])[0]))
                    layout = parameters.get("layout", ["list"])[0]
                    if start > end or layout not in ("list", "calendar") or (
                            layout == "calendar" and (end - start).days >= 366):
                        raise ValueError("Période ou format incorrect. La vue calendrier accepte jusqu’à 366 jours.")
                except ValueError as error:
                    self.send_json(dict(error=str(error)), 400)
                    return
            name = parameters.get("zone", ["UTC"])[0]
            try:
                zone = ZoneInfo(name) if len(name) <= 80 else timezone.utc
            except (ValueError, ZoneInfoNotFoundError):
                try:
                    offset = max(-720, min(840, int(parameters.get("offset", ["0"])[0])))
                except ValueError:
                    offset = 0
                zone = timezone(timedelta(minutes=offset))
            plan = read_planning(store)["planning"] or {}
            references = reference_map(store, self.reference_directory, calendar=True)["courses"]
            rows, recap = report_rows(plan, references, zone, start=start, end=end)
            if not printing:
                self.reply(planning_xlsx(rows, recap, plan.get("types", [])),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           attachment="PredicTrail-planning.xlsx")
            else:
                embedded = parameters.get("embedded", [""])[0] == "1"
                self.reply(planning_print(rows, recap, str(zone), start, end, layout, embedded=embedded),
                           "text/html; charset=utf-8")
        elif parsed.path == "/api/planning/references":
            store = getattr(self.runtime_context, "store", None)
            if store is None:
                self.send_json(dict(error="Stockage en cours d’initialisation."), 503)
            else:
                self.send_json(reference_map(store, self.reference_directory, calendar=True))
        elif parsed.path=="/api/state":
            store=getattr(self.runtime_context,"store",None)
            self.send_json(dict(state=store.get_app_state()) if store else dict(error="Stockage en cours d’initialisation."),200 if store else 503)
        elif parsed.path=="/api/backup/download":
            try:
                token = parse_qs(parsed.query).get("token", [""])[0]
                path = self.backups().path(token)
                source = path.open("rb")
            except (ValueError, OSError):
                self.send_json(dict(error="Sauvegarde introuvable."), 404)
                return
            with source:
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(os.fstat(source.fileno()).st_size))
                self.send_header("Content-Disposition", f'attachment; filename="PredicTrail-{token}.zip"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                shutil.copyfileobj(source, self.wfile, 1024**2)
        elif parsed.path=="/api/source":
            key=parse_qs(parsed.query).get("id",[""])[0]
            if len(key)!=64 or any(c not in "0123456789abcdef" for c in key):self.send_json(dict(error="Parcours inconnu."),400);return
            try:self.reply((self.runtime_context.store.path.parent/"parcours-importes"/(key+".gpx")).read_bytes(),"application/gpx+xml")
            except OSError:self.send_json(dict(error="Parcours source indisponible."),404)
        elif self.path == "/":
            self.reply(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/references":
            if self.ready():
                self.send_json(self.runtime_context.references)
        elif self.path == "/api/reference-map":
            store = getattr(self.runtime_context, "store", None)
            if store is None:
                self.send_json(dict(error="Stockage en cours d’initialisation. Réessayez dans quelques instants."), 503)
            else:
                self.send_json(reference_map(store, self.reference_directory))
        elif self.path == "/api/reference-selection":
            store = getattr(self.runtime_context, "store", None)
            self.send_json(dict(references=store.reference_inventory(self.reference_directory) if store else []))
        elif self.path == "/api/runtime":
            self.send_json(dict(python=platform.python_version(), version=__version__))
        elif self.path == "/api/startup":
            startup = getattr(self.runtime_context, "startup", None)
            self.send_json(startup.snapshot() if startup else dict(status="ready", progress=1, elapsed=0))
        elif self.path == "/api/local":
            store = getattr(self.runtime_context, "store", None)
            self.send_json(dict(activities=store.list_activities() if store else []))
        elif self.path == "/api/garmin/status":
            self.send_json(self.runtime_context.garmin.status())
        elif self.path == "/api/operation":
            operation = getattr(self.runtime_context, "operation", None)
            self.send_json(operation.snapshot() if operation else dict(status="ready", message="Aucune opération"))
        elif self.path in STATIC_FILES:
            try:
                path, content_type = STATIC_FILES[self.path]
                asset = path.read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.reply(asset, content_type)
        else:
            self.send_error(404)

    def read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        path = urlsplit(self.path).path
        limit = {"/api/gpx/convert": MAX_SOURCE, "/api/local/upload": MAX_REFERENCE_BATCH,
                 "/api/state": MAX_UPLOAD*2, "/api/backup/create": MAX_UPLOAD*2}.get(path, MAX_UPLOAD)
        if self.headers.get_content_type() != "application/json" or not 0 < size <= limit * 2:
            raise ValueError("Requête JSON absente, incorrecte ou trop volumineuse.")
        value = json.loads(self.rfile.read(size))
        if not isinstance(value, dict):
            raise ValueError("Un objet JSON est attendu.")
        return value

    def do_POST(self):
        if not self.local_host():
            return
        url = urlsplit(self.path)
        try:
            # Les actions locales n'acceptent pas une origine web tierce.
            origin = self.headers.get("Origin")
            expected_origin = getattr(self.server, "origin", "http://" + self.headers.get("Host", ""))
            if origin and origin != expected_origin:
                raise ValueError("Origine de requête non autorisée.")
            if url.path=="/api/backup/inspect":
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=MAX_ARCHIVE:raise ValueError("Archive ZIP attendue, jusqu’à 2 Gio.")
                manager=self.backups();token=uuid.uuid4().hex;path=manager.path(token)
                try:
                    with path.open("wb") as target:
                        remaining=size
                        while remaining:
                            chunk=self.rfile.read(min(1024**2,remaining))
                            if not chunk:raise ValueError("Archive incomplète.")
                            target.write(chunk);remaining-=len(chunk)
                    manifest=manager.inspect(path)
                except Exception:
                    path.unlink(missing_ok=True);raise
                self.send_json(dict(token=token,version=manifest["version"],createdAt=manifest["createdAt"],files=len(manifest["files"])))
                return
            if url.path != "/api/prediction":
                self.manage(url.path, self.read_json())
                return
            parameters = parse_qs(url.query)
            mode = "model"
            waypoints = []
            if self.headers.get_content_type() == "application/json":
                options = self.read_json()
                body = base64.b64decode(options.get("gpx", ""), validate=True)
                mode = options.get("mode", "model")
                waypoints = options.get("waypoints", [])
                interval = int(options.get("interval", 5))
                choice = options.get("model", "auto")
            else:
                options = {}
                size = int(self.headers.get("Content-Length", "0"))
                if self.headers.get_content_type() != "application/gpx+xml" or not 0 < size <= MAX_UPLOAD:
                    raise ValueError("Format GPX attendu, jusqu'à 20 Mo.")
                body = self.rfile.read(size)
                interval = int(parameters.get("pas-km", ["5"])[0])
                choice = parameters.get("model", ["auto"])[0]
            if not 1 <= interval <= 50 or not body or len(body) > MAX_UPLOAD:
                raise ValueError("Vérifiez le GPX (20 Mo maximum) et l'espacement des repères (1 à 50 km).")
            if not isinstance(waypoints, list) or any(not isinstance(item, dict) for item in waypoints):
                raise ValueError("Liste de repères incorrecte.")
            if mode == "model" and not self.ready():
                return
            if mode == "recorded":
                try:
                    course = read_gpx(BytesIO(body), timed=True)
                except ValueError as error:
                    raise ValueError("Comparaison sans prédiction : un GPX avec altitudes et horodatages ordonnés est requis. " + str(error)) from error
                if options.get("strategy") is not None:
                    raise ValueError("Choisissez une méthode de simulation pour appliquer une stratégie aux temps estimés.")
                self.send_prediction(recorded_run(course, interval * 1000),body,options)
                return
            course = read_gpx(BytesIO(body))
            bank, references = getattr(self.runtime_context, "runtime",
                (getattr(self.runtime_context, "model", None), getattr(self.runtime_context, "references", None)))
            if mode == "model":
                model = choose_model(bank, course, choice)
            else:
                model = manual_model(course, mode, options.get("totalSeconds"), options.get("paceSeconds"))
            sampling = model.metadata.get("sampling", describe_course(course)["sampling"])
            course = resample_course(course, sampling, preserve_turns=True)
            marks = predict(course, model, interval * 1000, waypoints)
            total = marks[-1][1]
            pauses = (estimate_pauses(total, model, references["courses"]) if mode == "model" else
                      dict(duration=None, fraction=None, referenceCount=0, unknownFraction=0,
                           status="Mode manuel · pauses incluses dans la durée ou l'allure saisie"))
            result = dict(**summarize(course), trace=geometry(course),
                                marks=marks, duration=total, pauses=pauses,
                                exportPoints=export_points(course, model),
                                customWaypoints=waypoints,
                                movingDuration=total - pauses["duration"] if pauses["duration"] is not None else None,
                                classification=dict(describe_course(course), sampling=sampling),
                                model=model_summary(bank.courses if bank else [], model),
                                sections=predicted_sections(course, model),
                                terrain=terrain_breakdown(course, model))
            if options.get("strategy") is not None:
                result = apply_strategy(result, options["strategy"])
            self.send_prediction(result,body,options)
        except (ValueError, KeyError, TypeError, ParseError, OverflowError, binascii.Error, zipfile.BadZipFile, OSError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, 400)

    def manage(self, path, options):
        if path in ("/api/planning", "/api/planning/trace"):
            store = getattr(self.runtime_context, "store", None)
            if store is None:
                self.send_json(dict(error="Stockage en cours d’initialisation."), 503)
                return
            if not self.runtime_context.update_lock.acquire(blocking=False):
                self.send_json(dict(error="Une mise à jour est en cours. Réessayez ensuite."), 409)
                return
            try:
                if path == "/api/planning/trace":
                    body = base64.b64decode(options.get("gpx", ""), validate=True)
                    if len(body) > MAX_UPLOAD:
                        raise ValueError("Trace GPX limitée à 20 Mio après conversion.")
                    checked, _ = convert_gpx(body, "original")
                    self.send_json(dict(sourceId=self.retain_gpx(store, checked)))
                else:
                    result = save_planning(store, options)
                    if result is None:
                        self.send_json(dict(error="Le planning a changé sur un autre écran. Rechargez-le avant de poursuivre."), 409)
                    else:
                        self.send_json(result)
            finally:
                self.runtime_context.update_lock.release()
        elif path=="/api/state":
            if not self.runtime_context.update_lock.acquire(blocking=False):raise ValueError("Une mise à jour est en cours. Réessayez après sa fin.")
            try:self.runtime_context.store.save_app_state(options.get("state"));self.send_json(dict(saved=True))
            finally:self.runtime_context.update_lock.release()
        elif path=="/api/backup/create":
            if not self.runtime_context.update_lock.acquire(blocking=False):raise ValueError("Une mise à jour est en cours. Réessayez après sa fin.")
            try:
                self.runtime_context.store.save_app_state(options.get("state"))
                report=self.backups().create();report["url"]="/api/backup/download?token="+report["token"]
                self.send_json(report)
            finally:self.runtime_context.update_lock.release()
        elif path=="/api/backup/restore":
            token=options.get("token");manager=self.backups();manager.path(token)
            def restore(progress):
                report=manager.restore(token)
                progress("restauration","Données restaurées · reconstruction des modèles",1)
                return report
            start_update(self.runtime_context,restore,kind="restore")
            self.send_json(dict(accepted=True),202)
        elif path in ("/api/gpx/convert", "/api/reference-gpx"):
            if path == "/api/reference-gpx":
                store = getattr(self.runtime_context, "store", None)
                if store is None:
                    self.send_json(dict(error="Stockage en cours d’initialisation."), 503)
                    return
                body = store.read_reference_gpx(options.get("key"), self.reference_directory, MAX_SOURCE)
            else:
                body = base64.b64decode(options.get("gpx", ""), validate=True)
            converted, report = convert_gpx(body, options.get("mode", "compact"))
            response = dict(gpx=base64.b64encode(converted).decode("ascii"), report=report)
            if options.get("preview"):
                source = read_gpx(BytesIO(body))
                preview = dict(**summarize(source), trace=geometry(source),
                    classification=describe_course(source), duration=0, sections=recorded_sections(source),
                    exportPoints=[[[*p[:3], 0] for p in points] for _, points, _ in source])
                if report["recordedCompatible"]:
                    preview = recorded_run(read_gpx(BytesIO(body), timed=True), 5000)
                response["preview"] = preview
            self.send_json(response)
        elif path == "/api/garmin/connect":
            self.send_json(self.runtime_context.garmin.connect(options.get("email"), options.get("password")))
        elif path == "/api/garmin/mfa":
            self.send_json(self.runtime_context.garmin.complete_mfa(options.get("code", "")))
        elif path == "/api/garmin/disconnect":
            self.send_json(self.runtime_context.garmin.disconnect())
        elif path == "/api/references/refresh":
            start_update(self.runtime_context)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/reference-selection":
            key, enabled = str(options.get("key", "")), options.get("enabled")
            if not isinstance(enabled, bool):
                raise ValueError("Sélection incorrecte.")
            def select(progress):
                self.runtime_context.store.select_reference(key, enabled, self.reference_directory)
                return dict(updated=True)
            start_update(self.runtime_context, select)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/local/upload":
            files = options.get("files", [options])
            if not isinstance(files, list) or not 1 <= len(files) <= MAX_REFERENCE_FILES:
                raise ValueError("Sélectionnez entre 1 et 20 GPX.")
            if any(not isinstance(file, dict) or not isinstance(file.get("gpx"), str) for file in files):
                raise ValueError("Lot de GPX incorrect.")
            if sum(len(file["gpx"]) for file in files) > MAX_REFERENCE_BATCH * 4 // 3:
                raise ValueError("Le lot de références est limité à 60 Mio après conversion.")
            def upload(progress):
                report = dict(imported=0, existing=0, errors=[])
                for index, file in enumerate(files):
                    name = str(file.get("name") or "Course importée")[:200]
                    progress("import", name, index / len(files), index, len(files))
                    try:
                        body = base64.b64decode(file["gpx"], validate=True)
                        if not body or len(body) > MAX_UPLOAD:
                            raise ValueError("Fichier GPX absent ou trop volumineux.")
                        course = read_gpx(BytesIO(body), timed=True)
                        if elapsed(course) <= 0:
                            raise ValueError("La référence doit être chronométrée.")
                        descriptor = describe_course(course)
                        activity = dict(id="local-" + digest(body), source="gpx", name=name, kind="running",
                            date=datetime.fromtimestamp(course[0][1][0][3]).date().isoformat(),
                            distance=descriptor["distance"], reference=True)
                        saved = self.runtime_context.store.save_activity(activity, body, descriptor)
                        report["imported" if saved else "existing"] += 1
                    except (ValueError, KeyError, TypeError, ParseError, OverflowError, binascii.Error, OSError, sqlite3.Error) as error:
                        report["errors"].append(name + " · " + str(error))
                return report
            start_update(self.runtime_context, upload)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/local/reference":
            activity_id = str(options.get("id", ""))
            value = options.get("reference")
            if not isinstance(value, bool):
                raise ValueError("Choisissez si cette activité sert de référence.")
            def reference(progress):
                self.runtime_context.store.set_reference(activity_id, value)
                return dict(updated=True)
            start_update(self.runtime_context, reference)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/local/delete":
            if options.get("scope") not in ("all", "matching"):
                raise ValueError("Précisez la suppression de tous les imports ou des résultats filtrés.")
            filters = validate_filters(options.get("filters", {})) if options["scope"] == "matching" else None
            def remove(progress):
                return dict(deleted=self.runtime_context.store.delete_activities(filters))
            start_update(self.runtime_context, remove)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/garmin/stop":
            operation = getattr(self.runtime_context, "operation", None)
            if operation and operation.snapshot().get("kind") == "garmin" and operation.snapshot()["status"] == "loading":
                operation.cancel_event.set()
                self.send_json(dict(stopping=True, message="Arrêt demandé. La requête réseau en cours doit se terminer ; les imports déjà enregistrés sont conservés."))
            else:
                self.send_json(dict(stopping=False, message="Aucun import Garmin à interrompre."))
        elif path == "/api/garmin/import":
            filters = validate_filters(options.get("filters", {}))
            use_running = options.get("useRunning", True)
            if not isinstance(use_running, bool):
                raise ValueError("Option de référence incorrecte.")
            def download(progress):
                return self.runtime_context.garmin.import_activities(self.runtime_context.store, filters, use_running, progress, self.runtime_context.operation.cancel_event)
            start_update(self.runtime_context, download, kind="garmin")
            self.send_json(dict(accepted=True), 202)
        else:
            self.send_json(dict(error="Action inconnue."), 404)


def initialize(server, operation=None):
    """Restaurer un instantané cohérent ou recalculer les références modifiées."""
    def progress(phase, message, value, completed=0, total=0):
        server.startup.update(phase, message, value, completed, total)
        if operation:
            operation.update(phase, message, 0.5 + value * 0.5, completed, total, log=False)
    directory = getattr(server, "reference_directory", REFERENCES)
    try:
        if hasattr(server, "store"):
            if server.store is None:
                server.store = Store()
            sources = server.store.reference_sources(directory)
            if getattr(server, "hosted", False) and not sources:
                server.references = server.model = None
                server.runtime = (None, None)
                progress("empty", "Ajoutez une référence GPX chronométrée pour entraîner votre modèle.", 1)
                return
            fingerprint = server.store.manifest(sources)
            restored = server.store.load_models(fingerprint)
            if restored:
                model, references = restored
                cache = dict(restored=True, reused=len(sources), total=len(sources))
                progress("cache", "Références et modèles restaurés depuis le stockage local", 0.95)
            else:
                names, courses, pauses, skipped, cache = read_references(progress, server.store, directory=directory)
                fingerprint = cache["fingerprint"]
                restored = server.store.load_models(fingerprint)
                if restored:
                    model, references = restored
                    cache["restored"] = True
                else:
                    arguments = (names, courses, pauses, skipped)
                    model, references = (supervised_build(arguments, progress)
                        if getattr(server, "validation_isolated", False) else build_models(*arguments, progress))
                    cache["restored"] = False
                if fingerprint and server.store.manifest(server.store.reference_sources(directory)) != fingerprint:
                    raise ValueError("Références modifiées pendant le calcul. Relancez l'actualisation.")
                if fingerprint and not restored:
                    server.store.save_models(fingerprint, (model, references))
            references["cache"] = cache
        else:
            # Interface conservée pour les tests et usages directs sans cache.
            courses, references = load_references(progress)
            model = fit(courses)
            references["model"] = model_summary(courses, model.global_model)
            references["models"] = model_catalog(model, references["courses"], progress)
            references["inclinationModel"] = model_summary(courses, model.inclination_model())
        server.references, server.model = references, model
        server.runtime = (model, references)
        progress("ready", "Application prête", 1)
        if getattr(server,"backup_auto_enabled",False):
            def automatic_backup():
                with server.update_lock:
                    manager=Backups(server.store,directory)
                    marker=manager.directory/("automatique-"+datetime.now().strftime("%Y%m%d")+".json")
                    if marker.exists():return
                    try:
                        server.backup_state=dict(status="loading",message="Sauvegarde automatique locale en cours.")
                        report=manager.create("automatique")
                        marker.write_text(json.dumps(report),encoding="utf-8")
                        server.backup_state=dict(status="ready",message="Sauvegarde automatique locale créée.")
                    except Exception as error:server.backup_state=dict(status="error",message="Sauvegarde automatique impossible : "+str(error))
            Thread(target=automatic_backup,daemon=True).start()
    except Exception as error:
        server.references = server.model = None
        server.runtime = (None, None)
        progress("error", f"Échec du démarrage · {error}", server.startup.snapshot()["progress"])


def start_update(server, work=None, kind="update"):
    """Sérialiser imports, suppressions et publication d'un nouvel instantané."""
    if not server.update_lock.acquire(blocking=False):
        raise ValueError("Une importation ou une mise à jour est déjà en cours.")
    slots = getattr(server, "compute_slots", None)
    if slots is not None and not slots.acquire(blocking=False):
        server.update_lock.release()
        raise ValueError("Le serveur traite déjà deux mises à jour. Réessayez dans quelques instants.")
    operation = StartupStatus()
    operation.cancel_event = Event()
    operation.state["kind"] = kind
    operation.state["initial"] = work is None and getattr(server, "model", None) is None
    server.operation = operation

    def run():
        report = {}
        failure = None
        try:
            if work:
                report = work(lambda phase, message, value, completed=0, total=0:
                    operation.update(phase, message, value * 0.5, completed, total))
        except Exception as error:
            failure = str(error)
        try:
            # Recalculer aussi après un import partiel interrompu.
            server.startup = StartupStatus()
            initialize(server, operation)
            report_model_counts = getattr(server, "report_model_counts", None)
            if report_model_counts is not None:
                status = server.startup.snapshot()["status"]
                references = server.references if status == "ready" else None
                try:
                    report_model_counts(references, empty=status == "empty")
                except sqlite3.Error as error:
                    print(f"Statistiques du modèle indisponibles : {error}", flush=True)
            with operation.lock:
                operation.state["result"] = report
            if failure or server.startup.snapshot()["status"] == "error":
                operation.update("error", failure or server.startup.snapshot()["message"], 1)
            else:
                operation.update("ready", "Mise à jour terminée", 1)
        finally:
            if slots is not None:
                slots.release()
            server.update_lock.release()
    try:
        Thread(target=run, daemon=True).start()
    except RuntimeError:
        if slots is not None:
            slots.release()
        server.update_lock.release()
        raise


def main():
    """Démarrer le serveur, puis entraîner les modèles dans un fil de travail."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    with ThreadingHTTPServer((HOST, PORT), Dashboard) as server:
        server.startup = StartupStatus()
        print(f"Tableau de bord : http://{HOST}:{PORT} · suivi du démarrage disponible", flush=True)
        server.backup_auto_enabled = os.environ.get("PREDICTRAIL_NO_AUTO_BACKUP") != "1"
        server.validation_isolated = True
        server.store = None
        server.model = server.references = None
        server.runtime = (None, None)
        server.update_lock = Lock()
        server.garmin = GarminConnection()
        start_update(server)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
