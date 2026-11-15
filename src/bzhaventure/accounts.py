"""Comptes et sessions du mode serveur, séparés des bibliothèques GPX."""
from contextlib import closing
from datetime import date
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
import json
from pathlib import Path
import re
import secrets
import sqlite3
from time import time
from uuid import uuid4


SESSION_SECONDS = 12 * 3600
IDLE_SECONDS = 300
ACTIVITY_WRITE_SECONDS = 15
USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,39}", re.ASCII)
GENDERS = {"woman": "Femme", "man": "Homme", "nonbinary": "Non binaire", "other": "Autre"}
MAX_PROFILE_PHOTO = 2 * 1024 * 1024


def password_hash(password, salt):
    return pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)


def normalize_username(value):
    return value.strip().lower()


def validate_profile(gender, birth_date):
    if gender and gender not in GENDERS:
        raise ValueError("Genre incorrect.")
    if birth_date:
        try:
            birthday = date.fromisoformat(birth_date)
            if birthday.isoformat() != birth_date or birthday > date.today():
                raise ValueError
        except ValueError:
            raise ValueError("Indiquez une date de naissance valide et non future.") from None
    return gender or None, birth_date or None


def profile_photo_type(photo):
    if not photo:
        return None
    if len(photo) > MAX_PROFILE_PHOTO:
        raise ValueError("Photo de profil limitée à 2 Mio.")
    if photo.startswith(b"\x89PNG\r\n\x1a\n") and photo[12:16] == b"IHDR" and photo.endswith(b"IEND\xaeB`\x82"):
        return "image/png"
    if photo.startswith(b"\xff\xd8\xff") and photo.endswith(b"\xff\xd9"):
        return "image/jpeg"
    raise ValueError("Choisissez une photo au format JPEG ou PNG.")


class Accounts:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / "accounts.sqlite3"
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    admin INTEGER NOT NULL, salt BLOB NOT NULL, verifier BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    expires REAL NOT NULL
                );
            """)
            db.execute("BEGIN IMMEDIATE")
            additions = {
                "users": {
                    "login_count": "INTEGER NOT NULL DEFAULT 0",
                    "last_login": "REAL",
                    "active_seconds": "REAL NOT NULL DEFAULT 0",
                    "reset_requested": "INTEGER NOT NULL DEFAULT 0",
                    "must_change": "INTEGER NOT NULL DEFAULT 0",
                    "model_count": "INTEGER",
                    "model_groups": "TEXT",
                    "gender": "TEXT",
                    "birth_date": "TEXT",
                    "photo": "BLOB",
                    "photo_type": "TEXT",
                },
                "sessions": {"last_seen": "REAL"},
            }
            for table, columns in additions.items():
                existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                for name, definition in columns.items():
                    if name not in existing:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def create(self, username, password, *, first_admin=False, gender="", birth_date="", photo=None):
        username = normalize_username(username)
        if not USERNAME.fullmatch(username):
            raise ValueError("Identifiant de 3 à 40 caractères : lettres non accentuées, chiffres, point, tiret ou soulignement.")
        if not 12 <= len(password) <= 256:
            raise ValueError("Le mot de passe doit contenir de 12 à 256 caractères.")
        gender, birth_date = validate_profile(gender, birth_date)
        photo_type = profile_photo_type(photo)
        salt = secrets.token_bytes(16)
        verifier = password_hash(password, salt)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if first_admin and db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise ValueError("Le serveur a déjà un administrateur.")
            try:
                db.execute("""INSERT INTO users
                    (id, username, admin, salt, verifier, model_count, gender, birth_date, photo, photo_type)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                    (uuid4().hex, username, int(first_admin), salt, verifier,
                     gender or None, birth_date or None, photo or None, photo_type))
            except sqlite3.IntegrityError as error:
                raise ValueError("Cet identifiant existe déjà.") from error

    def list(self):
        with closing(self.connect()) as db:
            return db.execute("SELECT id, username, admin FROM users ORDER BY username").fetchall()

    def profile_photo(self, account_id):
        with closing(self.connect()) as db:
            return db.execute("SELECT photo, photo_type FROM users WHERE id=? AND photo IS NOT NULL",
                              (account_id,)).fetchone()

    def update_profile(self, account_id, gender, birth_date, *, photo=None, remove_photo=False):
        gender, birth_date = validate_profile(gender, birth_date)
        if photo and remove_photo:
            raise ValueError("Choisissez de remplacer ou de supprimer la photo.")
        photo_type = profile_photo_type(photo)
        with closing(self.connect()) as db, db:
            if photo or remove_photo:
                result = db.execute("UPDATE users SET gender=?, birth_date=?, photo=?, photo_type=? WHERE id=?",
                                    (gender, birth_date, photo or None, photo_type, account_id))
            else:
                result = db.execute("UPDATE users SET gender=?, birth_date=? WHERE id=?",
                                    (gender, birth_date, account_id))
            if not result.rowcount:
                raise ValueError("Compte inconnu.")

    def statistics(self):
        with closing(self.connect()) as db:
            return db.execute("""
                SELECT id, username, admin, login_count, last_login, active_seconds, reset_requested,
                       model_count, model_groups, gender, birth_date, photo_type
                FROM users ORDER BY username
            """).fetchall()

    def save_model_count(self, account_id, count, groups=None):
        encoded = json.dumps(groups, ensure_ascii=False) if groups is not None else None
        with closing(self.connect()) as db, db:
            db.execute("UPDATE users SET model_count=?, model_groups=? WHERE id=?", (count, encoded, account_id))

    def account_id(self, username):
        with closing(self.connect()) as db:
            row = db.execute("SELECT id FROM users WHERE username=?", (normalize_username(username),)).fetchone()
        if row is None:
            raise ValueError("Compte inconnu.")
        return row["id"]

    def login(self, username, password):
        if len(password) > 256:
            return None
        with closing(self.connect()) as db, db:
            user = db.execute("SELECT * FROM users WHERE username=?",
                              (normalize_username(username),)).fetchone()
            salt = user["salt"] if user else bytes(16)
            expected = user["verifier"] if user else bytes(32)
            valid = compare_digest(password_hash(password, salt), expected)
            if not valid or user is None:
                return None
            token = secrets.token_urlsafe(32)
            now = time()
            db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
            inserted = db.execute("""
                INSERT INTO sessions (digest, user_id, expires, last_seen)
                SELECT ?, id, ?, ? FROM users WHERE id=? AND verifier=?
            """, (self.token_digest(token), now + SESSION_SECONDS, now, user["id"], expected))
            if inserted.rowcount != 1:
                return None
            db.execute("UPDATE users SET login_count=login_count+1, last_login=? WHERE id=?", (now, user["id"]))
            return token

    @staticmethod
    def token_digest(token):
        return sha256(token.encode("utf-8")).hexdigest()

    def user(self, token, *, finalize=False):
        if not token:
            return None
        now = time()
        digest = self.token_digest(token)
        with closing(self.connect()) as db, db:
            user = db.execute("""
                SELECT users.id, users.username, users.admin, users.must_change, users.gender,
                       users.birth_date, users.photo_type, sessions.last_seen FROM users
                JOIN sessions ON sessions.user_id=users.id
                WHERE sessions.digest=? AND sessions.expires>?
            """, (digest, now)).fetchone()
            if user is None:
                return None
            previous = user["last_seen"]
            elapsed = max(0, now - previous) if previous is not None else 0
            if previous is None or finalize or elapsed >= ACTIVITY_WRITE_SECONDS:
                updated = db.execute("UPDATE sessions SET last_seen=? WHERE digest=? AND last_seen IS ?",
                                     (now, digest, previous))
                if updated.rowcount == 1:
                    db.execute("UPDATE users SET active_seconds=active_seconds+? WHERE id=?",
                               (min(elapsed, IDLE_SECONDS), user["id"]))
            return user

    def request_reset(self, username):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE users SET reset_requested=1 WHERE username=? AND admin=0",
                       (normalize_username(username),))

    def set_user_password(self, username, password):
        if not 12 <= len(password) <= 256:
            raise ValueError("Le mot de passe doit contenir de 12 à 256 caractères.")
        salt = secrets.token_bytes(16)
        verifier = password_hash(password, salt)
        with closing(self.connect()) as db, db:
            updated = db.execute("""
                UPDATE users SET salt=?, verifier=?, must_change=1, reset_requested=0
                WHERE username=? AND admin=0
            """, (salt, verifier, normalize_username(username)))
            if updated.rowcount != 1:
                raise ValueError("Compte utilisateur inconnu.")
            db.execute("DELETE FROM sessions WHERE user_id=(SELECT id FROM users WHERE username=?)",
                       (normalize_username(username),))

    def logout(self, token):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM sessions WHERE digest=?", (self.token_digest(token),))

    def change_password(self, account_id, old_password, new_password):
        if not 12 <= len(new_password) <= 256 or len(old_password) > 256:
            raise ValueError("Le nouveau mot de passe doit contenir de 12 à 256 caractères.")
        with closing(self.connect()) as db, db:
            user = db.execute("SELECT salt, verifier FROM users WHERE id=?", (account_id,)).fetchone()
            if user is None or not compare_digest(password_hash(old_password, user["salt"]), user["verifier"]):
                raise ValueError("Mot de passe actuel incorrect.")
            salt = secrets.token_bytes(16)
            updated = db.execute("UPDATE users SET salt=?, verifier=?, must_change=0, reset_requested=0 WHERE id=? AND verifier=?",
                                 (salt, password_hash(new_password, salt), account_id, user["verifier"]))
            if updated.rowcount != 1:
                raise ValueError("Le mot de passe a déjà changé. Reconnectez-vous.")
            db.execute("DELETE FROM sessions WHERE user_id=?", (account_id,))
