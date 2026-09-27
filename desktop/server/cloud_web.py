"""Read-only Vercel API. PostgreSQL stores encrypted snapshots and upload fragments."""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import sqlite3
import tempfile
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from cryptography.fernet import Fernet
from storage import active_connection, TransactionView
from app import Application, APIError, password_matches
import analytics

SCHEMA = '''
CREATE TABLE IF NOT EXISTS online_snapshot(id SMALLINT PRIMARY KEY CHECK(id=1), server_id TEXT NOT NULL, sequence BIGINT NOT NULL, captured_at TEXT NOT NULL, published_at TEXT NOT NULL, encrypted BYTEA NOT NULL);
CREATE TABLE IF NOT EXISTS online_uploads(id TEXT PRIMARY KEY, metadata JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS online_chunks(upload_id TEXT NOT NULL REFERENCES online_uploads(id) ON DELETE CASCADE, n INTEGER NOT NULL, data BYTEA NOT NULL, PRIMARY KEY(upload_id,n));
CREATE TABLE IF NOT EXISTS online_login_limits(key TEXT PRIMARY KEY, bucket BIGINT NOT NULL, attempts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS online_push(id TEXT PRIMARY KEY,user_id BIGINT NOT NULL,subscription JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS online_push_outbox(id TEXT PRIMARY KEY,user_id BIGINT NOT NULL,body JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now());
'''

def cipher(secret):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))

def unpack(encrypted,secret):
    content=cipher(secret).decrypt(bytes(encrypted))
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        files={entry.filename:entry for entry in archive.infolist()}
        allowed={'marassim.db','snapshot.json','template/Bon_Recu_Marassim_Template.docx','template/Contrat_Arabe_Template.docx'}
        if set(files)-allowed or not {'marassim.db','snapshot.json'} <= set(files): raise APIError('Archive de synchronisation invalide.')
        if sum(e.file_size for e in files.values())>256*1024*1024: raise APIError('Archive décompressée trop volumineuse.')
        data=archive.read('marassim.db'); meta=json.loads(archive.read('snapshot.json'))
        templates={Path(name).name:archive.read(name) for name in files if name.startswith('template/')}
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    try:
        conn.deserialize(data)
        if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise APIError('Copie SQLite corrompue.')
        conn.execute('PRAGMA query_only=ON')
        identity=dict(conn.execute('SELECT * FROM cloud_meta WHERE id=1').fetchone())
        if identity['server_id']!=meta['serverId'] or identity['sequence']!=meta['sequence']: raise APIError('Identité de la copie incohérente.')
        for table in ('web_sessions','idempotency','replicas','audit_log','cloud_agents'):
            if conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]: raise APIError('La copie contient des informations techniques interdites.')
        return conn,meta,templates
    except Exception:
        conn.close(); raise

@contextmanager
def postgres():
    import psycopg2
    url=os.environ.get('DATABASE_URL')
    if not url: raise APIError('La base en ligne n’est pas encore configurée.',503)
    conn=psycopg2.connect(url,connect_timeout=10,sslmode='require')
    try:
        with conn.cursor() as cursor:
            for statement in SCHEMA.split(';'):
                if statement.strip(): cursor.execute(statement)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()

def latest(pg):
    with pg.cursor() as cursor:
        cursor.execute('SELECT server_id,sequence,captured_at,published_at,encrypted FROM online_snapshot WHERE id=1')
        row=cursor.fetchone()
    if not row: raise APIError('Aucune synchronisation reçue. Activez le relais depuis un poste du réseau local.',503)
    return dict(zip(['serverId','sequence','capturedAt','publishedAt','encrypted'],row))

def auth_stamp(row,modules):
    return hashlib.sha256(json.dumps([row['password_hash'],row['revision'],row['role'],row['actif'],sorted(modules)]).encode()).hexdigest()

def signed_session(user,stamp,secret,now=None):
    body=base64.urlsafe_b64encode(json.dumps({'id':user,'stamp':stamp,'expires':int(now or time.time())+3600},separators=(',',':')).encode()).decode().rstrip('=')
    signature=hmac.new(secret.encode(),body.encode(),hashlib.sha256).hexdigest()
    return body+'.'+signature

def read_session(token,secret,now=None):
    try:
        body,signature=token.split('.')
        if not hmac.compare_digest(signature,hmac.new(secret.encode(),body.encode(),hashlib.sha256).hexdigest()): raise ValueError()
        result=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        if result['expires'] <= (now or time.time()): raise ValueError()
        return result
    except (ValueError,KeyError,TypeError): raise APIError('Session expirée. Reconnectez-vous.',401)

def check_upload(metadata):
    expected={'id','serverId','sequence','capturedAt','sha256','bytes','chunks','encryptedSha256','encryptedBytes','encryptedChunks'}
    if set(metadata)!=expected: raise APIError('Métadonnées invalides.')
    uuid.UUID(metadata['serverId'])
    datetime.fromisoformat(metadata['capturedAt'])
    if not isinstance(metadata['sequence'],int) or metadata['sequence']<1: raise APIError('Version invalide.')
    if not isinstance(metadata['encryptedChunks'],int) or not 1<=metadata['encryptedChunks']<=180: raise APIError('Nombre de fragments invalide.')
    if not 1<=metadata['encryptedBytes']<=128*1024*1024: raise APIError('Copie trop volumineuse.')
    if not all(re.fullmatch('[0-9a-f]{64}',metadata[k]) for k in ('sha256','encryptedSha256')): raise APIError('Empreinte invalide.')

def upload(pg,path,payload,secret):
    from cloud_sync import CHUNK
    with pg.cursor() as cursor:
        cursor.execute("DELETE FROM online_uploads WHERE created_at<now()-interval '1 day'")
        if path=='/cloud/begin':
            check_upload(payload)
            identifier=payload['encryptedSha256']
            cursor.execute('INSERT INTO online_uploads(id,metadata) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO NOTHING',(identifier,json.dumps(payload)))
            return {'uploadId':identifier}
        identifier=payload.get('uploadId','')
        cursor.execute('SELECT metadata FROM online_uploads WHERE id=%s',(identifier,)); row=cursor.fetchone()
        if not row: raise APIError('Synchronisation expirée. Réessayez.',404)
        meta=row[0]
        if path=='/cloud/chunk':
            index=payload['index']; data=base64.b64decode(payload['data'],validate=True)
            if not isinstance(index,int) or not 0<=index<meta['encryptedChunks'] or not 0<len(data)<=CHUNK: raise APIError('Fragment invalide.')
            expected=min(CHUNK,meta['encryptedBytes']-index*CHUNK)
            if len(data)!=expected: raise APIError('Taille de fragment invalide.')
            cursor.execute('INSERT INTO online_chunks(upload_id,n,data) VALUES (%s,%s,%s) ON CONFLICT(upload_id,n) DO UPDATE SET data=excluded.data',(identifier,index,data))
            return {'ok':True}
        if path!='/cloud/finish': raise APIError('Page introuvable.',404)
        cursor.execute('SELECT n,data FROM online_chunks WHERE upload_id=%s ORDER BY n',(identifier,)); chunks=cursor.fetchall()
        if [r[0] for r in chunks]!=list(range(meta['encryptedChunks'])): raise APIError('Copie incomplète.',409)
        encrypted=b''.join(bytes(r[1]) for r in chunks)
        if len(encrypted)!=meta['encryptedBytes'] or hashlib.sha256(encrypted).hexdigest()!=meta['encryptedSha256']: raise APIError('Empreinte de copie invalide.')
        db,inside,_=unpack(encrypted,secret)
        try:
            if any(inside[k]!=meta[k] for k in ('serverId','sequence','capturedAt')): raise APIError('Version de la copie incohérente.')
            cursor.execute('SELECT pg_advisory_xact_lock(173831)')
            cursor.execute('SELECT server_id,sequence,encrypted FROM online_snapshot WHERE id=1 FOR UPDATE'); old=cursor.fetchone()
            if old and old[0]!=meta['serverId']: raise APIError('Ce projet est associé à un autre serveur Marassim.',409)
            if old and old[1]>=meta['sequence']: return {'published':False,'sequence':old[1]}
            # Only a completely verified snapshot can replace the currently visible one.
            published=datetime.now(timezone.utc).isoformat()
            cursor.execute('INSERT INTO online_snapshot(id,server_id,sequence,captured_at,published_at,encrypted) VALUES (1,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET sequence=excluded.sequence,captured_at=excluded.captured_at,published_at=excluded.published_at,encrypted=excluded.encrypted',(meta['serverId'],meta['sequence'],meta['capturedAt'],published,encrypted))
            from notifications_web import queue_push
            queue_push(cursor,db,old,secret)
            cursor.execute('DELETE FROM online_uploads WHERE id=%s',(identifier,))
            return {'published':True,'sequence':meta['sequence']}
        finally: db.close()

def business(conn,templates,user,path,query):
    import db,database,access_control,rules
    original=active_connection.set(TransactionView(conn))
    db.connect=lambda: active_connection.get()
    try:
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,content in templates.items(): (root/name).write_bytes(content)
            application=Application.__new__(Application)
            application.database=database; application.access=access_control; application.rules=rules
            application.all_modules=access_control.ALL_MODULES+analytics.REPORT_MODULES; application.templates=root
            permitted=('/reports','/forecast','/reservations','/journal','/employees','/charges','/charges-omar','/recettes-omar','/employee-payments','/pointage','/rules','/reception','/exports','/notifications')
            if not any(path==p or path.startswith(p+'/') for p in permitted): raise APIError('Ce module n’est pas disponible en ligne.',403)
            return application.business_route(conn,user,'GET',path,query,{})
    finally: active_connection.reset(original)

def public_user(conn,row):
    import access_control
    user={k:row[k] for k in ('id','username','nom','prenom','role','actif','revision')}
    user['modules']=access_control.ALL_MODULES+analytics.REPORT_MODULES if row['role']=='admin' else [r[0] for r in conn.execute('SELECT module_name FROM module_access WHERE user_id=? AND can_access=1',(row['id'],))]
    return user

class handler(BaseHTTPRequestHandler):
    def do_GET(self): self.handle_api()
    def do_POST(self): self.handle_api()
    def do_PUT(self): self.handle_api()
    def do_DELETE(self): self.handle_api()
    def log_message(self,*_): pass

    def handle_api(self):
        from http.cookies import SimpleCookie
        parsed=urlparse(self.path); query={k:v[-1] for k,v in parse_qs(parsed.query).items()}
        route='/'+query.pop('route',parsed.path.removeprefix('/api/online').strip('/'))
        status=200; cookie=None
        try:
            length=int(self.headers.get('Content-Length',0))
            if length<0 or length>1_200_000: raise APIError('Requête trop volumineuse.',413)
            payload=json.loads(self.rfile.read(length)) if length else {}
            if not isinstance(payload,dict): raise APIError('Formulaire invalide.')
            sync_secret=os.environ.get('MARASSIM_SYNC_SECRET',''); session_secret=os.environ.get('MARASSIM_SESSION_SECRET','')
            if min(len(sync_secret),len(session_secret))<32: raise APIError('Le site n’est pas encore configuré.',503)
            if route.startswith('/cloud/'):
                if self.command!='POST' or not hmac.compare_digest(self.headers.get('Authorization',''),'CloudRelay '+sync_secret): raise APIError('Relais non autorisé.',403)
                with postgres() as pg: result=upload(pg,route,payload,sync_secret)
                if route=='/cloud/finish':
                    from notifications_web import deliver_push
                    deliver_push()
            else:
                if self.command!='GET' and route not in ('/login','/logout','/push/subscribe'): raise APIError('L’application en ligne est en consultation uniquement.',403)
                origin=self.headers.get('Origin')
                if self.command!='GET' and origin and urlparse(origin).netloc!=self.headers.get('Host'): raise APIError('Origine de requête invalide.',403)
                with postgres() as pg:
                    snapshot=latest(pg); conn,meta,templates=unpack(snapshot['encrypted'],sync_secret)
                    try:
                        if route=='/login' and self.command=='POST':
                            username=payload.get('username','')
                            if not isinstance(username,str) or len(username)>80: raise APIError('Identifiant invalide.')
                            bucket=int(time.time()//300); key=hashlib.sha256(username.lower().encode()).hexdigest()
                            with pg.cursor() as cursor:
                                cursor.execute('INSERT INTO online_login_limits(key,bucket,attempts) VALUES (%s,%s,1) ON CONFLICT(key) DO UPDATE SET bucket=excluded.bucket,attempts=CASE WHEN online_login_limits.bucket=excluded.bucket THEN online_login_limits.attempts+1 ELSE 1 END RETURNING attempts',(key,bucket))
                                attempts=cursor.fetchone()[0]
                            pg.commit()  # Rejected sign-ins must still consume a rate-limit attempt.
                            if attempts>15: raise APIError('Trop de tentatives. Réessayez dans 5 minutes.',429)
                            row=conn.execute('SELECT * FROM users WHERE username=? AND actif=1',(username,)).fetchone()
                            if not row or not password_matches(payload.get('password'),row['password_hash']): raise APIError('Identifiant ou mot de passe incorrect.',401)
                            user=public_user(conn,row)
                            token=signed_session(user['id'],auth_stamp(row,user['modules']),session_secret)
                            cookie='marassim_session='+token+'; Path=/api/online; HttpOnly; Secure; SameSite=Strict; Max-Age=3600'
                            result={'user':user}
                        elif route=='/logout' and self.command=='POST':
                            cookie='marassim_session=; Path=/api/online; HttpOnly; Secure; SameSite=Strict; Max-Age=0'; result={'ok':True}
                        else:
                            cookies=SimpleCookie(); cookies.load(self.headers.get('Cookie',''))
                            token=cookies['marassim_session'].value if 'marassim_session' in cookies else ''
                            session=read_session(token,session_secret)
                            row=conn.execute('SELECT * FROM users WHERE id=? AND actif=1',(session['id'],)).fetchone()
                            if not row: raise APIError('Compte désactivé. Reconnectez-vous.',401)
                            user=public_user(conn,row)
                            if not hmac.compare_digest(session['stamp'],auth_stamp(row,user['modules'])): raise APIError('Votre compte a changé. Reconnectez-vous.',401)
                            if route=='/me': result=user
                            elif route=='/health': result={'ok':True,'readOnly':True,**{k:snapshot[k] for k in ('sequence','capturedAt','publishedAt')}}
                            elif route.startswith('/push/'):
                                from notifications_web import push_route
                                result=push_route(pg,user,self.command,route,payload)
                            else: result=business(conn,templates,user,route,query)
                    finally: conn.close()
        except APIError as error: status,result=error.status,{'error':str(error)}
        except (ValueError,KeyError,TypeError): status,result=400,{'error':'Formulaire ou copie invalide.'}
        except Exception: status,result=503,{'error':'Le service en ligne est temporairement indisponible. Les données locales restent utilisables.'}
        content=json.dumps(result,ensure_ascii=False).encode()
        if len(content)>4_000_000: status,content=413,json.dumps({'error':'Export trop volumineux. Réduisez la période ou utilisez le poste local.'}).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(content)))
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(content)
