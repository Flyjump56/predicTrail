"""Import personnel Garmin Connect via le connecteur communautaire facultatif."""
from datetime import date
import hashlib
import json
import platform
from importlib.util import find_spec
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from math import isfinite
from threading import Event, RLock
import sys

from .gpx import describe_course, elapsed, read_gpx
from .storage import matches


def normalize_activity(activity):
    key = str(activity.get("activityType", {}).get("typeKey", "")).lower()
    if "running" in key:
        kind = "running"
    elif "cycling" in key or "biking" in key or "bike" in key:
        kind = "cycling"
    elif "hiking" in key or "walking" in key or "mountaineering" in key:
        kind = "hiking"
    else:
        return None
    when = str(activity.get("startTimeLocal") or activity.get("startTimeGMT") or "")[:10]
    date.fromisoformat(when)
    activity_id = int(activity["activityId"])
    meters = float(activity.get("distance") or 0)
    if activity_id <= 0 or not isfinite(meters) or meters < 0:
        raise ValueError("Identifiant ou distance Garmin incorrecte.")
    version_data = {key: activity.get(key) for key in (
        "activityName", "activityType", "startTimeLocal", "distance", "duration",
        "movingDuration", "elevationGain", "lastModifiedDate", "lastUpdatedTimestamp")}
    revision = hashlib.sha256(json.dumps(version_data, sort_keys=True).encode()).hexdigest()
    return dict(id=str(activity_id), name=str(activity.get("activityName") or "Activité Garmin"),
                kind=kind, date=when, distance=meters, revision=revision)


class GarminConnection:
    def __init__(self, factory=None):
        self.factory = factory
        self.lock = RLock()
        self.client = None
        self.pending = None
        self.account = None

    def status(self):
        installed = None
        try:
            installed = version("garminconnect")
        except PackageNotFoundError:
            pass
        if sys.version_info < (3, 10):
            message = "Python " + platform.python_version() + " trop ancien pour Garmin. Lancez Demarrer-BZHAventure.cmd avec l’environnement du projet."
        elif installed is None or find_spec("garminconnect") is None:
            message = "Connecteur Garmin absent de ce Python. Lancez Demarrer-BZHAventure.cmd, qui utilise les dépendances du projet."
        elif installed != "0.2.38":
            message = "Version Garmin incompatible : " + installed + ". La version attendue est 0.2.38."
        else:
            message = "Connecteur prêt"
            try:
                from garminconnect import Garmin  # noqa: F401 — vérifier aussi les dépendances transitives.
            except Exception:
                message = "Le connecteur Garmin est installé mais ses dépendances ne se chargent pas. Réinstallez requirements-garmin.txt dans l’environnement du projet."
        available = self.factory is not None or message == "Connecteur prêt"
        if self.factory is not None:
            message = "Connecteur prêt"
        return dict(available=available, connected=self.client is not None and self.pending is None,
                    mfa=self.pending is not None,
                    python=platform.python_version(), connectorVersion=installed, message=message)

    @staticmethod
    def connection_error(error):
        """Décrire la cause sans afficher réponse distante, identifiants ou jetons."""
        response = getattr(error, "response", None)
        if response is None:
            response = getattr(getattr(error, "error", None), "response", None)
        status = getattr(response, "status_code", None)
        name = type(error).__name__
        if status == 429 or name == "GarminConnectTooManyRequestsError":
            return "Garmin limite les tentatives de connexion. Attendez avant de réessayer."
        if status == 401 or name == "GarminConnectAuthenticationError":
            return "Garmin a refusé l’authentification. Vérifiez vos identifiants sur Garmin Connect."
        if status == 403:
            return "Garmin bloque cette connexion (HTTP 403). Vérifiez l’accès à votre compte sur le site Garmin Connect."
        if "Timeout" in name:
            return "Garmin ne répond pas dans le délai prévu. Réessayez plus tard."
        if "SSLError" in name:
            return "La connexion sécurisée à Garmin a échoué. Vérifiez les certificats et la configuration réseau."
        if "ConnectionError" in name:
            return "Connexion réseau à Garmin impossible. Vérifiez Internet, le proxy ou le VPN."
        return "Connexion Garmin échouée (" + name + "). Vérifiez vos identifiants sur Garmin Connect ou réessayez plus tard."

    def connect(self, email, password):
        if not email or not password:
            raise ValueError("Saisissez votre adresse et votre mot de passe Garmin.")
        if not self.status()["available"]:
            raise ValueError(self.status()["message"])
        if self.factory is None:
            from garminconnect import Garmin
            factory = Garmin
        else:
            factory = self.factory
        with self.lock:
            self.client = None
            self.pending = None
            self.account = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:20]
            client = None
            try:
                client = factory(email=email.strip(), password=password, return_on_mfa=True)
                # Flux explicite en mémoire, sans lecture ni sauvegarde de jetons sur disque.
                result, state = client.garth.login(email, password, return_on_mfa=True)
                self.client = client
                self.pending = state if result == "needs_mfa" else None
            except Exception as error:
                self.client = None
                self.pending = None
                self.account = None
                raise ValueError(self.connection_error(error)) from None
            finally:
                if client is not None:
                    client.password = None
        return self.status()

    def complete_mfa(self, code):
        with self.lock:
            if self.client is None or self.pending is None:
                raise ValueError("Aucune validation Garmin en attente.")
            try:
                self.client.resume_login(self.pending, str(code).strip())
            except Exception:
                raise ValueError("Code Garmin refusé ou expiré. Réessayez la connexion.") from None
            self.pending = None
        return self.status()

    def disconnect(self):
        with self.lock:
            self.client = self.pending = self.account = None
        return self.status()

    def read_activity_list(self, filters, progress, cancel_event):
        # Même API paginée que le connecteur, avec contrôle d’arrêt entre les pages.
        if cancel_event.is_set():
            return []
        if not hasattr(self.client, "connectapi"):
            return self.client.get_activities_by_date(filters["minDate"] or "1970-01-01",
                filters["maxDate"] or date.today().isoformat(), activitytype=None)
        result, start, previous_page = [], 0, None
        while not cancel_event.is_set():
            progress("import", f"Lecture Garmin · {len(result)} activités reçues", 0)
            page = self.client.connectapi(self.client.garmin_connect_activities, params=dict(
                startDate=filters["minDate"] or "1970-01-01",
                endDate=filters["maxDate"] or date.today().isoformat(), start=str(start), limit="20"))
            if cancel_event.is_set() or not page:
                break
            signature = tuple(item.get("activityId") for item in page)
            if signature == previous_page:
                raise ValueError("Garmin renvoie plusieurs fois la même page d’activités.")
            previous_page = signature
            result.extend(page)
            start += 20
        return result

    def import_activities(self, store, filters, use_running, progress, cancel_event=None):
        cancel_event = cancel_event if cancel_event is not None else Event()
        with self.lock:
            if self.client is None or self.pending is not None:
                raise ValueError("Connectez votre compte Garmin avant l'import.")
            try:
                progress("import", "Lecture de la liste des activités Garmin", 0)
                activities = self.read_activity_list(filters, progress, cancel_event)
            except Exception:
                raise ValueError("Lecture Garmin impossible. La session peut avoir expiré ou la limite de requêtes être atteinte.") from None
            selected, selection_errors = [], []
            for item in activities:
                if cancel_event.is_set():
                    break
                try:
                    normalized = normalize_activity(item)
                    if normalized and matches(normalized, filters, include_morphology=False):
                        selected.append(normalized)
                except (ValueError, KeyError, TypeError, AttributeError):
                    selection_errors.append("Activité Garmin sans métadonnées exploitables")
            report = dict(imported=0, existing=0, errors=selection_errors, selected=len(selected), filtered=0)
            existing = {row["id"]: row for row in store.list_activities()}
            for i, activity in enumerate(selected):
                if cancel_event.is_set():
                    break
                progress("import", activity["name"], i / max(1, len(selected)), i, len(selected))
                activity["id"] = "garmin-" + self.account + "-" + activity["id"]
                if activity["id"] in existing and existing[activity["id"]]["revision"] == activity["revision"]:
                    report["existing" if matches(existing[activity["id"]],filters) else "filtered"] += 1
                    continue
                remote_id = activity["id"].rsplit("-", 1)[-1]
                try:
                    data = self.client.download_activity(
                        remote_id, dl_fmt=self.client.ActivityDownloadFormat.GPX)
                    if cancel_event.is_set():
                        break
                    course = read_gpx(BytesIO(data), timed=True)
                    if elapsed(course) <= 0:
                        raise ValueError("Horodatages inutilisables")
                    descriptor = describe_course(course)
                    if cancel_event.is_set():
                        break
                    activity.update(profile=descriptor['profile'],distanceClass=descriptor['distanceClass'])
                    if not matches(activity,filters):
                        report['filtered'] += 1
                        continue
                    activity.update(source="garmin",
                                    reference=bool(use_running and activity["kind"] == "running"))
                    # Le filtre kilométrique s'applique aux distances Garmin, déjà sélectionnées.
                    report["imported" if store.save_activity(activity, data, descriptor) else "existing"] += 1
                except Exception as error:
                    report["errors"].append(activity["name"] + " · GPX horodaté indisponible ou téléchargement échoué")
                    if type(error).__name__ in ("GarminConnectTooManyRequestsError", "GarminConnectAuthenticationError"):
                        break
            report["cancelled"] = cancel_event.is_set()
            return report
