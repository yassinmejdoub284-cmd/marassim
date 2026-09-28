"""Isolated production-frontend verification, with a test-only PostgreSQL protocol fixture."""
import functools,os,sys,threading,time,json,uuid
from datetime import date,timedelta
from contextlib import contextmanager
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root/'desktop/server'),str(root/'desktop/tests')]
from app import Application,serve
import cloud_web
from test_cloud import MemoryPG,CloudTests,SECRET,SESSION
os.environ.update(MARASSIM_SYNC_SECRET=SECRET,MARASSIM_SESSION_SECRET=SESSION)
source=root/'desktop/test-results/ui-finance-fixture/marassim.db'
target=root/'desktop/test-results/ui-cloud-fixture'
application=Application(target,source if source.is_file() and not (target/'marassim.db').exists() else None)
with application.storage.transaction() as conn:
    exists=conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
if not exists:
    application.dispatch('POST','/api/setup',{'X-Bootstrap-Key':application.bootstrap.read_text()},{'username':'ui-test','password':'ui-test-password'})
with application.storage.transaction(True) as conn:
    if not conn.execute("SELECT 1 FROM recettes_omar_extra WHERE designation='Recette antérieure FICTIVE pour vérification'").fetchone():
        first=date.today().replace(day=1)
        conn.execute('INSERT INTO recettes_omar_extra(date_recette,designation,montant) VALUES (?,?,?)',((first-timedelta(days=1)).isoformat(),'Recette antérieure FICTIVE pour vérification',7508.078))
        conn.execute('INSERT INTO recettes_omar_extra(date_recette,designation,montant) VALUES (?,?,?)',(first.isoformat(),'Acompte client FICTIF · exemple',500))
        charge=conn.execute('INSERT INTO charges_omar(date_encaissement,designation,montant) VALUES (?,?,?)',(first.replace(day=5).isoformat(),'Dépense soirée CHICHKHANE 21H ET ALMES 21H · FICTIVE',555)).lastrowid
        details=[{'name':name,'period':period,'amount':amount} for name,period,amount in [('Employé exemple 1','21H',150),('Employé exemple 2','15H',100),('Accueil exemple 1','21H',80),('Accueil exemple 2','21H',70),('Lumière exemple','21H',35),('Hôtesse exemple','21H',30),('Hôtesse exemple 2','21H',30),('Aménagement exemple','21H',60)]]
        conn.execute('INSERT INTO omar_charge_details(charge_id,details) VALUES (?,?)',(charge,json.dumps(details)))
pg=MemoryPG();lock=threading.RLock()
tester=CloudTests();tester.app=application
def publish():
    with lock:tester.publish(pg,*tester.copy())
publish()
@contextmanager
def postgres():
    with lock:yield pg
cloud_web.postgres=postgres
class Static(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(root/'web-dist'),**kwargs)
    def do_POST(self):self.proxy()
    def do_PUT(self):self.proxy()
    def do_DELETE(self):self.proxy()
    def do_GET(self):
        if self.path.startswith('/api/online'):self.proxy()
        else:super().do_GET()
    def proxy(self):
        import http.client
        conn=http.client.HTTPConnection('127.0.0.1',18745,timeout=20)
        data=self.rfile.read(int(self.headers.get('Content-Length',0)))
        conn.request(self.command,self.path,body=data,headers=dict(self.headers))
        response=conn.getresponse();content=response.read();self.send_response(response.status)
        for key,value in response.getheaders():
            if key.lower() not in ('server','date','transfer-encoding'):self.send_header(key,value)
        self.end_headers();self.wfile.write(content);conn.close()
    def log_message(self,*_):pass
servers=[ThreadingHTTPServer(('127.0.0.1',18745),cloud_web.handler),ThreadingHTTPServer(('127.0.0.1',5174),Static),serve(application,'127.0.0.1',18746,insecure=True)]
for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
print('Cloud UI fixture ready on 5174; all data fictitious.',flush=True)
try:
    while True:time.sleep(5);publish()
finally:
    application.stop.set()
    for server in servers:server.shutdown();server.server_close()
