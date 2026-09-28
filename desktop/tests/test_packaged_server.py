"""Run against the bundled executable: no Python installation used by the server."""
import json
import base64
import io
import os
import socket
import ssl
import subprocess
import tempfile
import time
import unittest
import urllib.request
import uuid
import zipfile
from pathlib import Path


EXE = Path(__file__).resolve().parents[1] / 'server-dist/MarassimServer/MarassimServer.exe'


@unittest.skipUnless(EXE.exists(), 'Compilez le serveur pour exécuter ce test du binaire Windows.')
class PackagedServerTests(unittest.TestCase):
    def test_standalone_https_engine_and_documents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with socket.socket() as port_finder:
                port_finder.bind(('127.0.0.1', 0)); port = port_finder.getsockname()[1]
            process = subprocess.Popen([str(EXE), '--host', '127.0.0.1', '--port', str(port), '--data-dir', str(root / 'data')], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                context = None
                for _ in range(60):
                    if (root / 'data/server.crt').exists():
                        context = ssl.create_default_context(cadata=(root / 'data/server.crt').read_text())
                        context.check_hostname = False
                        try:
                            with urllib.request.urlopen(f'https://127.0.0.1:{port}/api/health', context=context, timeout=1) as response:
                                self.assertTrue(json.loads(response.read())['ok'])
                            break
                        except OSError:
                            pass
                    if process.poll() is not None:
                        self.fail('Le binaire serveur a quitté avant de démarrer.')
                    time.sleep(.2)
                else: self.fail('Le binaire serveur n’a pas répondu.')
                def request(path, method='GET', body=None, token=None):
                    headers = {'Content-Type': 'application/json', 'Idempotency-Key': str(uuid.uuid4())}
                    if token: headers['Authorization'] = 'Bearer ' + token
                    if path == '/setup': headers['X-Bootstrap-Key'] = (root / 'data/bootstrap.key').read_text()
                    req = urllib.request.Request(f'https://127.0.0.1:{port}/api' + path, method=method, headers=headers, data=json.dumps(body).encode() if body is not None else None)
                    with urllib.request.urlopen(req, context=context, timeout=10) as response: return json.loads(response.read())
                request('/setup', 'POST', {'username': 'binary-test', 'password': 'binary-test-password'})
                token = request('/login', 'POST', {'username': 'binary-test', 'password': 'binary-test-password'})['token']
                row = request('/reservations', 'POST', {'salle': 'Almes', 'date_evenement': '2027-04-15', 'heure_debut': '15:00', 'heure_fin': '18:00', 'nom_client': 'Test binaire', 'forfait': 1000}, token)[0]
                notifications = request('/notifications?after=0',token=token)
                self.assertEqual(len(notifications['items']),1)
                self.assertTrue(notifications['serverId'])
                relay = request('/cloud/agents','POST',{'name':'Relais compilé'},token)
                relay_headers = {'Authorization':'CloudRelay '+relay['relayToken'],'Content-Type':'application/json'}
                req = urllib.request.Request(f'https://127.0.0.1:{port}/api/cloud/relay/snapshot',data=b'{}',headers=relay_headers)
                with urllib.request.urlopen(req,context=context) as response: manifest=json.load(response)
                req = urllib.request.Request(f"https://127.0.0.1:{port}/api/cloud/relay/snapshot/{manifest['id']}?chunk=0",headers=relay_headers)
                with urllib.request.urlopen(req,context=context) as response: block=json.load(response)
                with zipfile.ZipFile(io.BytesIO(base64.b64decode(block['data']))) as archive:
                    self.assertIn('snapshot.json',archive.namelist())
                forecast = request('/forecast?start=2027-03-01&end=2027-04-30&overdue=0',token=token)
                self.assertEqual(forecast['events'][0]['due'],'2027-03-31')
                self.assertEqual(forecast['summary']['income'],1000)
                request('/forecast-items','POST',{'due_date':'2027-04-01','designation':'Loyer test','direction':'out','amount':100},token)
                self.assertEqual(request('/forecast?start=2027-03-01&end=2027-04-30',token=token)['summary']['expense'],100)
                self.assertEqual(request('/reports?start=2027-04-01&end=2027-04-30',token=token)['summary']['booked'],1000)
                for path in ['/exports/reports?start=2027-04-01&end=2027-04-30','/exports/forecast?start=2027-03-01&end=2027-04-30']:
                    self.assertGreater(len(request(path,token=token)['base64']),1000)
                for path in [f"/exports/contract/{row['id']}", '/exports/calendar?year=2027&month=4', '/exports/journal?start=2027-04-01&end=2027-04-30&number=15']:
                    exported = request(path, token=token)
                    self.assertGreater(len(exported['base64']), 1000)
                    if '/contract/' in path:
                        with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported['base64']))) as document:
                            self.assertIn((EXE.parents[2] / 'assets/marassim-logo.png').read_bytes(), [document.read(n) for n in document.namelist() if n.startswith('word/media/')])
                exported_ar = request(f"/exports/arabic/{row['id']}", 'POST', {'arabic': {'ar_nom': 'عميل اختبار'}}, token)
                self.assertGreater(len(exported_ar['base64']), 1000)
                with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported_ar['base64']))) as document:
                    self.assertIn((EXE.parents[2] / 'assets/marassim-logo.png').read_bytes(), [document.read(n) for n in document.namelist() if n.startswith('word/media/')])
                self.assertTrue(request('/backups', 'POST', {}, token)['sha256'])
                request('/recettes-omar', 'POST', {'date_recette':'2026-05-31','designation':'Ancienne recette fictive','montant':7508.078}, token)
                request('/charges-omar', 'POST', {'date_encaissement':'2026-06-05','designation':'Charge fictive','montant':555}, token)
                query='caisse=omar&start=2026-06-01&end=2026-06-30'
                june=request('/journal?'+query,token=token)
                self.assertEqual(june['opening'],7508.078);self.assertEqual(june['closing'],6953.078)
                july=request('/journal?caisse=omar&start=2026-07-01&end=2026-07-31',token=token)
                self.assertEqual(july['opening'],june['closing'])
                pdf=request('/exports/journal?'+query+'&format=pdf',token=token)
                self.assertTrue(base64.b64decode(pdf['base64']).startswith(b'%PDF'))
                self.assertTrue(request('/exports/table?resource=charges-omar',token=token)['base64'])
            finally:
                process.terminate()
                process.wait(timeout=15)


if __name__ == '__main__': unittest.main()
