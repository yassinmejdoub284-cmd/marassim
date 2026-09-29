import base64
import hashlib
import io
import json
import os
import sys
import threading
import unittest
import urllib.request
import urllib.error
import uuid
import zipfile
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import test_server
import cloud_sync,cloud_web
from app import APIError

SECRET='test-only-sync-secret-0123456789abcdef'
SESSION='test-only-session-secret-0123456789abc'
def encrypt(data):return Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET.encode()).digest())).encrypt(data)

class MemoryPG:
    """SQL protocol fixture; production uses PostgreSQL, never this class."""
    def __init__(self):self.snapshot=None;self.uploads={};self.chunks={};self.attempts={};self.outbox={}
    def cursor(self):return Cursor(self)
    def commit(self):pass
    def rollback(self):pass
class Cursor:
    def __init__(self,pg):self.pg=pg;self.rows=[]
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def fetchone(self):return self.rows[0] if self.rows else None
    def fetchall(self):return self.rows
    def execute(self,sql,args=()):
        self.rows=[];p=self.pg
        if sql.startswith('SELECT server_id,sequence,captured_at'):
            if p.snapshot:self.rows=[p.snapshot]
        elif sql.startswith('SELECT server_id,sequence,encrypted'):
            if p.snapshot:self.rows=[(p.snapshot[0],p.snapshot[1],p.snapshot[4])]
        elif sql.startswith('INSERT INTO online_snapshot'):p.snapshot=tuple(args)
        elif sql.startswith('INSERT INTO online_uploads'):p.uploads.setdefault(args[0],json.loads(args[1]))
        elif sql.startswith('SELECT metadata'):self.rows=[(p.uploads[args[0]],)] if args[0] in p.uploads else []
        elif sql.startswith('INSERT INTO online_chunks'):p.chunks[(args[0],args[1])]=args[2]
        elif sql.startswith('SELECT n,data'):self.rows=sorted((n,data) for (key,n),data in p.chunks.items() if key==args[0])
        elif sql.startswith('DELETE FROM online_uploads WHERE id='):p.uploads.pop(args[0],None)
        elif sql.startswith('INSERT INTO online_login_limits'):
            key,bucket=args;old=p.attempts.get(key,(bucket,0));count=old[1]+1 if old[0]==bucket else 1;p.attempts[key]=(bucket,count);self.rows=[(count,)]
        elif sql.startswith('INSERT INTO online_push_outbox'):p.outbox.setdefault(args[0],args)
        elif sql.startswith("DELETE FROM online_uploads WHERE created_at") or sql.startswith('SELECT pg_advisory'):pass
        else:raise AssertionError(sql)

class CloudTests(unittest.TestCase):
    setUp=test_server.ServerTests.setUp
    tearDown=test_server.ServerTests.tearDown
    call=test_server.ServerTests.call
    create=test_server.ServerTests.create
    reservation=test_server.ServerTests.reservation
    def copy(self):
        meta=cloud_sync.snapshot(self.app)
        data=(self.app.root/'cloud-export'/(meta['id']+'.zip')).read_bytes()
        return meta,data,encrypt(data)
    def publish(self,pg,meta,data,encrypted,finish=True):
        manifest={**meta,'encryptedSha256':hashlib.sha256(encrypted).hexdigest(),'encryptedBytes':len(encrypted),'encryptedChunks':(len(encrypted)+cloud_sync.CHUNK-1)//cloud_sync.CHUNK}
        key=cloud_web.upload(pg,'/cloud/begin',manifest,SECRET)['uploadId']
        for i in range(manifest['encryptedChunks']):cloud_web.upload(pg,'/cloud/chunk',{'uploadId':key,'index':i,'data':base64.b64encode(encrypted[i*cloud_sync.CHUNK:(i+1)*cloud_sync.CHUNK]).decode()},SECRET)
        return cloud_web.upload(pg,'/cloud/finish',{'uploadId':key},SECRET) if finish else key
    def test_snapshot_consistent_sanitized_and_readonly_reports(self):
        self.create(self.reservation(acompte1=200))
        self.call('POST','/replicas',{'name':'Test client'})
        meta,data,encrypted=self.copy()
        conn,inside,templates=cloud_web.unpack(encrypted,SECRET)
        try:
            self.assertEqual(inside['sequence'],meta['sequence'])
            for table in ('web_sessions','idempotency','replicas','audit_log','cloud_agents'):self.assertEqual(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT nom_client FROM reservations').fetchone()[0],'Client test')
            user=cloud_web.public_user(conn,conn.execute('SELECT * FROM users').fetchone())
            report=cloud_web.business(conn,templates,user,'/forecast',{'start':'2026-12-31','end':'2027-01-30','opening':'0'})
            self.assertEqual(report['summary']['income'],800)
            with self.assertRaises(Exception):conn.execute("UPDATE reservations SET nom_client='Changed'")
            self.assertEqual(len(templates),2)
        finally:conn.close()
        with self.assertRaises(Exception):cloud_web.unpack(encrypted,'a-different-random-secret-000000000000')
    def test_notifications_are_transactional_and_idempotent(self):
        baseline=self.call('GET','/notifications');key=str(uuid.uuid4())
        self.create(key=key);self.create(key=key)
        events=self.call('GET',f"/notifications?after={baseline['latest']}")
        self.assertEqual(len(events['items']),1);self.assertTrue(events['serverId'])
        with self.assertRaises(APIError):self.create()
        self.assertEqual(len(self.call('GET','/notifications?after=0')['items']),1)
        row=self.call('GET','/reservations')[0]
        self.call('PUT',f"/reservations/{row['id']}",{'revision':row['revision'],'nom_client':'Client modifié'})
        self.assertEqual(len(self.call('GET','/notifications?after=0')['items']),1)
    def test_relay_token_cannot_write_business_or_read_without_permission(self):
        result=self.call('POST','/cloud/agents',{'name':'Internet relay'})
        headers={'Authorization':'CloudRelay '+result['relayToken']}
        manifest=self.app.dispatch('POST','/api/cloud/relay/snapshot',headers,{})
        block=self.app.dispatch('GET','/api/cloud/relay/snapshot/'+manifest['id']+'?chunk=0',headers,{})
        self.assertTrue(base64.b64decode(block['data']).startswith(b'PK'))
        with self.assertRaises(APIError):self.app.dispatch('POST','/api/reservations',headers,self.reservation())
        with self.assertRaises(APIError):self.app.dispatch('POST','/api/cloud/relay/snapshot',{'Authorization':'CloudRelay wrong'}, {})
    def test_publication_older_copy_does_not_replace_newer_and_outbox_once(self):
        pg=MemoryPG();first=self.copy();self.publish(pg,*first)
        self.assertEqual(len(pg.outbox),0)
        self.create(self.reservation(acompte1=100));second=self.copy();self.publish(pg,*second)
        self.assertEqual(len(pg.outbox),2)
        titles=[json.loads(args[2])['title'] for args in pg.outbox.values()]
        self.assertEqual(sorted(titles),['Nouvelle réservation Marassim','Paiement reçu Marassim'])
        replay=self.publish(pg,*first)
        self.assertFalse(replay['published']);self.assertEqual(pg.snapshot[1],second[0]['sequence'])
        self.assertEqual(len(pg.outbox),2)
    def test_incomplete_copy_leaves_previous_snapshot_unchanged(self):
        pg=MemoryPG();self.publish(pg,*self.copy());previous=pg.snapshot
        meta,data,encrypted=self.copy();key=self.publish(pg,meta,data,encrypted,False)
        pg.chunks.clear()
        with self.assertRaises(APIError):cloud_web.upload(pg,'/cloud/finish',{'uploadId':key},SECRET)
        self.assertEqual(pg.snapshot,previous)
    def test_sessions_signature_expiry_account_changes_and_origin(self):
        token=cloud_web.signed_session(1,'stamp',SESSION,now=1000)
        self.assertEqual(cloud_web.read_session(token,SESSION,now=1100)['id'],1)
        for invalid in (token+'x',token.replace('stamp','wrong'),'invalid'):
            if invalid==token:continue
            with self.assertRaises(APIError):cloud_web.read_session(invalid,SESSION,now=1100)
        with self.assertRaises(APIError):cloud_web.read_session(token,SESSION,now=4600)
        for url in ('http://host','https://user:pass@host','https://host/path','https://host?key=secret'):
            with self.assertRaises(ValueError):cloud_sync.online_origin(url)
    def test_http_cookie_login_readonly_permissions_and_exports(self):
        self.create();pg=MemoryPG();self.publish(pg,*self.copy())
        @contextmanager
        def store():yield pg
        with patch.object(cloud_web,'postgres',store),patch.dict(os.environ,{'MARASSIM_SYNC_SECRET':SECRET,'MARASSIM_SESSION_SECRET':SESSION}):
            server=ThreadingHTTPServer(('127.0.0.1',0),cloud_web.handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{server.server_port}/api/online'
            def fetch(path,body=None,cookie=None,method=None):
                req=urllib.request.Request(url+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**({'Cookie':cookie} if cookie else {})},method=method)
                return urllib.request.urlopen(req)
            try:
                with fetch('/login',{'username':'admin','password':'test-password-123'}) as response:
                    cookie=response.headers['Set-Cookie'];user=json.load(response)['user']
                    self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertNotIn('password',user)
                with fetch('/forecast',cookie=cookie) as response:self.assertTrue(json.load(response)['summary'])
                with fetch('/payment-alerts',cookie=cookie) as response:self.assertIsInstance(json.load(response),list)
                with fetch('/exports/contract/1',cookie=cookie) as response:self.assertTrue(json.load(response)['base64'])
                for resource in ('charges','charges-omar','recettes-omar','employees','pointage','employee-payments','rules','reception','users'):
                    with fetch('/'+resource,cookie=cookie) as response:
                        rows=json.load(response);self.assertIsInstance(rows,list)
                        if resource=='users':self.assertNotIn('password_hash',rows[0])
                    with fetch('/exports/table?resource='+resource,cookie=cookie) as response:self.assertTrue(json.load(response)['base64'])
                with fetch('/journal?caisse=omar&start=2026-06-01&end=2026-06-30',cookie=cookie) as response:self.assertEqual(json.load(response)['opening'],0)
                with fetch('/exports/journal?caisse=omar&start=2026-06-01&end=2026-06-30&format=pdf',cookie=cookie) as response:self.assertTrue(base64.b64decode(json.load(response)['base64']).startswith(b'%PDF'))
                with fetch('/status',cookie=cookie) as response:
                    status=json.load(response);self.assertTrue(status['available']);self.assertNotIn('last_sha256',json.dumps(status))
                for method,path in (('POST','/reservations'),('PUT','/reservations/1'),('DELETE','/reservations/1'),('POST','/reception'),('PUT','/users/1'),('POST','/charges-omar'),('POST','/pointage/batch')):
                    with self.assertRaises(urllib.error.HTTPError) as error:fetch(path,{},cookie,method)
                    self.assertEqual(error.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as error:fetch('/reports')
                self.assertEqual(error.exception.code,401)
                with fetch('/logout',{},cookie) as response:self.assertIn('Max-Age=0',response.headers['Set-Cookie'])
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
