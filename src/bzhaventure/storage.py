"""Stockage transactionnel des imports et caches locaux de la version 1.1."""
from contextlib import contextmanager
from datetime import date
import hashlib
from io import BytesIO
import json
from math import isfinite
from pathlib import Path
import pickle
import sqlite3
import sys
from xml.etree.ElementTree import ParseError

from .settings import DATABASE, DISTANCE_CLASSES, PROFILE_LABELS


def digest(data):
    return hashlib.sha256(data).hexdigest()


class CacheUnpickler(pickle.Unpickler):
    """Limiter les classes désérialisables aux représentations de l'application."""
    def find_class(self, module, name):
        allowed = {
            ("bzhaventure.gpx", "Course"),
            ("bzhaventure.models", "PaceModel"),
            ("bzhaventure.models", "InclinationModel"),
            ("bzhaventure.models", "SegmentedModel"),
        }
        if (module, name) not in allowed:
            raise pickle.UnpicklingError("Type de cache inconnu.")
        return super().find_class(module, name)


def decode(payload, checksum):
    if digest(payload) != checksum:
        raise ValueError("Cache incomplet ou endommagé.")
    return CacheUnpickler(BytesIO(payload)).load()


def calculation_version():
    """Invalider les caches si le code de calcul ou la version Python change."""
    root = Path(__file__).parent
    data = b"".join((root / name).read_bytes() for name in
                    ("gpx.py", "models.py", "prediction.py", "analysis.py", "settings.py", "storage.py"))
    return digest(data + str(sys.version_info[:2]).encode())


def validate_filters(data):
    kind = data.get("kind", "all")
    if kind not in ("all", "running", "cycling", "hiking"):
        raise ValueError("Type d'activité inconnu.")
    result = dict(kind=kind)
    for key,allowed in (('profile',PROFILE_LABELS),('distanceClass',{row[0] for row in DISTANCE_CLASSES})):
        value = data.get(key) or 'all'
        if value != 'all' and value not in allowed:
            raise ValueError('Profil ou classe de distance inconnu.')
        result[key] = value
    for key in ("minKm", "maxKm"):
        raw = data.get(key)
        value = None if raw in (None, "") else float(raw)
        if value is not None and (not isfinite(value) or value < 0):
            raise ValueError("Les limites kilométriques doivent être positives.")
        result[key] = value
    for key in ("minDate", "maxDate"):
        raw = data.get(key)
        result[key] = date.fromisoformat(raw).isoformat() if raw else None
    if result["minKm"] is not None and result["maxKm"] is not None and result["minKm"] > result["maxKm"]:
        raise ValueError("La distance minimale dépasse la distance maximale.")
    if result["minDate"] and result["maxDate"] and result["minDate"] > result["maxDate"]:
        raise ValueError("La date minimale dépasse la date maximale.")
    return result


def matches(activity, filters, include_morphology=True):
    return ((filters["kind"] == "all" or activity["kind"] == filters["kind"]) and
            (filters["minKm"] is None or activity["distance"] >= filters["minKm"] * 1000) and
            (filters["maxKm"] is None or activity["distance"] <= filters["maxKm"] * 1000) and
            (not filters["minDate"] or activity["date"] >= filters["minDate"]) and
            (not filters["maxDate"] or activity["date"] <= filters["maxDate"]) and
            (not include_morphology or filters.get('profile','all') == 'all' or activity.get('profile') == filters['profile']) and
            (not include_morphology or filters.get('distanceClass','all') == 'all' or activity.get('distanceClass') == filters['distanceClass']))


class Store:
    def __init__(self, path=DATABASE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.version = calculation_version()
        root = Path(__file__).parent
        self.profile_version = digest((root/'gpx.py').read_bytes()+(root/'settings.py').read_bytes())
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reference_selection (key TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS reference_cache (
                    key TEXT PRIMARY KEY, signature TEXT, digest TEXT, version TEXT,
                    payload BLOB, checksum TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS model_cache (
                    fingerprint TEXT PRIMARY KEY, payload BLOB, checksum TEXT
                );
                CREATE TABLE IF NOT EXISTS activities (
                    id TEXT PRIMARY KEY, source TEXT, name TEXT, kind TEXT, date TEXT,
                    distance REAL, digest TEXT UNIQUE, gpx BLOB, reference INTEGER
                );
                CREATE TABLE IF NOT EXISTS activity_profiles (
                    id TEXT PRIMARY KEY, digest TEXT, version TEXT, profile TEXT,
                    distance_class TEXT, error TEXT
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(activities)")}
            if "revision" not in columns:
                db.execute("ALTER TABLE activities ADD COLUMN revision TEXT NOT NULL DEFAULT ''")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get_app_state(self):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None

    def save_app_state(self, state):
        from .backup import validate_state
        payload = json.dumps(validate_state(state), ensure_ascii=False, allow_nan=False)
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO app_state VALUES (1,?)", (payload,))

    def reference_sources(self, directory, include_excluded=False):
        sources = []
        for path in sorted(Path(directory).iterdir()):
            if path.is_file() and path.suffix.lower() == ".gpx":
                stat = path.stat()
                sources.append(dict(key="file:" + str(path.resolve()), name=path.stem,
                                    path=path, signature=f"{stat.st_size}:{stat.st_mtime_ns}"))
        with self.connection() as db:
            rows = db.execute("SELECT id,name,digest,reference FROM activities " +
                ("" if include_excluded else "WHERE reference=1 ") + "ORDER BY id").fetchall()
        sources.extend(dict(key="activity:" + row["id"], name=row["name"],
                            activity=row["id"], enabled=bool(row["reference"]), signature=row["digest"] + ":" + row["name"]) for row in rows)
        with self.connection() as db:
            choices = {row["key"]: bool(row["enabled"]) for row in db.execute("SELECT * FROM reference_selection")}
        for source in sources:
            source["enabled"] = choices.get(source["key"], source.get("enabled", True))
        return sources if include_excluded else [s for s in sources if s["enabled"]]

    def reference_inventory(self, directory):
        """Inclure les références désactivées pour permettre leur réintégration."""
        sources = self.reference_sources(directory, include_excluded=True)
        with self.connection() as db:
            active_ids = {s.get("activity") for s in sources}
            for row in db.execute("SELECT id,name FROM activities WHERE reference=0 ORDER BY name"):
                if row["id"] not in active_ids:
                    sources.append(dict(key="activity:" + row["id"], name=row["name"], enabled=False))
        return [dict(key=s["key"], name=s["name"], enabled=s["enabled"]) for s in sources]

    def select_reference(self, key, enabled, directory):
        if not isinstance(enabled, bool):
            raise ValueError("Sélection de référence incorrecte.")
        if key not in {s["key"] for s in self.reference_inventory(directory)}:
            raise ValueError("Référence inconnue.")
        with self.connection() as db:
            if key.startswith("activity:"):
                db.execute("UPDATE activities SET reference=? WHERE id=?", (int(enabled), key[9:]))
                db.execute("DELETE FROM reference_selection WHERE key=?", (key,))
            else:
                db.execute("INSERT OR REPLACE INTO reference_selection VALUES (?,?)", (key, int(enabled)))
            db.execute("DELETE FROM model_cache")

    def load_reference(self, source, loader):
        version = self.version
        with self.connection() as db:
            cached = db.execute("SELECT * FROM reference_cache WHERE key=?", (source["key"],)).fetchone()
        if cached and cached["signature"] == source["signature"] and cached["version"] == version:
            try:
                value = decode(cached["payload"], cached["checksum"]) if not cached["error"] else None
                return value, cached["digest"], cached["error"], True
            except (ValueError, pickle.UnpicklingError, EOFError, AttributeError, TypeError):
                pass
        if "path" in source:
            data = source["path"].read_bytes()
        else:
            with self.connection() as db:
                row = db.execute("SELECT gpx FROM activities WHERE id=?", (source["activity"],)).fetchone()
                if row is None:
                    raise ValueError("L'activité a été retirée pendant l'actualisation.")
                data = bytes(row["gpx"])
        fingerprint = digest(data)
        if cached and cached["digest"] == fingerprint and cached["version"] == version:
            try:
                value = decode(cached["payload"], cached["checksum"]) if not cached["error"] else None
                with self.connection() as db:
                    db.execute("UPDATE reference_cache SET signature=? WHERE key=?", (source["signature"], source["key"]))
                return value, fingerprint, cached["error"], True
            except (ValueError, pickle.UnpicklingError, EOFError, AttributeError, TypeError):
                pass
        error = None
        try:
            value = loader(data)
        except (ValueError, KeyError, OSError, ParseError, OverflowError) as exc:
            # L'erreur d'un GPX est aussi mémorisée pour éviter de le relire à chaque démarrage.
            error = str(exc)
            value = None
        payload = pickle.dumps(value, protocol=4)
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO reference_cache VALUES (?,?,?,?,?,?,?)",
                       (source["key"], source["signature"], fingerprint, version, payload, digest(payload), error))
        return value, fingerprint, error, False

    def manifest(self, sources):
        with self.connection() as db:
            known = {row["key"]: row for row in db.execute("SELECT key,signature,digest,version FROM reference_cache")}
        version = self.version
        result = []
        for source in sources:
            row = known.get(source["key"])
            if not row or row["signature"] != source["signature"] or row["version"] != version:
                return None
            result.append((source["key"], row["digest"], source["name"]))
        return digest(json.dumps([version, result], sort_keys=True).encode())

    def load_models(self, fingerprint):
        if fingerprint is None:
            return None
        with self.connection() as db:
            row = db.execute("SELECT payload,checksum FROM model_cache WHERE fingerprint=?", (fingerprint,)).fetchone()
        if row:
            try:
                return decode(row["payload"], row["checksum"])
            except (ValueError, pickle.UnpicklingError, EOFError, AttributeError, TypeError):
                return None
        return None

    def save_models(self, fingerprint, value):
        payload = pickle.dumps(value, protocol=4)
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO model_cache VALUES (?,?,?)", (fingerprint, payload, digest(payload)))
            db.execute("DELETE FROM model_cache WHERE fingerprint<>?", (fingerprint,))

    def list_activities(self, filters=None):
        with self.connection() as db:
            rows = [dict(row) for row in db.execute(
                "SELECT id,source,name,kind,date,distance,reference,revision,digest FROM activities ORDER BY date DESC,id")]
        for row in rows:
            row.update(self.activity_profile(row['id'],row.pop('digest')))
        return [row for row in rows if filters is None or matches(row, filters)]

    def activity_profile(self, activity_id, fingerprint):
        """Calculer une seule fois la morphologie des imports existants ou modifiés."""
        with self.connection() as db:
            cached = db.execute('SELECT * FROM activity_profiles WHERE id=?',(activity_id,)).fetchone()
            if cached and cached['digest'] == fingerprint and cached['version'] == self.profile_version:
                return dict(profile=cached['profile'],distanceClass=cached['distance_class'],classificationError=cached['error'])
            row = db.execute('SELECT gpx FROM activities WHERE id=? AND digest=?',(activity_id,fingerprint)).fetchone()
        if row is None:
            return dict(profile=None,distanceClass=None,classificationError='Activité retirée ou modifiée.')
        try:
            from .gpx import read_gpx, describe_course
            descriptor = describe_course(read_gpx(BytesIO(bytes(row['gpx']))))
            result = dict(profile=descriptor['profile'],distanceClass=descriptor['distanceClass'],classificationError=None)
        except (ValueError,KeyError,OSError,ParseError,OverflowError) as error:
            result = dict(profile=None,distanceClass=None,classificationError='Classification GPX indisponible : '+str(error))
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO activity_profiles SELECT ?,?,?,?,?,? WHERE EXISTS '
                       '(SELECT 1 FROM activities WHERE id=? AND digest=?)',
                       (activity_id,fingerprint,self.profile_version,result['profile'],result['distanceClass'],result['classificationError'],activity_id,fingerprint))
        return result

    def save_activity(self, activity, data, descriptor=None):
        fingerprint = digest(data)
        with self.connection() as db:
            # Une écriture sérialisée rend les retries et imports simultanés idempotents.
            db.execute("BEGIN IMMEDIATE")
            duplicate = db.execute("SELECT id FROM activities WHERE digest=? AND id<>?",
                                   (fingerprint, activity["id"])).fetchone()
            if duplicate:
                return False
            existing = db.execute("SELECT * FROM activities WHERE id=?", (activity["id"],)).fetchone()
            revision = activity.get("revision", "")
            if existing and all(existing[key] == value for key, value in (
                ("digest", fingerprint), ("revision", revision), ("name", activity["name"]),
                ("kind", activity["kind"]), ("date", activity["date"]), ("distance", activity["distance"]))):
                return False
            if existing:
                db.execute("UPDATE activities SET name=?,kind=?,date=?,distance=?,digest=?,gpx=?,revision=? WHERE id=?",
                    (activity["name"], activity["kind"], activity["date"], activity["distance"], fingerprint,
                     data, revision, activity["id"]))
            else:
                db.execute("INSERT INTO activities (id,source,name,kind,date,distance,digest,gpx,reference,revision) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (activity["id"], activity["source"], activity["name"], activity["kind"], activity["date"],
                            activity["distance"], fingerprint, data, int(activity["reference"]), revision))
            if descriptor:
                db.execute('INSERT OR REPLACE INTO activity_profiles VALUES (?,?,?,?,?,?)',
                    (activity['id'],fingerprint,self.profile_version,descriptor['profile'],descriptor['distanceClass'],None))
        return True

    def delete_activities(self, filters=None):
        if filters and (filters.get('profile','all') != 'all' or filters.get('distanceClass','all') != 'all'):
            self.list_activities(filters)  # Préparer les classifications avant la transaction de suppression.
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = [dict(row) for row in db.execute('SELECT a.id,a.kind,a.date,a.distance,a.reference, '
                'CASE WHEN p.digest=a.digest AND p.version=? THEN p.profile END AS profile, '
                'CASE WHEN p.digest=a.digest AND p.version=? THEN p.distance_class END AS distanceClass '
                'FROM activities a LEFT JOIN activity_profiles p ON p.id=a.id', (self.profile_version,self.profile_version))]
            ids = [row["id"] for row in rows if filters is None or matches(row, filters)]
            if any(row["reference"] and row["id"] in ids for row in rows):
                db.execute("DELETE FROM model_cache")
            db.executemany("DELETE FROM activities WHERE id=?", [(key,) for key in ids])
            db.executemany('DELETE FROM activity_profiles WHERE id=?',[(key,) for key in ids])
            db.executemany("DELETE FROM reference_cache WHERE key=?", [("activity:" + key,) for key in ids])
        return len(ids)

    def set_reference(self, activity_id, value):
        with self.connection() as db:
            changed = db.execute("UPDATE activities SET reference=? WHERE id=?", (int(value), activity_id)).rowcount
        if not changed:
            raise ValueError("Activité locale introuvable.")
