"""Marassim LAN API. Legacy business logic/templates remain authoritative."""
import argparse
import base64
import hashlib
import hmac
import io
import json
import logging
import math
import os
import re
import secrets
import socket
import sqlite3
import ssl
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
LEGACY = Path(getattr(sys, '_MEIPASS', HERE.parents[1]))
sys.path.insert(0, str(LEGACY))
from storage import Storage
import analytics
import omar_cash
import cloud_sync
from backups import BackupManager, atomic_write, restore_backup, sync_replica

MODULES = {
    'forecast-items': ('Cash-flow prévu',) * 3,
    'reservations': ('Réservations', 'Nouvelle réservation', 'Modifier réservation'),
    'charges': ('Charges',) * 3,
    'charges-omar': ('Charges Omar',) * 3,
    'recettes-omar': ('Journal Caisse Omar',) * 3,
    'employees': ('Liste employés', 'Ajouter employé', 'Ajouter employé'),
    'pointage': ('Pointage',) * 3,
    'employee-payments': ('Liste employés',) * 3,
    'rules': ('Règles de réservation',) * 3,
}
TABLES = {'reservations': 'reservations', 'charges': 'charges', 'charges-omar': 'charges_omar', 'recettes-omar': 'recettes_omar_extra', 'employees': 'employees', 'pointage': 'pointage', 'employee-payments': 'paiement_employees', 'rules': 'reservation_rules'}
TABLES['forecast-items'] = 'forecast_items'


class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def password_hash(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 200:
        raise APIError('Le mot de passe doit contenir entre 8 et 200 caractères.')
    salt = secrets.token_bytes(16)
    hashed = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return 'scrypt$' + salt.hex() + '$' + hashed.hex()


def password_matches(password, encoded):
    if not isinstance(password, str) or len(password) > 200:
        return False
    if encoded.startswith('scrypt$'):
        _, salt, expected = encoded.split('$')
        return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex(), expected)
    return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), encoded)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def ensure_certificate(root):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    certificate, key_path = root / 'server.crt', root / 'server.key'
    if not certificate.exists() or not key_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Marassim LAN Server')])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False).sign(key, hashes.SHA256()))
        atomic_write(key_path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        atomic_write(certificate, cert.public_bytes(serialization.Encoding.PEM))
    cert = x509.load_pem_x509_certificate(certificate.read_bytes())
    return certificate, key_path, cert.fingerprint(hashes.SHA256()).hex()


def sync_templates(source, destination):
    """Upgrade known factory templates; preserve customized documents and originals."""
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    manifest_file = source / 'branding.json'
    manifest = json.loads(manifest_file.read_text(encoding='utf-8')) if manifest_file.exists() else {}
    for bundled in source.glob('*.docx'):
        target = destination / bundled.name
        content = bundled.read_bytes()
        if not target.exists():
            atomic_write(target, content)
            continue
        known = manifest.get('files', {}).get(bundled.name, {})
        current = target.read_bytes()
        if (hashlib.sha256(content).hexdigest() == known.get('sha256')
                and hashlib.sha256(current).hexdigest() in known.get('previous_sha256', [])):
            preserved = destination.parent / 'template-history' / 'before-logo' / bundled.name
            if not preserved.exists():
                atomic_write(preserved, current)
            atomic_write(target, content)


class Application:
    def __init__(self, data_dir, source=None):
        self.root = Path(data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'marassim.db'
        if not self.path.exists() and source:
            source_path = Path(source).resolve()
            if source_path == self.path or not source_path.is_file():
                raise ValueError('Base source introuvable ou identique à la destination.')
            # Read-only source; never migrate the user's original DB.
            original = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
            copy = sqlite3.connect(self.path)
            try:
                original.backup(copy)
                if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('La base source est corrompue.')
            finally:
                copy.close()
                original.close()
        os.environ['MARASSIM_DB_BACKEND'] = 'sqlite'
        os.environ['MARASSIM_DB_PATH'] = str(self.path)
        import config, db, database, access_control, rules
        config.reload()
        self.storage = Storage(self.path)
        # A request-scoped connection means legacy commits cannot split an API transaction.
        db.connect = self.storage.legacy_connect
        self.database, self.access, self.rules = database, access_control, rules
        self.all_modules = access_control.ALL_MODULES + analytics.REPORT_MODULES
        with self.storage.transaction(True) as conn:
            database.init_db()
            conn.execute(access_control.SCHEMA_USERS)
            conn.execute(access_control.SCHEMA_MODULE_ACCESS)
            cloud_sync.initialize(conn)
            conn.execute('CREATE TABLE IF NOT EXISTS omar_charge_details(charge_id INTEGER PRIMARY KEY REFERENCES charges_omar(id) ON DELETE CASCADE, details TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS reservation_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,reservation_id INTEGER NOT NULL,hall TEXT NOT NULL,event_date TEXT NOT NULL,bon TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
            conn.execute('CREATE TRIGGER IF NOT EXISTS notify_new_reservation AFTER INSERT ON reservations BEGIN INSERT INTO reservation_notifications(reservation_id,hall,event_date,bon) VALUES (NEW.id,NEW.salle,NEW.date_evenement,NEW.num_bon); END')
            for statement in analytics.SCHEMA.split(';'):
                if statement.strip():
                    conn.execute(statement)
            conn.execute('INSERT OR IGNORE INTO forecast_settings(id,opening_date) VALUES (1,?)', (date.today().isoformat(),))
            for table in list(TABLES.values()) + ['users', 'forecast_settings']:
                columns = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
                if 'revision' not in columns:
                    conn.execute(f'ALTER TABLE {table} ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
                conn.execute(f'CREATE TRIGGER IF NOT EXISTS version_{table} AFTER UPDATE ON {table} WHEN NEW.revision=OLD.revision BEGIN UPDATE {table} SET revision=OLD.revision+1 WHERE id=OLD.id; END')
            conn.execute('CREATE INDEX IF NOT EXISTS reservations_date_salle ON reservations(date_evenement,salle)')
            conn.execute('CREATE TABLE IF NOT EXISTS web_sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires REAL NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS idempotency (user_id INTEGER NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, response TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(user_id,key))')
            conn.execute('CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL, entity TEXT, entity_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            conn.execute('CREATE TABLE IF NOT EXISTS replicas (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, token_hash TEXT NOT NULL, last_seen TEXT, last_backup TEXT, last_sha256 TEXT, active INTEGER NOT NULL DEFAULT 1)')
        self.columns = {}
        with self.storage.transaction() as conn:
            for table in TABLES.values():
                self.columns[table] = {r['name']: r['type'] for r in conn.execute(f'PRAGMA table_info({table})')}
        self.templates = self.root / 'template'
        sync_templates(LEGACY / 'template', self.templates)
        self.backups = BackupManager(self.storage, self.root, self.templates)
        self.certificate, self.tls_key, self.fingerprint = ensure_certificate(self.root)
        self.bootstrap = self.root / 'bootstrap.key'
        if not self.bootstrap.exists():
            atomic_write(self.bootstrap, secrets.token_urlsafe(32).encode())
        self.stop = threading.Event()
        self.login_attempts = {}
        self.login_lock = threading.Lock()

    def require(self, user, *modules):
        if user['role'] != 'admin' and not any(m in user['modules'] for m in modules):
            raise APIError('Votre compte n’a pas accès à ce module.', 403)

    def require_admin(self, user):
        if user['role'] != 'admin':
            raise APIError('Accès réservé à l’administrateur.', 403)

    def public_user(self, conn, row):
        user = {k: row[k] for k in ('id', 'username', 'nom', 'prenom', 'role', 'actif', 'revision')}
        user['modules'] = self.all_modules if user['role'] == 'admin' else [r[0] for r in conn.execute('SELECT module_name FROM module_access WHERE user_id=? AND can_access=1', (row['id'],))]
        return user

    def authenticate(self, conn, headers):
        raw = headers.get('Authorization', '')
        if not raw.startswith('Bearer '):
            raise APIError('Veuillez vous connecter.', 401)
        row = conn.execute('SELECT u.* FROM users u JOIN web_sessions s ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.actif=1', (token_hash(raw[7:]), time.time())).fetchone()
        if not row:
            raise APIError('Session expirée. Reconnectez-vous.', 401)
        return self.public_user(conn, row)

    def audit(self, conn, user, action, entity='', entity_id=None):
        conn.execute('INSERT INTO audit_log(user_id,action,entity,entity_id) VALUES (?,?,?,?)', (user['id'], action, entity, entity_id))

    def existing(self, conn, table, entity_id, revision=None):
        row = conn.execute(f'SELECT * FROM {table} WHERE id=?', (entity_id,)).fetchone()
        if row is None:
            raise APIError('Cet élément n’existe plus. Actualisez la liste.', 404)
        if revision is not None and str(row['revision']) != str(revision):
            raise APIError('Un autre poste a modifié cet élément. Rechargez-le avant de continuer.', 409)
        return dict(row)

    def clean(self, table, payload):
        if not isinstance(payload, dict):
            raise APIError('Formulaire invalide.')
        unknown = set(payload) - set(self.columns[table]) - {'salles', 'revision', 'employeeRevision'}
        if unknown:
            raise APIError('Champs inconnus : ' + ', '.join(sorted(unknown)))
        result = {k: v for k, v in payload.items() if k in self.columns[table] and k not in {'id', 'revision', 'created_at', 'num_bon'}}
        if table == 'reservations' and any(k.startswith(('omar_statut', 'omar_date_accept')) for k in result):
            raise APIError('La validation Omar doit passer par le Centre de Réception.', 403)
        for key, value in result.items():
            kind = self.columns[table][key]
            if value == '' and kind in ('REAL', 'INTEGER'):
                result[key] = None
            elif value is not None and kind in ('REAL', 'INTEGER'):
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    raise APIError(f'Valeur numérique invalide : {key}.')
                if not math.isfinite(number) or (kind == 'INTEGER' and not number.is_integer()):
                    raise APIError(f'Valeur numérique invalide : {key}.')
                if number < 0 and key != 'priorite':
                    raise APIError(f'La valeur {key} ne peut pas être négative.')
                result[key] = int(number) if kind == 'INTEGER' else round(number, 3)
            elif value is not None:
                if not isinstance(value, str) or len(value) > 10000:
                    raise APIError(f'Texte invalide : {key}.')
                if ('date' in key or key in ('periode_debut', 'periode_fin')) and value:
                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        raise APIError(f'Date invalide : {key}.')
                if 'heure' in key and value and not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', value):
                    raise APIError(f'Heure invalide : {key}.')
            if key in {'date_evenement', 'date_cin', 'date_contrat', 'date_signature', 'date_reste', 'date_cheque_virement', 'violoniste_date', 'date_acompte1', 'date_acompte2', 'date_acompte3', 'date_debut', 'date_fin', 'heure_fin_max', 'violon_debut_min', 'violon_fin_max'} and not value:
                result[key] = None
        return result

    def validate_reservation(self, data, exclude_id=None, complexe=False):
        for key in ('nom_client', 'salle', 'date_evenement', 'heure_debut', 'heure_fin'):
            if not data.get(key):
                raise APIError(f'Champ obligatoire : {key}.')
        if data['salle'] not in self.rules.SALLES:
            raise APIError('Salle inconnue.')
        total = sum(data.get(f'acompte{i}') or 0 for i in range(1, 4))
        forfait = data.get('forfait') or 0
        if total > forfait and forfait > 0:
            raise APIError('Le total des acomptes dépasse le forfait.')
        methode = data.get('methode_paiement')
        if methode in ('Chèque', 'Virement', 'Effet') and not data.get('is_temporaire'):
            if not all(data.get(k) for k in ('num_cheque_virement', 'banque', 'date_cheque_virement')):
                raise APIError('N° de pièce, banque et date obligatoires pour chèque, virement ou effet.')
        if data.get('is_temporaire'):
            # Temporary holds keep flexible hours but still reserve the actual resource.
            ok, message = self.rules.check_salle_slot_conflict(None, data['salle'], data['date_evenement'], data['heure_debut'], data['heure_fin'], exclude_id)
        else:
            ok, message = self.rules.validate_reservation(data, exclude_id, complexe)
            reste = data.get('reste_acompte') or 0
            if forfait and reste >= forfait * 0.5:
                deadline = date.fromisoformat(data['date_evenement']) - timedelta(days=15)
                if not data.get('date_reste') or date.fromisoformat(data['date_reste']) > deadline:
                    raise APIError('La date du reste doit être au moins 15 jours avant l’événement.')
        if not ok:
            raise APIError(message, 409)

    def dispatch(self, method, url, headers, payload, peer='127.0.0.1'):
        parsed = urlparse(url)
        path = parsed.path.removeprefix('/api').rstrip('/') or '/'
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if path == '/health' and method == 'GET':
            with self.storage.transaction() as conn:
                setup = conn.execute('SELECT COUNT(*) FROM users WHERE actif=1').fetchone()[0] == 0
            return {'ok': True, 'application': 'marassim', 'version': '3.3.0', 'needsSetup': setup, 'fingerprint': self.fingerprint}
        if path.startswith('/replica/'):
            return self.replica_route(method, path, headers, payload)
        if path.startswith('/cloud/relay/'):
            return cloud_sync.relay_route(self,method,path,headers,query)
        if path == '/backups' and method == 'POST':
            with self.storage.transaction() as conn:
                user = self.authenticate(conn, headers)
                self.require_admin(user)
            metadata = self.backups.create()
            with self.storage.transaction(True) as conn:
                self.audit(conn, user, 'backup_created')
            return metadata
        is_mutation = method != 'GET' and not path.startswith('/exports/')
        with self.storage.transaction(is_mutation) as conn:
            if path == '/setup' and method == 'POST':
                if peer not in ('127.0.0.1', '::1') or not hmac.compare_digest(headers.get('X-Bootstrap-Key', ''), self.bootstrap.read_text()):
                    raise APIError('Initialisez le compte sur le PC serveur.', 403)
                if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
                    raise APIError('Le serveur possède déjà des comptes.', 409)
                username = payload.get('username', '').strip()
                if not username or len(username) > 80:
                    raise APIError('Identifiant invalide.')
                conn.execute('INSERT INTO users(username,password_hash,nom,prenom,role) VALUES (?,?,?,?,?)', (username, password_hash(payload.get('password')), 'Administrateur', '', 'admin'))
                return {'ok': True}
            if path == '/login' and method == 'POST':
                with self.login_lock:
                    attempts = [t for t in self.login_attempts.get(peer, []) if t > time.time() - 300]
                    if len(attempts) >= 15:
                        raise APIError('Trop de tentatives. Réessayez dans 5 minutes.', 429)
                    attempts.append(time.time())
                    self.login_attempts[peer] = attempts
                row = conn.execute('SELECT * FROM users WHERE username=? AND actif=1', (payload.get('username'),)).fetchone()
                if not row or not password_matches(payload.get('password'), row['password_hash']):
                    raise APIError('Identifiant ou mot de passe incorrect.', 401)
                if not row['password_hash'].startswith('scrypt$') and len(payload['password']) >= 8:
                    conn.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash(payload['password']), row['id']))
                token = secrets.token_urlsafe(48)
                conn.execute('DELETE FROM web_sessions WHERE expires<?', (time.time(),))
                conn.execute('INSERT INTO web_sessions VALUES (?,?,?)', (token_hash(token), row['id'], time.time() + 12 * 3600))
                return {'token': token, 'user': self.public_user(conn, row)}
            user = self.authenticate(conn, headers)
            if path == '/me':
                return user
            if path == '/logout' and method == 'POST':
                conn.execute('DELETE FROM web_sessions WHERE token_hash=?', (token_hash(headers['Authorization'][7:]),))
                return {'ok': True}
            # All business writes need a durable, per-user idempotency key.
            key = headers.get('Idempotency-Key')
            fingerprint = hashlib.sha256((method + path + json.dumps(payload, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
            if is_mutation:
                if not key or len(key) > 100:
                    raise APIError('Clé de transaction manquante.')
                cached = conn.execute('SELECT * FROM idempotency WHERE user_id=? AND key=?', (user['id'], key)).fetchone()
                if cached:
                    if cached['fingerprint'] != fingerprint:
                        raise APIError('Cette clé a déjà servi pour une autre opération.', 409)
                    return json.loads(cached['response'])
            result = self.business_route(conn, user, method, path, query, payload)
            if is_mutation:
                conn.execute('INSERT INTO idempotency VALUES (?,?,?,?,?)', (user['id'], key, fingerprint, json.dumps(result), time.time()))
                self.audit(conn, user, method, path, payload.get('id'))
            return result

    def business_route(self, conn, user, method, path, query, payload):
        parts = path.strip('/').split('/')
        resource = parts[0]
        if path == '/notifications' and method == 'GET':
            self.require(user,'Réservations','Calendrier','Rapports avancés','Cash-flow prévu')
            latest=conn.execute('SELECT COALESCE(MAX(id),0) FROM reservation_notifications').fetchone()[0]
            after=int(query.get('after',latest))
            rows=[dict(r) for r in conn.execute('SELECT * FROM reservation_notifications WHERE id>? ORDER BY id LIMIT 100',(after,))]
            return {'serverId':conn.execute('SELECT server_id FROM cloud_meta WHERE id=1').fetchone()[0],'latest':rows[-1]['id'] if len(rows)==100 else latest,'items':rows}
        if path == '/cloud/agents':
            self.require_admin(user)
            if method == 'GET':
                return [dict(r) for r in conn.execute('SELECT id,name,active,last_seen FROM cloud_agents ORDER BY id')]
            if method == 'POST':
                name = payload.get('name','').strip()
                if not 1 <= len(name) <= 80: raise APIError('Nom du poste obligatoire.')
                token = secrets.token_urlsafe(48)
                conn.execute('INSERT INTO cloud_agents(name,token_hash) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET token_hash=excluded.token_hash,active=1', (name,token_hash(token)))
                return {'relayToken':token}
        if resource == 'cloud' and len(parts)==3 and parts[1]=='agents' and method=='DELETE':
            self.require_admin(user)
            conn.execute('UPDATE cloud_agents SET active=0 WHERE id=?',(int(parts[2]),))
            return {'ok':True}
        if path == '/reports' and method == 'GET':
            self.require(user, 'Rapports avancés')
            return analytics.report(conn, self.database, query)
        if path == '/forecast' and method == 'GET':
            self.require(user, 'Cash-flow prévu')
            return analytics.forecast(conn, query)
        if path == '/forecast/settings' and method == 'PUT':
            self.require(user, 'Cash-flow prévu')
            if 'revision' not in payload:
                raise APIError('Rechargez les hypothèses avant de les modifier.', 428)
            self.existing(conn, 'forecast_settings', 1, payload['revision'])
            data = analytics.validate_settings(payload)
            conn.execute(f'UPDATE forecast_settings SET {",".join(k+"=?" for k in data)} WHERE id=1', list(data.values()))
            return self.existing(conn, 'forecast_settings', 1)
        if resource == 'status' and method == 'GET':
            self.require_admin(user)
            replicas = [dict(r) for r in conn.execute('SELECT id,name,last_seen,last_backup,last_sha256,active FROM replicas ORDER BY id')]
            manifests = self.backups.manifests()
            latest = manifests[0] if manifests else None
            verified = sum(bool(latest and r['active'] and r['last_backup'] == latest['name'] and r['last_sha256'] == latest['sha256']) for r in replicas)
            return {'server': socket.gethostname(), 'fingerprint': self.fingerprint, 'latest': latest, 'replicas': replicas, 'verifiedCopies': (1 if latest else 0) + verified, 'backupError': self.backups.last_error, 'backupHour': '19:00', 'retentionDays': 30}
        if resource == 'replicas':
            self.require_admin(user)
            if method == 'POST':
                name = payload.get('name', '').strip()
                if not 1 <= len(name) <= 80:
                    raise APIError('Nom du poste obligatoire.')
                token = secrets.token_urlsafe(48)
                row = conn.execute('SELECT id FROM replicas WHERE name=?', (name,)).fetchone()
                if (not row or not conn.execute('SELECT active FROM replicas WHERE name=?', (name,)).fetchone()[0]) and conn.execute('SELECT COUNT(*) FROM replicas WHERE active=1').fetchone()[0] >= 4:
                    raise APIError('Les 4 postes sont déjà enregistrés. Révoquez un ancien poste avant d’en ajouter un.')
                conn.execute('INSERT INTO replicas(name,token_hash) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET token_hash=excluded.token_hash, active=1,last_backup=NULL,last_sha256=NULL', (name, token_hash(token)))
                return {'replicaToken': token, 'name': name, 'certificate': self.certificate.read_text()}
            if method == 'DELETE' and len(parts) == 2:
                conn.execute('UPDATE replicas SET active=0 WHERE id=?', (int(parts[1]),))
                return {'ok': True}
        if resource == 'users':
            self.require_admin(user)
            if method == 'GET':
                return [self.public_user(conn, r) for r in conn.execute('SELECT * FROM users ORDER BY nom,prenom')]
            if method in ('POST', 'PUT'):
                data = {k: payload.get(k) for k in ('username', 'nom', 'prenom', 'role', 'actif') if k in payload}
                if method == 'POST':
                    if not data.get('username') or not data.get('nom'):
                        raise APIError('Identifiant et nom obligatoires.')
                    data['password_hash'] = password_hash(payload.get('password'))
                    data.setdefault('actif', 1)
                elif payload.get('password'):
                    data['password_hash'] = password_hash(payload['password'])
                if data.get('role', 'employe') not in self.access.ROLE_PERMISSIONS:
                    raise APIError('Rôle invalide.')
                if method == 'POST':
                    columns = list(data)
                    entity_id = conn.execute(f'INSERT INTO users ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', list(data.values())).lastrowid
                else:
                    entity_id = int(parts[1])
                    old = conn.execute('SELECT * FROM users WHERE id=?', (entity_id,)).fetchone()
                    if not old:
                        raise APIError('Utilisateur introuvable.', 404)
                    if 'revision' not in payload:
                        raise APIError('Rechargez le compte avant de le modifier.', 428)
                    if old['revision'] != payload['revision']:
                        raise APIError('Un autre poste a modifié ce compte. Rechargez-le.', 409)
                    if old['role'] == 'admin' and (data.get('role', 'admin') != 'admin' or data.get('actif', 1) == 0):
                        if conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND actif=1 AND id<>?", (entity_id,)).fetchone()[0] == 0:
                            raise APIError('Conservez au moins un administrateur actif.')
                    if data:
                        conn.execute(f'UPDATE users SET {",".join(k+"=?" for k in data)} WHERE id=?', list(data.values()) + [entity_id])
                    conn.execute('DELETE FROM web_sessions WHERE user_id=?', (entity_id,))
                modules = payload.get('modules', self.access.ROLE_PERMISSIONS[data.get('role', 'employe')])
                if not isinstance(modules, list) or any(m not in self.all_modules for m in modules):
                    raise APIError('Permissions invalides.')
                conn.execute('DELETE FROM module_access WHERE user_id=?', (entity_id,))
                conn.executemany('INSERT INTO module_access(user_id,module_name,can_access) VALUES (?,?,1)', [(entity_id, m) for m in set(modules)])
                if method == 'PUT' and not data:
                    conn.execute('UPDATE users SET revision=revision+1 WHERE id=?', (entity_id,))
                return {'id': entity_id}
        if resource == 'journal' and method == 'GET':
            omar = query.get('caisse') == 'omar'
            self.require(user, 'Journal Caisse Omar' if omar else 'Journal de Caisse')
            start, end = query.get('start', date.today().replace(day=1).isoformat()), query.get('end', date.today().isoformat())
            date.fromisoformat(start); date.fromisoformat(end)
            if start > end:
                raise APIError('La date de fin précède le début de la période.')
            return omar_cash.journal(conn, self.database, start, end) if omar else self.database.get_journal_caisse(start, end)
        if resource == 'employees' and len(parts) == 2 and parts[1] == 'options' and method == 'GET':
            self.require(user, 'Liste employés', 'Ajouter employé', 'Pointage')
            return self.database.get_all_employees()
        if path == '/pointage/events' and method == 'GET':
            self.require(user, 'Pointage')
            day = query.get('date', date.today().isoformat())
            if date.fromisoformat(day).isoformat() != day:
                raise APIError('Date de soirée invalide.')
            return [dict(r) for r in conn.execute('SELECT id,salle,date_evenement,heure_debut,heure_fin FROM reservations WHERE date_evenement=? AND COALESCE(is_temporaire,0)=0 ORDER BY heure_debut,salle,id', (day,))]
        if resource == 'pointage' and len(parts) == 2 and parts[1] == 'batch' and method == 'POST':
            self.require(user, 'Pointage')
            entries = payload.get('entries')
            if not isinstance(entries, list) or not 1 <= len(entries) <= 500:
                raise APIError('Sélectionnez au moins un employé et une période.')
            ids, nuit, charge_details = [], {}, []
            session_date, notes = None, payload.get('notes') or None
            for entry in entries:
                data = self.clean('pointage', entry)
                employee = self.existing(conn, 'employees', data.get('employee_id'))
                if not employee['actif']:
                    raise APIError('Un employé sélectionné est inactif.')
                if data.get('periode') not in ('midi', 'apres_midi', 'soiree', 'journee_complete'):
                    raise APIError('Période de pointage invalide.')
                day = data.get('date_pointage')
                date.fromisoformat(day)
                if session_date and session_date != day:
                    raise APIError('Une session de pointage doit concerner une seule date.')
                session_date = day
                if conn.execute('SELECT id FROM pointage WHERE employee_id=? AND date_pointage=? AND periode=?', (employee['id'], day, data['periode'])).fetchone():
                    raise APIError(f"{employee['nom']} est déjà pointé pour cette période.", 409)
                data['notes'] = notes
                ids.append(self.database.insert_pointage(data))
                if employee.get('type_ouvrier') == 'nuit':
                    tariff_field = {'midi': 'salaire_midi', 'apres_midi': 'salaire_apres_midi', 'soiree': 'salaire_soiree', 'journee_complete': 'salaire_journalier'}[data['periode']]
                    amount = (employee.get(tariff_field) or 0) + (data.get('heures_supplementaires') or 0) * (employee.get('prix_heure_supp') or 0)
                    charge_details.append({'name': f"{employee['nom']} {employee['prenom']}".strip(), 'period': {'midi': 'Midi', 'apres_midi': '15H', 'soiree': '21H', 'journee_complete': 'Journée complète'}[data['periode']], 'amount': analytics.number(amount), 'pointageId': ids[-1]})
                    nuit.setdefault(employee['id'], {'employee': employee, 'amount': 0})['amount'] += amount
            total = sum(item['amount'] for item in nuit.values())
            if total > 0:
                event_ids = payload.get('eventIds')
                if event_ids is not None and (not isinstance(event_ids,list) or len(event_ids)>30 or any(type(i) is not int for i in event_ids) or len(set(event_ids))!=len(event_ids)):
                    raise APIError('Sélection de soirées invalide.')
                events = [dict(r) for r in conn.execute('SELECT id,salle,heure_debut FROM reservations WHERE date_evenement=? AND COALESCE(is_temporaire,0)=0 ORDER BY heure_debut,salle,id', (session_date,))]
                if event_ids is not None:
                    if set(event_ids)-{r['id'] for r in events}: raise APIError('Une soirée sélectionnée ne correspond plus à cette date. Rechargez le pointage.',409)
                    events = [r for r in events if r['id'] in event_ids]
                else:
                    periods = {d['period'] for d in charge_details}
                    events = [r for r in events if ('21H' if int(r['heure_debut'][:2])>=19 else '15H' if int(r['heure_debut'][:2])>=13 else 'Midi') in periods or 'Journée complète' in periods]
                labels = ' ET '.join(f"{r['salle'].upper()} {r['heure_debut'].replace(':00','H').replace(':','H')}" for r in events)
                designation = f"Dépense Soirée le {datetime.strptime(session_date, '%Y-%m-%d').strftime('%d/%m/%Y')}"
                if labels: designation += ' ' + labels
                if notes: designation += ' · ' + notes
                charge_id = self.database.insert_charge_omar(session_date, designation, round(total, 3))
                conn.execute('INSERT INTO omar_charge_details(charge_id,details) VALUES (?,?)', (charge_id, json.dumps(charge_details, ensure_ascii=False)))
            for employee_id in {entry['employee_id'] for entry in entries}:
                conn.execute('UPDATE employees SET revision=revision+1 WHERE id=?', (employee_id,))
            return {'ids': ids, 'omarCharge': round(total, 3)}
        if resource == 'reception':
            self.require(user, 'Centre de Réception')
            if method == 'GET':
                result = self.database.get_acomptes_caisse_omar()
                for item in result:
                    item['revision'] = self.existing(conn, 'reservations', item['res_id'])['revision']
                return result
            if method == 'POST':
                entity_id = int(payload['res_id'])
                slot = int(payload['slot'])
                row = self.existing(conn, 'reservations', entity_id, payload.get('revision'))
                if 'revision' not in payload:
                    raise APIError('Rechargez la réservation avant de valider.', 428)
                if not row.get(f'num_caisse_omar{slot}'):
                    raise APIError('Cet acompte ne contient pas de recette Omar.')
                if payload.get('statut') not in ('accepte', 'refuse', None):
                    raise APIError('Statut invalide.')
                self.database.update_omar_statut(entity_id, slot, payload.get('statut'))
                return self.existing(conn, 'reservations', entity_id)
        if resource == 'exports' and method in ('GET', 'POST'):
            return self.export(conn, user, parts, query, payload)
        if resource == 'employees' and len(parts) == 3 and parts[2] == 'fiche' and method == 'GET':
            self.require(user, 'Liste employés', 'Pointage')
            return self.database.get_employee_fiche_data(int(parts[1]))
        if resource == 'reservations' and len(parts) == 3 and parts[2] == 'payments' and method == 'POST':
            self.require(user, 'Ajouter un acompte')
            entity_id = int(parts[1])
            if 'revision' not in payload:
                raise APIError('Rechargez le bon avant d’ajouter un acompte.', 428)
            self.existing(conn, 'reservations', entity_id, payload['revision'])
            amount = float(payload.get('montant', 0))
            if not math.isfinite(amount) or amount <= 0:
                raise APIError('Le montant doit être positif.')
            method_payment = payload.get('methode', 'Espèce')
            if method_payment not in ('Espèce', 'Chèque', 'Virement', 'Effet'):
                raise APIError('Méthode de paiement invalide.')
            if method_payment != 'Espèce' and not payload.get('num_ref'):
                raise APIError('Numéro de pièce obligatoire.')
            self.database.add_acompte(entity_id, round(amount, 3), method_payment, payload.get('num_ref'), payload.get('num_caisse'), payload.get('num_caisse_omar'))
            return self.existing(conn, 'reservations', entity_id)
        if resource in TABLES:
            table = TABLES[resource]
            permissions = MODULES[resource]
            if method == 'GET':
                if resource == 'reservations':
                    self.require(user, permissions[0], 'Calendrier', 'Ajouter un acompte', 'Modifier réservation', 'Centre de Réception')
                elif resource == 'employee-payments':
                    self.require(user, 'Liste employés', 'Pointage')
                else:
                    self.require(user, permissions[0])
                if len(parts) == 2:
                    return self.existing(conn, table, int(parts[1]))
                return [dict(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY id DESC')]
            if resource == 'employee-payments' and method == 'POST':
                self.require(user, 'Liste employés', 'Pointage')
            else:
                self.require(user, permissions[1] if method == 'POST' else permissions[0] if method == 'DELETE' else permissions[2])
            if resource == 'pointage':
                raise APIError('Utilisez le pointage collectif pour préserver la charge Caisse Omar.', 405)
            entity_id = int(parts[1]) if len(parts) == 2 else None
            if method in ('PUT', 'DELETE'):
                if 'revision' not in payload:
                    raise APIError('Version de l’élément manquante. Rechargez-le.', 428)
                old = self.existing(conn, table, entity_id, payload['revision'])
            if method == 'DELETE':
                if resource == 'reservations':
                    self.require(user, 'Réservations')
                if resource == 'forecast-items':
                    conn.execute("UPDATE forecast_items SET state='cancelled' WHERE id=?", (entity_id,))
                elif resource == 'employees':
                    conn.execute('UPDATE employees SET actif=0 WHERE id=?', (entity_id,))
                else:
                    if resource == 'employee-payments':
                        if 'employeeRevision' not in payload:
                            raise APIError('Rechargez la fiche employé avant de supprimer ce paiement.', 428)
                        self.existing(conn, 'employees', old['employee_id'], payload['employeeRevision'])
                        conn.execute('UPDATE employees SET revision=revision+1 WHERE id=?', (old['employee_id'],))
                    conn.execute(f'DELETE FROM {table} WHERE id=?', (entity_id,))
                return {'ok': True}
            data = self.clean(table, payload)
            if resource == 'forecast-items':
                if method == 'POST':
                    data.setdefault('category', 'Autre')
                    data.setdefault('frequency', 'once')
                    data.setdefault('state', 'planned')
                analytics.validate_item(dict(old, **data) if method == 'PUT' else data)
            if resource == 'reservations':
                if method == 'POST':
                    salles = payload.get('salles') or [data.get('salle')]
                    if not isinstance(salles, list) or not salles or len(set(salles)) != len(salles) or any(s not in self.rules.SALLES for s in salles):
                        raise APIError('Sélection de salles invalide.')
                    data.setdefault('date_signature', date.today().isoformat())
                    data['dossier_traite_par'] = (user.get('prenom', '') + ' ' + user['nom']).strip()
                    # All availability checks and all inserts share BEGIN IMMEDIATE.
                    for salle in salles:
                        self.validate_reservation(dict(data, salle=salle), complexe=set(salles) == set(self.rules.SALLES))
                    result = []
                    for salle in salles:
                        row = dict(data, salle=salle)
                        new_id, _ = self.database.insert_reservation_with_bon(row, prefix='TMP' if row.get('is_temporaire') else 'BON')
                        result.append(self.existing(conn, table, new_id))
                    return result
                candidate = dict(old, **data)
                self.validate_reservation(candidate, entity_id)
                if old.get('is_temporaire') and not candidate.get('is_temporaire'):
                    conn.execute('UPDATE reservations SET num_bon=? WHERE id=?', (f'BON-{date.today().year}-{entity_id:04d}', entity_id))
            if resource == 'rules':
                candidate = dict(old, **data) if method == 'PUT' else data
                if candidate.get('salle') not in self.rules.SALLES + ['*']:
                    raise APIError('Salle de règle invalide.')
                if not candidate.get('nom'):
                    raise APIError('Nom de règle obligatoire.')
                for slot in (candidate.get('creneaux') or '').split(';'):
                    if slot and not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d', slot.strip()):
                        raise APIError('Créneau invalide : utilisez 15:00-18:00;21:00-01:00.')
                if candidate.get('jours') and not re.fullmatch(r'[0-6](,[0-6])*', candidate['jours']):
                    raise APIError('Jours invalides : 0=lundi, …, 6=dimanche.')
                if candidate.get('date_debut') and candidate.get('date_fin') and candidate['date_debut'] > candidate['date_fin']:
                    raise APIError('La fin de la période précède le début.')
            if resource in ('pointage', 'employee-payments'):
                employee_id = data.get('employee_id', old.get('employee_id') if method == 'PUT' else None)
                self.existing(conn, 'employees', employee_id)
            if resource == 'pointage':
                if data.get('periode', old.get('periode') if method == 'PUT' else None) not in ('midi', 'apres_midi', 'soiree', 'journee_complete'):
                    raise APIError('Période de pointage invalide.')
                duplicate = conn.execute('SELECT id FROM pointage WHERE employee_id=? AND date_pointage=? AND periode=? AND id<>?', (employee_id, data.get('date_pointage', old.get('date_pointage') if method == 'PUT' else None), data.get('periode', old.get('periode') if method == 'PUT' else None), entity_id or 0)).fetchone()
                if duplicate:
                    raise APIError('Cet employé est déjà pointé pour cette période.', 409)
            if resource == 'employee-payments':
                candidate = dict(old, **data) if method == 'PUT' else data
                if candidate.get('periode_debut', '') > candidate.get('periode_fin', ''):
                    raise APIError('Période de paiement invalide.')
                if not candidate.get('montant_total') or candidate['montant_total'] <= 0:
                    raise APIError('Le montant du paiement doit être positif.')
                if 'employeeRevision' not in payload:
                    raise APIError('Sélectionnez à nouveau l’employé avant d’enregistrer le paiement.', 428)
                self.existing(conn, 'employees', employee_id, payload['employeeRevision'])
            if method == 'POST':
                columns = list(data)
                if not columns:
                    raise APIError('Formulaire vide.')
                entity_id = conn.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', list(data.values())).lastrowid
            elif method == 'PUT':
                if data:
                    conn.execute(f'UPDATE {table} SET {",".join(k+"=?" for k in data)} WHERE id=?', list(data.values()) + [entity_id])
            else:
                raise APIError('Méthode non autorisée.', 405)
            if resource == 'employee-payments':
                conn.execute('UPDATE employees SET revision=revision+1 WHERE id=?', (employee_id,))
            return self.existing(conn, table, entity_id)
        raise APIError('Page introuvable.', 404)

    def export(self, conn, user, parts, query, payload):
        import contract_generator, excel_export
        contract_generator.TEMPLATE_PATH = str(self.templates / 'Bon_Recu_Marassim_Template.docx')
        contract_generator.ARABIC_TEMPLATE_PATH = str(self.templates / 'Contrat_Arabe_Template.docx')
        with tempfile.TemporaryDirectory() as temp:
            if parts[1] in ('reports', 'forecast'):
                kind = parts[1]
                self.require(user, 'Rapports avancés' if kind == 'reports' else 'Cash-flow prévu')
                data = analytics.report(conn, self.database, query) if kind == 'reports' else analytics.forecast(conn, query)
                period = data['period'] if kind == 'reports' else data['parameters']
                name = f"Marassim_{kind}_{period['start']}_{period['end']}.xlsx"
                file = Path(temp) / name
                analytics.export_workbook(data, kind, file)
            elif parts[1] == 'calendar':
                self.require(user, 'Export Excel')
                year, month = int(query.get('year', date.today().year)), int(query.get('month', date.today().month))
                if not 2000 <= year <= 2200 or not 1 <= month <= 12:
                    raise APIError('Mois ou année invalide.')
                name = f'Calendrier_Marassim_{year}_{month:02d}.xlsx'
                file = Path(temp) / name
                excel_export.export_month_calendar(year, month, str(file))
            elif parts[1] in ('contract', 'arabic', 'draft-contract', 'draft-arabic'):
                self.require(user, 'Réservations', 'Nouvelle réservation', 'Modifier réservation')
                draft = parts[1].startswith('draft-')
                row = self.clean('reservations', payload.get('reservation', {})) if draft else self.existing(conn, 'reservations', int(parts[2]))
                if draft:
                    row['num_bon'] = 'BROUILLON'
                name = f"{row.get('num_bon') or row.get('id', 'BROUILLON')}{'_AR' if parts[1].endswith('arabic') else ''}.docx"
                file = Path(temp) / name
                if parts[1].endswith('arabic'):
                    contract_generator.generate_arabic_contract(row, payload.get('arabic', {}), str(file))
                else:
                    contract_generator.generate_contract(row, str(file))
            elif parts[1] == 'table':
                from online_exports import export_table
                resource = query.get('resource', '')
                name = f'Marassim_{resource}.xlsx'
                file = Path(temp) / name
                export_table(self, conn, user, resource, query, file)
            elif parts[1] == 'journal':
                from legacy_exports import export_journal
                omar = query.get('caisse') == 'omar'
                self.require(user, 'Journal Caisse Omar' if omar else 'Journal de Caisse')
                start, end = query['start'], query['end']
                date.fromisoformat(start); date.fromisoformat(end)
                if start > end:
                    raise APIError('La date de fin précède le début de la période.')
                kind = query.get('format', 'xlsx')
                if kind not in ('xlsx', 'pdf') or (kind == 'pdf' and not omar):
                    raise APIError('Format de journal invalide.')
                name = f"Journal_Caisse_{'Omar_' if omar else ''}{start}_{end}.{kind}"
                file = Path(temp) / name
                if omar:
                    data = omar_cash.journal(conn, self.database, start, end)
                    (omar_cash.export_pdf if kind == 'pdf' else omar_cash.export_excel)(data, file)
                else:
                    export_journal(self.database, False, start, end, str(file), query.get('number') or '?')
            else:
                raise APIError('Export inconnu.', 404)
            return {'name': name, 'base64': base64.b64encode(file.read_bytes()).decode()}

    def replica_route(self, method, path, headers, payload):
        raw = headers.get('Authorization', '')
        if not raw.startswith('Replica '):
            raise APIError('Poste non enregistré.', 401)
        with self.storage.transaction(method != 'GET') as conn:
            replica = conn.execute('SELECT * FROM replicas WHERE token_hash=? AND active=1', (token_hash(raw[8:]),)).fetchone()
            if not replica:
                raise APIError('Autorisation de copie révoquée.', 401)
            manifests = self.backups.manifests()
            if method == 'GET' and path == '/replica/backups':
                return manifests
            if method == 'GET' and path.startswith('/replica/backups/'):
                name = path.split('/')[-1]
                if not any(m['name'] == name for m in manifests):
                    raise APIError('Sauvegarde introuvable.', 404)
                return (self.backups.root / name).read_bytes()
            if method == 'POST' and path == '/replica/ack':
                if not any(m['name'] == payload.get('name') and m['sha256'] == payload.get('sha256') for m in manifests):
                    raise APIError('Empreinte de sauvegarde invalide.', 409)
                conn.execute('UPDATE replicas SET last_seen=?,last_backup=?,last_sha256=? WHERE id=?', (datetime.now().isoformat(), payload['name'], payload['sha256'], replica['id']))
                return {'ok': True}
        raise APIError('Page introuvable.', 404)


def serve(application, host='0.0.0.0', port=7443, insecure=False):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def do_GET(self): self.handle_api()
        def do_POST(self): self.handle_api()
        def do_PUT(self): self.handle_api()
        def do_DELETE(self): self.handle_api()

        def handle_api(self):
            status = 200
            try:
                if not self.path.startswith('/api/'):
                    raise APIError('Page introuvable.', 404)
                if self.headers.get('Transfer-Encoding'):
                    raise APIError('Encodage non pris en charge.')
                length = int(self.headers.get('Content-Length', 0))
                if length < 0 or length > 1024 * 1024:
                    raise APIError('Formulaire trop volumineux.', 413)
                body = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(body, dict):
                    raise APIError('Formulaire invalide.')
                result = application.dispatch(self.command, self.path, self.headers, body, self.client_address[0])
            except APIError as error:
                status, result = error.status, {'error': str(error)}
            except sqlite3.IntegrityError:
                status, result = 409, {'error': 'Données manquantes, référence invalide ou élément déjà existant.'}
            except (ValueError, KeyError, TypeError) as error:
                status, result = 400, {'error': str(error) or 'Formulaire invalide.'}
            except Exception:
                logging.exception('API request failed: %s %s', self.command, self.path)
                status, result = 500, {'error': 'Le serveur n’a pas enregistré cette opération. Consultez le journal serveur.'}
            binary = isinstance(result, bytes)
            content = result if binary else json.dumps(result, ensure_ascii=False).encode()
            try:
                self.send_response(status)
                self.send_header('Content-Type', 'application/octet-stream' if binary else 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass
            self.close_connection = True

        def log_message(self, *_):
            pass  # Do not log client secrets or request bodies.

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    if not insecure:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(application.certificate, application.tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    parser.add_argument('--source')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=7443)
    parser.add_argument('--replica')
    parser.add_argument('--online-sync')
    parser.add_argument('--restore')
    parser.add_argument('--key')
    parser.add_argument('--destination')
    args = parser.parse_args()
    if args.online_sync:
        try: cloud_sync.sync_online(args.online_sync)
        except Exception: raise SystemExit(1)
        return
    if args.replica:
        replica_root = Path(args.replica).parent
        from logging.handlers import RotatingFileHandler
        logging.basicConfig(handlers=[RotatingFileHandler(replica_root / 'replica.log', maxBytes=1024 * 1024, backupCount=2)], level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        try:
            sync_replica(args.replica)
        except Exception:
            logging.exception('La copie de sauvegarde a échoué ; elle sera réessayée au prochain passage.')
            raise
        return
    if args.restore:
        restore_backup(args.restore, args.key, args.destination)
        return
    if not args.data_dir:
        parser.error('--data-dir est obligatoire pour démarrer le serveur.')
    root = Path(args.data_dir)
    root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=root / 'server.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    application = Application(root, args.source)
    server = serve(application, args.host, args.port)
    threading.Thread(target=application.backups.scheduler, args=(application.stop,), daemon=True).start()
    try:
        server.serve_forever()
    finally:
        application.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
