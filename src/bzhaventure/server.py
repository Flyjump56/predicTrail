"""Serveur HTTP local et initialisation asynchrone avec suivi d'avancement."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import base64
import binascii
from datetime import datetime
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


# Liste fermée des ressources servies par HTTP.
STATIC_FILES = {
    "/assets/logo-bzhaventure.png": (LOGO, "image/png"),
    "/assets/theme.jpg": (LOGO.parent / "thème.jpg", "image/jpeg"),
    "/assets/styles.css": (WEB_DIR / "styles.css", "text/css; charset=utf-8"),
    "/assets/backup.js": (WEB_DIR / "backup.js", "text/javascript; charset=utf-8"),
    "/assets/app.js": (WEB_DIR / "app.js", "text/javascript; charset=utf-8"),
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
            if phase in ("ready", "error"):
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
    def log_request(self, code="-", size="-"):
        if self.path != "/api/startup":
            super().log_request(code, size)

    def reply(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload, status=200):
        self.reply(json.dumps(payload).encode("utf-8"), "application/json", status)

    def ready(self):
        """Répondre 503 tant que les modèles complets ne sont pas publiés."""
        startup = getattr(self.server, "startup", None)
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

    def send_prediction(self,payload,body,options):
        store=getattr(self.server,"store",None)
        if store and options.get("retainSource"):
            key=digest(body);directory=store.path.parent/"parcours-importes";directory.mkdir(exist_ok=True)
            path=directory/(key+".gpx")
            if not path.exists():
                temporary=directory/(uuid.uuid4().hex+".tmp");temporary.write_bytes(body);temporary.replace(path)
            payload["sourceId"]=key
        self.send_json(payload)

    def backups(self):
        store=getattr(self.server,"store",None)
        if store is None:raise ValueError("Stockage en cours d’initialisation.")
        return Backups(store,REFERENCES)

    def do_GET(self):
        if not self.local_host():
            return
        parsed=urlsplit(self.path)
        if parsed.path=="/api/backup/list":
            try:self.send_json(dict(backups=self.backups().list_backups(),automatic=getattr(self.server,"backup_state",None)))
            except ValueError as error:self.send_json(dict(error=str(error)),503)
        elif parsed.path=="/api/state":
            store=getattr(self.server,"store",None)
            self.send_json(dict(state=store.get_app_state()) if store else dict(error="Stockage en cours d’initialisation."),200 if store else 503)
        elif parsed.path=="/api/backup/download":
            try:
                token=parse_qs(parsed.query).get("token",[""])[0];path=self.backups().path(token)
                self.send_response(200);self.send_header("Content-Type","application/zip")
                self.send_header("Content-Length",str(path.stat().st_size));self.send_header("Content-Disposition",'attachment; filename="PredicTrail-'+token+'.zip"');self.end_headers()
                with path.open("rb") as source:shutil.copyfileobj(source,self.wfile,1024**2)
            except (ValueError,OSError) as error:self.send_json(dict(error=str(error)),400)
        elif parsed.path=="/api/source":
            key=parse_qs(parsed.query).get("id",[""])[0]
            if len(key)!=64 or any(c not in "0123456789abcdef" for c in key):self.send_json(dict(error="Parcours inconnu."),400);return
            try:self.reply((self.server.store.path.parent/"parcours-importes"/(key+".gpx")).read_bytes(),"application/gpx+xml")
            except OSError:self.send_json(dict(error="Parcours source indisponible."),404)
        elif self.path == "/":
            self.reply(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/references":
            if self.ready():
                self.send_json(self.server.references)
        elif self.path == "/api/reference-map":
            store = getattr(self.server, "store", None)
            if store is None:
                self.send_json(dict(error="Stockage en cours d’initialisation. Réessayez dans quelques instants."), 503)
            else:
                self.send_json(reference_map(store, REFERENCES))
        elif self.path == "/api/reference-selection":
            store = getattr(self.server, "store", None)
            self.send_json(dict(references=store.reference_inventory(REFERENCES) if store else []))
        elif self.path == "/api/runtime":
            self.send_json(dict(python=platform.python_version(), version=__version__))
        elif self.path == "/api/startup":
            startup = getattr(self.server, "startup", None)
            self.send_json(startup.snapshot() if startup else dict(status="ready", progress=1, elapsed=0))
        elif self.path == "/api/local":
            store = getattr(self.server, "store", None)
            self.send_json(dict(activities=store.list_activities() if store else []))
        elif self.path == "/api/garmin/status":
            self.send_json(self.server.garmin.status())
        elif self.path == "/api/operation":
            operation = getattr(self.server, "operation", None)
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
        limit = MAX_SOURCE if urlsplit(self.path).path == "/api/gpx/convert" else (MAX_UPLOAD*2 if urlsplit(self.path).path in ("/api/state","/api/backup/create") else MAX_UPLOAD)
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
            if origin and origin != "http://" + self.headers.get("Host", ""):
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
            bank, references = getattr(self.server, "runtime",
                (getattr(self.server, "model", None), getattr(self.server, "references", None)))
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
        if path=="/api/state":
            if not self.server.update_lock.acquire(blocking=False):raise ValueError("Une mise à jour est en cours. Réessayez après sa fin.")
            try:self.server.store.save_app_state(options.get("state"));self.send_json(dict(saved=True))
            finally:self.server.update_lock.release()
        elif path=="/api/backup/create":
            if not self.server.update_lock.acquire(blocking=False):raise ValueError("Une mise à jour est en cours. Réessayez après sa fin.")
            try:
                self.server.store.save_app_state(options.get("state"))
                report=self.backups().create();report["url"]="/api/backup/download?token="+report["token"]
                self.send_json(report)
            finally:self.server.update_lock.release()
        elif path=="/api/backup/restore":
            token=options.get("token");manager=self.backups();manager.path(token)
            def restore(progress):
                report=manager.restore(token)
                progress("restauration","Données restaurées · reconstruction des modèles",1)
                return report
            start_update(self.server,restore,kind="restore")
            self.send_json(dict(accepted=True),202)
        elif path == "/api/gpx/convert":
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
            self.send_json(self.server.garmin.connect(options.get("email"), options.get("password")))
        elif path == "/api/garmin/mfa":
            self.send_json(self.server.garmin.complete_mfa(options.get("code", "")))
        elif path == "/api/garmin/disconnect":
            self.send_json(self.server.garmin.disconnect())
        elif path == "/api/references/refresh":
            start_update(self.server)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/reference-selection":
            key, enabled = str(options.get("key", "")), options.get("enabled")
            if not isinstance(enabled, bool):
                raise ValueError("Sélection incorrecte.")
            def select(progress):
                self.server.store.select_reference(key, enabled, REFERENCES)
                return dict(updated=True)
            start_update(self.server, select)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/local/upload":
            body = base64.b64decode(options.get("gpx", ""), validate=True)
            if not body or len(body) > MAX_UPLOAD:
                raise ValueError("Fichier GPX absent ou trop volumineux.")
            course = read_gpx(BytesIO(body), timed=True)
            if elapsed(course) <= 0:
                raise ValueError("La référence doit être chronométrée.")
            name = str(options.get("name") or "Course importée")[:200]
            activity = dict(id="local-" + digest(body), source="gpx", name=name, kind="running",
                date=datetime.fromtimestamp(course[0][1][0][3]).date().isoformat(),
                distance=describe_course(course)["distance"], reference=True)
            def upload(progress):
                return dict(imported=int(self.server.store.save_activity(activity, body, describe_course(course))))
            start_update(self.server, upload)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/local/reference":
            activity_id = str(options.get("id", ""))
            value = options.get("reference")
            if not isinstance(value, bool):
                raise ValueError("Choisissez si cette activité sert de référence.")
            def reference(progress):
                self.server.store.set_reference(activity_id, value)
                return dict(updated=True)
            start_update(self.server, reference)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/local/delete":
            if options.get("scope") not in ("all", "matching"):
                raise ValueError("Précisez la suppression de tous les imports ou des résultats filtrés.")
            filters = validate_filters(options.get("filters", {})) if options["scope"] == "matching" else None
            def remove(progress):
                return dict(deleted=self.server.store.delete_activities(filters))
            start_update(self.server, remove)
            self.send_json(dict(accepted=True), 202)
        elif path == "/api/garmin/stop":
            operation = getattr(self.server, "operation", None)
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
                return self.server.garmin.import_activities(self.server.store, filters, use_running, progress, self.server.operation.cancel_event)
            start_update(self.server, download, kind="garmin")
            self.send_json(dict(accepted=True), 202)
        else:
            self.send_json(dict(error="Action inconnue."), 404)


def initialize(server, operation=None):
    """Restaurer un instantané cohérent ou recalculer les références modifiées."""
    def progress(phase, message, value, completed=0, total=0):
        server.startup.update(phase, message, value, completed, total)
        if operation:
            operation.update(phase, message, 0.5 + value * 0.5, completed, total, log=False)
    try:
        if hasattr(server, "store"):
            if server.store is None:
                server.store = Store()
            sources = server.store.reference_sources(REFERENCES)
            fingerprint = server.store.manifest(sources)
            restored = server.store.load_models(fingerprint)
            if restored:
                model, references = restored
                cache = dict(restored=True, reused=len(sources), total=len(sources))
                progress("cache", "Références et modèles restaurés depuis le stockage local", 0.95)
            else:
                names, courses, pauses, skipped, cache = read_references(progress, server.store)
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
                if fingerprint and server.store.manifest(server.store.reference_sources(REFERENCES)) != fingerprint:
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
                    manager=Backups(server.store,REFERENCES)
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
            with operation.lock:
                operation.state["result"] = report
            if failure or server.startup.snapshot()["status"] == "error":
                operation.update("error", failure or server.startup.snapshot()["message"], 1)
            else:
                operation.update("ready", "Mise à jour terminée", 1)
        finally:
            server.update_lock.release()
    Thread(target=run, daemon=True).start()


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
