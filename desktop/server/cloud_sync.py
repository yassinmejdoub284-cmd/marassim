"""A LAN client carries a consistent, sanitized snapshot to the read-only website."""
import base64
import hashlib
import io
import json
import secrets
import sqlite3
import ssl
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from backups import atomic_write

CHUNK = 750_000
MAX_ARCHIVE = 96 * 1024 * 1024
SCHEMA = '''CREATE TABLE IF NOT EXISTS cloud_meta(id INTEGER PRIMARY KEY CHECK(id=1),server_id TEXT NOT NULL,sequence INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cloud_agents(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,token_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,last_seen TEXT);'''
snapshot_lock = threading.Lock()

def initialize(conn):
    for statement in SCHEMA.split(';'):
        if statement.strip(): conn.execute(statement)
    conn.execute('INSERT OR IGNORE INTO cloud_meta(id,server_id) VALUES (1,?)',(str(uuid.uuid4()),))

def snapshot(application):
    # One process serves the LAN. The lock orders snapshots from all four relay PCs.
    with snapshot_lock:
        with application.storage.transaction(True) as conn:
            conn.execute('UPDATE cloud_meta SET sequence=sequence+1 WHERE id=1')
            meta = dict(conn.execute('SELECT * FROM cloud_meta WHERE id=1').fetchone())
        source = application.storage.connect(); copy = sqlite3.connect(':memory:')
        try:
            source.backup(copy)
            for table in ('web_sessions','idempotency','replicas','audit_log','cloud_agents'):
                copy.execute(f'DELETE FROM {table}')
            copy.commit(); copy.execute('PRAGMA journal_mode=DELETE'); copy.execute('VACUUM')
            blob = copy.serialize()
        finally:
            copy.close(); source.close()
        captured = datetime.now(timezone.utc).isoformat()
        output = io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('marassim.db',blob)
            archive.writestr('snapshot.json',json.dumps({'serverId':meta['server_id'],'sequence':meta['sequence'],'capturedAt':captured}))
            for file in application.templates.glob('*.docx'): archive.writestr('template/'+file.name,file.read_bytes())
        content = output.getvalue()
        if len(content) > MAX_ARCHIVE: raise ValueError('Copie en ligne trop volumineuse (96 Mo maximum).')
        identifier = uuid.uuid4().hex
        root = application.root/'cloud-export'; root.mkdir(exist_ok=True)
        manifest = {'id':identifier,'serverId':meta['server_id'],'sequence':meta['sequence'],'capturedAt':captured,'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'chunks':(len(content)+CHUNK-1)//CHUNK}
        atomic_write(root/(identifier+'.zip'),content)
        atomic_write(root/(identifier+'.json'),json.dumps(manifest).encode())
        for file in root.iterdir():
            if file.suffix in ('.zip','.json') and time.time()-file.stat().st_mtime > 3600: file.unlink(missing_ok=True)
        return manifest

def relay_route(application,method,path,headers,query):
    raw = headers.get('Authorization','')
    token = raw[11:] if raw.startswith('CloudRelay ') else ''
    with application.storage.transaction(True) as conn:
        row = conn.execute('SELECT id FROM cloud_agents WHERE token_hash=? AND active=1',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not token or not row:
            from app import APIError
            raise APIError('Relais en ligne non autorisé.',403)
        conn.execute('UPDATE cloud_agents SET last_seen=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),row['id']))
    if method == 'POST' and path == '/cloud/relay/snapshot': return snapshot(application)
    parts = path.strip('/').split('/')
    if method == 'GET' and len(parts)==4 and parts[:3]==['cloud','relay','snapshot']:
        identifier = parts[3]
        if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier): raise ValueError('Copie invalide.')
        root = application.root/'cloud-export'
        manifest = json.loads((root/(identifier+'.json')).read_text())
        index = int(query.get('chunk',0))
        if not 0 <= index < manifest['chunks']: raise ValueError('Fragment invalide.')
        with (root/(identifier+'.zip')).open('rb') as file:
            file.seek(index*CHUNK); content=file.read(CHUNK)
        return {'data':base64.b64encode(content).decode()}
    from app import APIError
    raise APIError('Page introuvable.',404)

def online_origin(value):
    url = urlparse(value)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        raise ValueError('Indiquez uniquement l’adresse HTTPS de votre application en ligne.')
    return value.rstrip('/')

def json_request(url,body=None,headers=None,context=None):
    request = Request(url,headers={'Content-Type':'application/json',**(headers or {})},data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request,context=context,timeout=60) as response: return json.load(response)

def sync_online(config_path):
    from cryptography.fernet import Fernet
    path = Path(config_path); config = json.loads(path.read_text())
    status_path = path.with_name('online-status.json')
    try:
        website = online_origin(config['onlineUrl'])
        secret = config['syncSecret']
        if not isinstance(secret,str) or len(secret)<32: raise ValueError('Clé de synchronisation trop courte.')
        local = online_origin(config['serverUrl'])
        context=ssl.create_default_context(cadata=config['certificate']); context.check_hostname=False
        local_headers={'Authorization':'CloudRelay '+config['relayToken']}
        manifest=json_request(local+'/api/cloud/relay/snapshot',{},local_headers,context)
        blocks=[]
        for index in range(manifest['chunks']):
            blocks.append(base64.b64decode(json_request(local+'/api/cloud/relay/snapshot/'+manifest['id']+'?chunk='+str(index),headers=local_headers,context=context)['data'],validate=True))
        content=b''.join(blocks)
        if len(content)!=manifest['bytes'] or hashlib.sha256(content).hexdigest()!=manifest['sha256']: raise ValueError('La copie reçue du serveur est incomplète.')
        encrypted=Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())).encrypt(content)
        cloud_headers={'Authorization':'CloudRelay '+secret}
        metadata={**manifest,'encryptedSha256':hashlib.sha256(encrypted).hexdigest(),'encryptedBytes':len(encrypted),'encryptedChunks':(len(encrypted)+CHUNK-1)//CHUNK}
        upload=json_request(website+'/api/online/cloud/begin',metadata,cloud_headers)
        for index in range(metadata['encryptedChunks']):
            block=encrypted[index*CHUNK:(index+1)*CHUNK]
            json_request(website+'/api/online/cloud/chunk',{'uploadId':upload['uploadId'],'index':index,'data':base64.b64encode(block).decode()},cloud_headers)
        result=json_request(website+'/api/online/cloud/finish',{'uploadId':upload['uploadId']},cloud_headers)
        atomic_write(status_path,json.dumps({'ok':True,'lastSuccess':datetime.now(timezone.utc).isoformat(),'capturedAt':manifest['capturedAt'],'sequence':manifest['sequence'],'published':result['published']}).encode())
        return result
    except Exception:
        old={}
        try: old=json.loads(status_path.read_text())
        except (OSError,ValueError): pass
        atomic_write(status_path,json.dumps({**old,'ok':False,'lastAttempt':datetime.now(timezone.utc).isoformat(),'error':'Synchronisation interrompue. Vérifiez Internet, le serveur local et la configuration Vercel.'}).encode())
        raise
