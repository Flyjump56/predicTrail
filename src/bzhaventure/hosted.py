"""Mode serveur avec un espace de travail privé par compte."""
import argparse
from collections import deque
from datetime import datetime, timezone
from getpass import getpass
from html import escape
from http.cookies import CookieError, SimpleCookie
from http.server import ThreadingHTTPServer
from ipaddress import IPv4Address, IPv4Network
import json
import os
import secrets
from pathlib import Path
from shutil import copyfile
from threading import BoundedSemaphore, Lock
from time import monotonic
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from zipfile import BadZipFile

from .accounts import Accounts, SESSION_SECONDS
from .backup import Backups, MAX_ARCHIVE
from .garmin import GarminConnection
from .server import Dashboard, STATIC_FILES, StartupStatus, start_update
from .settings import PAGE, PORT
from .storage import Store


COOKIE = "predictrail_session"
LAN_NETWORKS = tuple(IPv4Network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
LOGIN_FIELDS = """
<label>Identifiant <input name="username" autocomplete="username" required maxlength="40"></label>
<label>Mot de passe <input name="password" type="password" autocomplete="current-password" required maxlength="256"></label>
"""


def account_storage(directory, account_id):
    root = directory / "users" / account_id
    references = root / "references"
    references.mkdir(mode=0o700, parents=True, exist_ok=True)
    return Store(root / "local" / "bzhaventure.sqlite3"), references


def model_counts_html(user):
    count = user["model_count"]
    if count is None:
        return "—"
    if not count:
        return "0"
    groups = user["model_groups"]
    if groups is None:
        return f"{count}<br><small>Détail disponible après le prochain chargement du modèle.</small>"
    rows = "".join(
        f'<tr><th scope="row">{escape(group["profile"])}</th><td>{escape(group["distance"])}</td>'
        f'<td>{group["exact"]}</td><td>{group["used"]}</td></tr>'
        for group in json.loads(groups)
    )
    return f"""<details class="account-model-counts"><summary>{count} · Détail par modèle</summary>
<p>Modèle global&nbsp;: {count}<br>Modèle par inclinaison&nbsp;: {count}</p>
<table><caption>Références par modèle de groupe</caption>
<thead><tr><th>Profil</th><th>Distance</th><th>Dans le groupe</th><th>Utilisées du profil</th></tr></thead>
<tbody>{rows}</tbody></table>
<p><small>Le modèle de groupe peut utiliser des courses du même profil sur d’autres distances, avec l’appui du modèle global. Un zéro dans la dernière colonne indique un repli sur le modèle global.</small></p></details>"""


def operation_progress_html(account_id="", element_id=None):
    target = f' id="{element_id}"' if element_id else ""
    hidden = "" if account_id else " hidden"
    return f"""<div{target} class="account-operation" data-operation-account="{account_id}"{hidden}>
<progress max="100" value="0" aria-label="Progression du calcul" hidden></progress>
<span>Chargement du suivi…</span></div>"""


def operations_script(account):
    return f'<script src="/assets/admin-progress.js" defer data-operations-url="/compte/{account["id"]}/api/admin/operations"></script>'


class AccountServer(ThreadingHTTPServer):
    def __init__(self, address, directory, origin, bind_and_activate=True):
        super().__init__(address, HostedDashboard, bind_and_activate)
        self.directory = Path(directory)
        self.accounts = Accounts(self.directory)
        self.origin = origin
        self.host = urlsplit(origin).netloc.lower()
        self.secure = origin.startswith("https://")
        self.runtimes = {}
        self.runtime_lock = Lock()
        self.compute_slots = BoundedSemaphore(2)
        self.request_slots = BoundedSemaphore(12)
        self.login_lock = Lock()
        self.login_attempts = deque()

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(60)
        return request, address

    def process_request(self, request, address):
        if not self.request_slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nRetry-After: 3\r\nContent-Length: 0\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.request_slots.release()

    def allow_login(self):
        now = monotonic()
        with self.login_lock:
            while self.login_attempts and self.login_attempts[0] <= now - 60:
                self.login_attempts.popleft()
            if len(self.login_attempts) >= 20:
                return False
            self.login_attempts.append(now)
            return True

    def runtime_for(self, account_id):
        with self.runtime_lock:
            runtime = self.runtimes.get(account_id)
            if runtime is None:
                store, references = account_storage(self.directory, account_id)
                startup = StartupStatus()
                runtime = SimpleNamespace(
                    store=store, reference_directory=references,
                    startup=startup, update_lock=Lock(), garmin=GarminConnection(),
                    validation_isolated=True, backup_auto_enabled=False, compute_slots=self.compute_slots, hosted=True,
                    model=None, references=None, runtime=(None, None),
                    report_model_counts=lambda references, empty: self.save_model_counts(account_id, references, empty),
                )
                self.runtimes[account_id] = runtime
            if not hasattr(runtime, "operation"):
                try:
                    start_update(runtime)
                except ValueError:
                    pass  # Une prochaine requête réessaiera si les créneaux sont occupés.
            return runtime

    def save_model_counts(self, account_id, references, empty):
        if references is None:
            self.accounts.save_model_count(account_id, 0 if empty else None)
            return
        groups = [
            dict(profile=group["profileLabel"], distance=group["distanceLabel"],
                 exact=group["exactCount"], used=group["count"] if group["localWeight"] > 0 else 0)
            for group in references["models"]
        ]
        self.accounts.save_model_count(account_id, len(references["courses"]), groups)

    def operations_snapshot(self):
        with self.runtime_lock:
            operations = [(account, runtime.operation) for account, runtime in self.runtimes.items()
                          if hasattr(runtime, "operation")]
        fields = ("status", "phase", "message", "progress", "completed", "total", "elapsed", "slow", "kind")
        snapshots = {}
        for account, operation in operations:
            snapshot = operation.snapshot()
            snapshots[account] = {key: snapshot[key] for key in fields if key in snapshot}
        return snapshots


class HostedDashboard(Dashboard):
    @property
    def runtime_context(self):
        return self.account_runtime

    def local_host(self):
        if self.headers.get("Host", "").lower() != self.server.host:
            self.send_json({"error": "Adresse du serveur incorrecte."}, 403)
            return False
        return True

    def log_request(self, code="-", size="-"):
        # Les identifiants d’archives et de comptes ne font pas partie des journaux HTTP.
        if self.path not in ("/api/startup", "/api/admin/operations"):
            self.log_message("%s %s", self.command, code)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()

    def session_token(self):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie[COOKIE].value if COOKIE in cookie else ""
        except CookieError:
            return ""

    def redirect(self, path, token=None):
        self.send_response(303)
        self.send_header("Location", path)
        self.send_header("Cache-Control", "no-store")
        if token is not None:
            age = SESSION_SECONDS if token else 0
            secure = "; Secure" if self.server.secure else ""
            self.send_header("Set-Cookie", f"{COOKIE}={token}; Path=/; Max-Age={age}; HttpOnly; SameSite=Strict{secure}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def page(self, title, body, status=200, *, wide=False, account_header=""):
        layout = " account-page-wide" if wide else ""
        html = f"""<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · PrédicTrail</title><link rel="stylesheet" href="/assets/styles.css">
<body>{account_header}<main class="account-page{layout}"><section><h1>{escape(title)}</h1>{body}</section></main></body></html>"""
        self.reply(html.encode("utf-8"), "text/html; charset=utf-8", status)

    def login_page(self, message="", status=200):
        self.page("Connexion à PrédicTrail", f"""
<p role="status">{escape(message)}</p>
<form method="post" action="/connexion" class="account-form">
{LOGIN_FIELDS}<button class="button">Se connecter</button></form>
<p><a href="/inscription">Créer un compte</a> · <a href="/mot-de-passe-oublie">Mot de passe oublié</a></p>""", status)

    def registration(self, message="", status=200):
        self.page("Créer un compte", f"""
<p role="status">{escape(message)}</p>
<form method="post" action="/inscription" class="account-form">
<label>Identifiant <input name="username" autocomplete="username" required minlength="3" maxlength="40"></label>
<label>Mot de passe <input name="password" type="password" autocomplete="new-password" required minlength="12" maxlength="256"></label>
<label>Confirmer le mot de passe <input name="confirmation" type="password" autocomplete="new-password" required maxlength="256"></label>
<button class="button">Créer mon compte</button></form><p><a href="/">Retour à la connexion</a></p>""", status)

    def forgot_password(self, message="", status=200):
        self.page("Mot de passe oublié", f"""
<p role="status">{escape(message)}</p>
<form method="post" action="/mot-de-passe-oublie" class="account-form">
<label>Identifiant <input name="username" autocomplete="username" required maxlength="40"></label>
<button class="button">Envoyer la demande à l’administrateur</button></form>
<p><a href="/">Retour à la connexion</a></p>""", status)

    def administration(self, account, message="", status=200):
        rows = []
        for user in self.server.accounts.statistics():
            username = escape(user["username"])
            last = (datetime.fromtimestamp(user["last_login"], timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
                    if user["last_login"] is not None else "—")
            minutes, seconds = divmod(int(user["active_seconds"]), 60)
            hours, minutes = divmod(minutes, 60)
            duration = f"{hours} h {minutes:02d} min {seconds:02d} s"
            traces = model_counts_html(user)
            role = "Administrateur" if user["admin"] else "Utilisateur"
            pending = "<strong>Demande de réinitialisation</strong>" if user["reset_requested"] else ""
            actions = "Mot de passe depuis ton compte" if user["admin"] else f"""
{pending}<details><summary>Gérer l’accès</summary>
<form method="post" action="/administration" class="account-form">
<input type="hidden" name="username" value="{username}">
<input type="hidden" name="action" value="password">
<label>Mot de passe provisoire <input name="password" type="password" autocomplete="new-password" required minlength="12" maxlength="256"></label>
<button class="button">Changer le mot de passe</button></form>
<form method="post" action="/administration" class="account-form">
<input type="hidden" name="username" value="{username}">
<input type="hidden" name="action" value="reset">
<label><input type="checkbox" name="confirm" value="yes" required> Révoquer les sessions et générer un mot de passe provisoire</label>
<button class="button">Réinitialiser l’accès</button></form></details>"""
            rows.append(f"""<tr><th scope="row">{username}</th><td>{role}</td><td>{user["login_count"]}</td>
<td>{last}</td><td>{duration}</td><td>{traces}</td><td>{operation_progress_html(user["id"])}</td><td>{actions}</td></tr>""")
        self.page("Administration des comptes", f"""
<p><a href="/">Retour à PrédicTrail</a></p><p role="status">{escape(message)}</p>
<details><summary>Créer un compte utilisateur</summary>
<form method="post" action="/administration" class="account-form">
<label>Identifiant <input name="username" required minlength="3" maxlength="40"></label>
<label>Mot de passe initial <input name="password" type="password" autocomplete="new-password" required minlength="12" maxlength="256"></label>
<button class="button">Créer le compte</button></form></details>
<div class="scroll"><table class="account-table"><caption>Suivi des comptes utilisateurs</caption>
<thead><tr><th scope="col">Compte</th><th scope="col">Rôle</th><th scope="col">Connexions</th>
<th scope="col">Dernière connexion</th><th scope="col">Temps de connexion estimé</th>
<th scope="col">Traces dans le modèle</th><th scope="col">Calculs et progression</th><th scope="col">Actions</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p>Le temps est estimé à partir de l’activité du navigateur, avec cinq minutes au maximum entre deux requêtes. Les statistiques commencent avec cette version. Le nombre de traces correspond au dernier modèle calculé. Un tiret indique qu’il n’est pas encore disponible.</p>{operations_script(account)}""",
                  status, wide=True, account_header=f"<header>{self.account_bar(account)}</header>")

    def account_bar(self, user):
        return f"""
<div class="account-bar no-print"><strong>Bienvenue, {escape(user["username"])} !</strong>
<a class="button" href="/parametres-compte"><span aria-hidden="true">⚙</span> Paramètres du compte</a>
<form method="post" action="/deconnexion"><button class="button">Se déconnecter</button></form></div>
"""

    def dashboard(self, user):
        html = PAGE.read_text(encoding="utf-8").replace(
            "<body>", f'<body data-account="{user["id"]}">', 1)
        html = html.replace("</header>", self.account_bar(user) + "</header>", 1)
        if user["admin"]:
            html = html.replace("<!-- admin-navigation -->",
                                '<a class="button" href="/administration" id="tab-administration">Administration</a>', 1)
            options = ['<option value="">Mon compte</option>']
            options.extend(f'<option value="{account["id"]}">{escape(account["username"])}</option>'
                           for account in self.server.accounts.list() if account["id"] != user["id"])
            for screen in ("references", "map"):
                controls = f"""<div class="controls admin-reference-view">
<label for="admin-reference-{screen}">Compte consulté
<select id="admin-reference-{screen}">{''.join(options)}</select></label>
<button type="button" class="button" id="admin-reference-refresh-{screen}">Actualiser la consultation</button>
<span role="status" id="admin-reference-status-{screen}"></span></div>
{operation_progress_html(element_id=f"admin-reference-operation-{screen}")}"""
                html = html.replace(f"<!-- admin-reference-{screen} -->", controls, 1)
            html = html.replace("</body>", operations_script(user) + "</body>", 1)
        self.reply(html.encode("utf-8"), "text/html; charset=utf-8")

    def password_page(self, user, message="", status=200):
        role = "Administrateur" if user["admin"] else "Utilisateur"
        notice = "<p>Choisissez un nouveau mot de passe pour activer votre accès.</p>" if user["must_change"] else ""
        self.page("Paramètres du compte", f"""
<p><a href="/">Retour à PrédicTrail</a></p><p role="status">{escape(message)}</p>
<dl><dt>Identifiant</dt><dd>{escape(user["username"])}</dd><dt>Rôle</dt><dd>{role}</dd></dl>
<h2>Modifier mon mot de passe</h2>{notice}
<form method="post" action="/mot-de-passe" class="account-form">
<label>Mot de passe actuel <input name="password" type="password" autocomplete="current-password" required maxlength="256"></label>
<label>Nouveau mot de passe <input name="new-password" type="password" autocomplete="new-password" required minlength="12" maxlength="256"></label>
<button class="button">Modifier et se reconnecter</button></form>""", status,
                  account_header=f"<header>{self.account_bar(user)}</header>")

    def authorize_api(self, user):
        if user is None:
            self.send_json({"error": "Session expirée. Reconnectez-vous."}, 401)
            return False
        if user["must_change"]:
            self.send_json({"error": "Modifiez le mot de passe provisoire avant d’accéder à votre espace."}, 403)
            return False
        prefix = f'/compte/{user["id"]}'
        if not self.path.startswith(prefix + "/api/"):
            self.send_json({"error": "Adresse indisponible pour ce compte."}, 403)
            return False
        self.path = self.path[len(prefix):]
        route = urlsplit(self.path).path
        if route in ("/api/backup/inspect", "/api/backup/restore"):
            self.send_json({"error": "La restauration ZIP est réservée à la maintenance du serveur."}, 403)
            return False
        if not route.startswith("/api/admin/"):
            self.account_runtime = self.server.runtime_for(user["id"])
        return True

    def read_form(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if self.headers.get_content_type() != "application/x-www-form-urlencoded" or not 0 < size <= 8192:
            raise ValueError("Formulaire incorrect.")
        fields = parse_qs(self.rfile.read(size).decode("utf-8"), keep_blank_values=True, max_num_fields=4)
        return {name: values[0] for name, values in fields.items()}

    def admin_reference_view(self, user):
        parsed = urlsplit(self.path)
        if parsed.path == "/api/admin/operations":
            if user["admin"]:
                self.send_json({"operations": self.server.operations_snapshot()})
            else:
                self.send_json({"error": "Accès administrateur requis."}, 403)
            return True
        route = {"/api/admin/references": "/api/references",
                 "/api/admin/reference-map": "/api/reference-map"}.get(parsed.path)
        if route is None:
            return False
        if not user["admin"]:
            self.send_json({"error": "Accès administrateur requis."}, 403)
            return True
        account_id = parse_qs(parsed.query).get("account", [""])[0]
        if account_id not in {account["id"] for account in self.server.accounts.list()}:
            self.send_json({"error": "Compte introuvable."}, 404)
            return True
        self.account_runtime = self.server.runtime_for(account_id)
        if route == "/api/references":
            state = self.account_runtime.startup.snapshot()
            if state["status"] != "ready":
                self.send_json({"error": state["message"]}, 503)
                return True
        self.path = route
        super().do_GET()
        return True

    def do_GET(self):
        if not self.local_host():
            return
        if self.path in STATIC_FILES:
            super().do_GET()
            return
        user = self.server.accounts.user(self.session_token())
        if self.path == "/":
            if user and user["must_change"]:
                self.redirect("/mot-de-passe")
            else:
                self.dashboard(user) if user else self.login_page()
        elif self.path == "/inscription":
            self.registration()
        elif self.path == "/mot-de-passe-oublie":
            self.forgot_password()
        elif self.path == "/administration":
            if user and user["admin"]:
                self.administration(user)
            else:
                self.send_json({"error": "Accès administrateur requis."}, 403)
        elif self.path in ("/parametres-compte", "/mot-de-passe"):
            self.password_page(user) if user else self.redirect("/")
        elif self.authorize_api(user) and not self.admin_reference_view(user):
            super().do_GET()

    def do_POST(self):
        if not self.local_host():
            return
        if self.headers.get("Origin") != self.server.origin:
            self.send_json({"error": "Origine de requête non autorisée."}, 403)
            return
        token = self.session_token()
        user = self.server.accounts.user(token, finalize=self.path in ("/connexion", "/deconnexion", "/mot-de-passe"))
        if self.path == "/connexion":
            if not self.server.allow_login():
                self.login_page("Trop de tentatives. Réessayez dans une minute.", 429)
                return
            try:
                fields = self.read_form()
                session = self.server.accounts.login(fields.get("username", ""), fields.get("password", ""))
            except ValueError:
                session = None
            if session:
                if token:
                    self.server.accounts.logout(token)
                self.redirect("/", session)
            else:
                self.login_page("Identifiant ou mot de passe incorrect.", 401)
        elif self.path == "/inscription":
            if not self.server.allow_login():
                self.registration("Trop de tentatives. Réessayez dans une minute.", 429)
                return
            try:
                fields = self.read_form()
                username, password = fields.get("username", ""), fields.get("password", "")
                if password != fields.get("confirmation"):
                    raise ValueError("Les mots de passe ne correspondent pas.")
                self.server.accounts.create(username, password)
                self.registration("Compte créé. Retournez à la connexion pour ouvrir votre espace.")
            except ValueError as error:
                self.registration(str(error), 400)
        elif self.path == "/mot-de-passe-oublie":
            if not self.server.allow_login():
                self.forgot_password("Trop de tentatives. Réessayez dans une minute.", 429)
                return
            try:
                fields = self.read_form()
                self.server.accounts.request_reset(fields.get("username", ""))
                self.forgot_password("Si l’identifiant correspond à un compte utilisateur, la demande est visible par l’administrateur. Contactez-le pour recevoir le mot de passe provisoire.")
            except ValueError as error:
                self.forgot_password(str(error), 400)
        elif self.path == "/deconnexion":
            if token:
                self.server.accounts.logout(token)
            self.redirect("/", "")
        elif self.path == "/administration":
            if not user or not user["admin"]:
                self.send_json({"error": "Accès administrateur requis."}, 403)
                return
            try:
                fields = self.read_form()
                username = fields.get("username", "")
                action = fields.get("action", "create")
                if action == "create":
                    self.server.accounts.create(username, fields.get("password", ""))
                    self.administration(user, "Compte créé.")
                elif action == "password":
                    self.server.accounts.set_user_password(username, fields.get("password", ""))
                    self.administration(user, "Mot de passe provisoire défini. Les sessions du compte ont été fermées.")
                elif action == "reset" and fields.get("confirm") == "yes":
                    temporary = secrets.token_urlsafe(18)
                    self.server.accounts.set_user_password(username, temporary)
                    self.administration(user, f"Accès réinitialisé pour {username}. Mot de passe provisoire à transmettre en privé : {temporary}")
                else:
                    raise ValueError("Action incorrecte ou réinitialisation non confirmée.")
            except ValueError as error:
                self.administration(user, str(error), 400)
        elif self.path == "/mot-de-passe":
            if not user:
                self.redirect("/")
                return
            if not self.server.allow_login():
                self.password_page(user, "Trop de tentatives. Réessayez dans une minute.", 429)
                return
            try:
                fields = self.read_form()
                self.server.accounts.change_password(user["id"], fields.get("password", ""), fields.get("new-password", ""))
                self.redirect("/", "")
            except ValueError as error:
                self.password_page(user, str(error), 400)
        elif self.authorize_api(user):
            super().do_POST()


def main():
    parser = argparse.ArgumentParser(description="Démarrer PrédicTrail avec des comptes séparés.")
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("PREDICTRAIL_SERVER_DATA", ".predictrail-server")))
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--origin", help="Adresse publique HTTPS, sans barre oblique finale.")
    parser.add_argument("--lan", metavar="IP_PRIVÉE", help="Écouter en HTTP sur cette IPv4 privée pour un test local.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--init-admin", metavar="IDENTIFIANT")
    actions.add_argument("--restore-account", metavar="IDENTIFIANT", help="Restaurer une archive de confiance, serveur arrêté.")
    parser.add_argument("--archive", type=Path, help="Archive ZIP pour --restore-account.")
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    if bool(args.restore_account) != bool(args.archive):
        parser.error("--restore-account et --archive doivent être utilisés ensemble.")
    if args.restore_account:
        try:
            accounts = Accounts(directory)
            account_id = accounts.account_id(args.restore_account)
            if not args.archive.is_file() or not 0 < args.archive.stat().st_size <= MAX_ARCHIVE:
                raise ValueError("Fichier ZIP attendu, jusqu’à 2 Gio.")
            store, references = account_storage(directory, account_id)
            backups = Backups(store, references)
            token = uuid4().hex
            staged = backups.path(token)
            try:
                copyfile(args.archive, staged)
                backups.restore(token)
                accounts.save_model_count(account_id, None)
            finally:
                staged.unlink(missing_ok=True)
        except (ValueError, OSError, BadZipFile) as error:
            parser.error(str(error))
        print("Données restaurées dans le compte demandé.")
        return
    if args.init_admin:
        password = getpass("Mot de passe administrateur : ")
        if password != getpass("Confirmer : "):
            parser.error("Les mots de passe ne correspondent pas.")
        try:
            Accounts(directory).create(args.init_admin, password, first_admin=True)
        except ValueError as error:
            parser.error(str(error))
        print("Compte administrateur créé.")
        return
    bind_address = "127.0.0.1"
    if args.lan:
        if args.origin:
            parser.error("--lan définit déjà l’origine HTTP du test.")
        try:
            address = IPv4Address(args.lan)
        except ValueError:
            parser.error("--lan attend une adresse IPv4 privée.")
        if not any(address in network for network in LAN_NETWORKS):
            parser.error("--lan accepte uniquement une adresse IPv4 de réseau privé.")
        bind_address = str(address)
    origin = args.origin or f"http://{bind_address}:{args.port}"
    parsed = urlsplit(origin)
    if (not parsed.hostname or parsed.username or parsed.path or parsed.query or parsed.fragment
            or parsed.scheme not in ("http", "https")
            or (parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", bind_address))):
        parser.error("Utilisez une origine HTTPS ou l’option --lan pour un test HTTP sur réseau privé.")
    if not Accounts(directory).list():
        parser.error("Créez le premier administrateur avec --init-admin avant de démarrer.")
    with AccountServer((bind_address, args.port), directory, origin) as server:
        print(f"PrédicTrail serveur · {origin} · écoute sur {bind_address}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
