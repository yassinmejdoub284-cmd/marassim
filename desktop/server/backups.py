"""Verified, encrypted snapshots; atomic replica downloads and offline recovery."""
import hashlib
import io
import json
import os
import sqlite3
import ssl
import tempfile
import threading
import urllib.request
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class BackupManager:
    def __init__(self, storage, data_dir, templates, retention=30):
        self.storage = storage
        self.root = Path(data_dir) / 'backups'
        self.root.mkdir(exist_ok=True)
        self.key_path = Path(data_dir) / 'recovery.key'
        if not self.key_path.exists():
            if any(self.root.glob('*.mrb')):
                raise RuntimeError('Clé de récupération absente : restaurer recovery.key avant de démarrer.')
            atomic_write(self.key_path, Fernet.generate_key())
        self.cipher = Fernet(self.key_path.read_bytes().strip())
        self.templates = Path(templates)
        self.retention = retention
        self.lock = threading.Lock()
        self.last_error = None

    def manifests(self):
        result = []
        for file in sorted(self.root.glob('*.json'), reverse=True):
            try:
                metadata = json.loads(file.read_text('utf-8'))
                if (self.root / metadata['name']).is_file():
                    result.append(metadata)
            except (OSError, ValueError, KeyError):
                continue
        return result

    def create(self):
        with self.lock:
            try:
                stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
                name = f'marassim_{stamp}.mrb'
                with tempfile.TemporaryDirectory(dir=self.root) as temp:
                    snapshot = Path(temp) / 'marassim.db'
                    source = self.storage.connect()
                    target = sqlite3.connect(snapshot)
                    try:
                        source.backup(target)
                        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                            raise RuntimeError('La sauvegarde a échoué au contrôle d’intégrité.')
                    finally:
                        target.close()
                        source.close()
                    stream = io.BytesIO()
                    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                        archive.write(snapshot, 'marassim.db')
                        for file in self.templates.glob('*.docx'):
                            archive.write(file, 'template/' + file.name)
                        archive.writestr('metadata.json', json.dumps({'format': 1, 'created_at': datetime.now().isoformat(), 'database_sha256': digest(snapshot)}))
                    atomic_write(self.root / name, self.cipher.encrypt(stream.getvalue()))
                metadata = {'name': name, 'created_at': datetime.now().isoformat(), 'sha256': digest(self.root / name), 'bytes': (self.root / name).stat().st_size, 'key_id': hashlib.sha256(self.key_path.read_bytes().strip()).hexdigest()}
                atomic_write(self.root / (name + '.json'), json.dumps(metadata).encode())
                # Keep 30 calendar days; manual backups do not consume daily slots.
                manifests = self.manifests()
                days = sorted({m['created_at'][:10] for m in manifests}, reverse=True)[:self.retention]
                for old in manifests:
                    if old['created_at'][:10] not in days:
                        (self.root / old['name']).unlink(missing_ok=True)
                        (self.root / (old['name'] + '.json')).unlink(missing_ok=True)
                self.last_error = None
                return metadata
            except Exception as error:
                self.last_error = str(error)
                raise

    def scheduler(self, stop):
        # First snapshot on startup, then at 19:00, with catch-up after downtime.
        while not stop.is_set():
            latest = self.manifests()
            now = datetime.now()
            due = now.replace(hour=19, minute=0, second=0, microsecond=0)
            last = datetime.fromisoformat(latest[0]['created_at']) if latest else None
            if last is None or last.date() < now.date() or (now >= due and last < due):
                try:
                    self.create()
                except Exception:
                    pass  # Reported in server status; retry in one minute.
            stop.wait(60)


def sync_replica(config_path):
    config = json.loads(Path(config_path).read_text('utf-8'))
    root = Path(config['backupDirectory'])
    root.mkdir(parents=True, exist_ok=True)
    server = config['serverUrl'].rstrip('/')
    if not server.startswith('https://'):
        raise ValueError('Les sauvegardes nécessitent HTTPS.')
    # Trust only the certificate explicitly paired on the server PC.
    context = ssl.create_default_context(cadata=config['certificate'])
    context.check_hostname = False
    headers = {'Authorization': 'Replica ' + config['replicaToken']}

    def request(path, body=None):
        req = urllib.request.Request(server + '/api' + path, headers=headers, data=None if body is None else json.dumps(body).encode())
        if body is not None:
            req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, context=context, timeout=120) as response:
            return response.read()

    manifests = json.loads(request('/replica/backups'))
    for metadata in reversed(manifests):
        name = metadata['name']
        if Path(name).name != name or not name.endswith('.mrb'):
            raise ValueError('Nom de sauvegarde invalide.')
        target = root / name
        if not target.exists() or digest(target) != metadata['sha256']:
            content = request('/replica/backups/' + name)
            if len(content) != metadata['bytes'] or hashlib.sha256(content).hexdigest() != metadata['sha256']:
                raise ValueError('Copie incomplète ou corrompue ; nouvelle tentative au prochain passage.')
            atomic_write(target, content)
        atomic_write(root / (name + '.json'), json.dumps(metadata).encode())
    if manifests:
        request('/replica/ack', {'name': manifests[0]['name'], 'sha256': manifests[0]['sha256']})
    # Prune only after all current backups have been verified and acknowledged.
    valid = {m['name'] for m in manifests}
    if manifests:
        cutoff = (datetime.fromisoformat(manifests[0]['created_at']) - timedelta(days=30)).isoformat()
        for old in root.glob('marassim_*.mrb'):
            metadata_path = old.with_name(old.name + '.json')
            if old.name not in valid and metadata_path.exists():
                try:
                    previous = json.loads(metadata_path.read_text('utf-8'))
                    # A new/empty/rebuilt server must never erase the surviving copies.
                    if previous.get('key_id') == manifests[0].get('key_id') and previous.get('key_id') and previous['created_at'] < cutoff:
                        old.unlink()
                        metadata_path.unlink(missing_ok=True)
                except (ValueError, KeyError, OSError):
                    continue
    atomic_write(root / 'last-sync.json', json.dumps({'synced_at': datetime.now().isoformat(), 'latest': manifests[0]['name'] if manifests else None}).encode())
    return len(manifests)


def restore_backup(backup, key, destination):
    """Restore to a NEW directory only; never overwrite a running database."""
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Le dossier de restauration doit être vide. Arrêtez le serveur avant de basculer vers ce dossier.')
    content = Fernet(Path(key).read_bytes().strip()).decrypt(Path(backup).read_bytes())
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        data = archive.read('marassim.db')
        metadata = json.loads(archive.read('metadata.json'))
        if hashlib.sha256(data).hexdigest() != metadata['database_sha256']:
            raise ValueError('Base corrompue dans la sauvegarde.')
        destination.mkdir(parents=True, exist_ok=True)
        atomic_write(destination / 'marassim.db', data)
        conn = sqlite3.connect(destination / 'marassim.db')
        try:
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Échec du contrôle de la base restaurée.')
            # Sessions and replica credentials are invalidated after disaster recovery.
            conn.execute('DELETE FROM web_sessions')
            conn.execute('DELETE FROM replicas')
            conn.execute('DELETE FROM idempotency')
            conn.commit()
        finally:
            conn.close()
        for name in archive.namelist():
            if name.startswith('template/') and Path(name).name == name[9:] and name.endswith('.docx'):
                atomic_write(destination / name, archive.read(name))
    atomic_write(destination / 'recovery.key', Path(key).read_bytes())
    return str(destination)
