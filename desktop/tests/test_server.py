import base64
import hashlib
import io
import json
import sqlite3
import ssl
import sys
import tempfile
import threading
import unittest
import urllib.request
import uuid
import zipfile
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / 'server'
sys.path.insert(0, str(SERVER))
from app import Application, APIError, serve, token_hash
from backups import restore_backup, sync_replica, digest


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = Application(self.root / 'data')
        self.app.dispatch('POST', '/api/setup', {'X-Bootstrap-Key': self.app.bootstrap.read_text()}, {'username': 'admin', 'password': 'test-password-123'})
        self.token = self.app.dispatch('POST', '/api/login', {}, {'username': 'admin', 'password': 'test-password-123'})['token']

    def tearDown(self):
        self.app.stop.set()
        self.temp.cleanup()

    def call(self, method, path, body=None, key=None, token=None):
        return self.app.dispatch(method, '/api' + path, {'Authorization': 'Bearer ' + (token or self.token), 'Idempotency-Key': key or str(uuid.uuid4())}, body or {})

    def reservation(self, **kwargs):
        return dict(salle='Almes', date_evenement='2027-01-15', heure_debut='21:00', heure_fin='01:00', nom_client='Client test', forfait=1000, **kwargs)

    def create(self, data=None, key=None):
        return self.call('POST', '/reservations', data or self.reservation(), key)[0]

    def test_four_users_same_slot_only_one_commits(self):
        barrier = threading.Barrier(4)
        def write(n):
            barrier.wait()
            try:
                return self.create()
            except APIError as error:
                return error.status
        with ThreadPoolExecutor(4) as pool:
            result = list(pool.map(write, range(4)))
        self.assertEqual(sum(isinstance(r, dict) for r in result), 1)
        self.assertEqual(result.count(409), 3)
        self.assertEqual(len(self.call('GET', '/reservations')), 1)

    def test_four_simultaneous_distinct_dates_unique_numbers(self):
        def write(n):
            data = self.reservation(); data['date_evenement'] = f'2027-02-{n + 1:02d}'
            return self.create(data)
        with ThreadPoolExecutor(4) as pool:
            rows = list(pool.map(write, range(4)))
        self.assertEqual(len({r['id'] for r in rows}), 4)
        self.assertEqual(len({r['num_bon'] for r in rows}), 4)

    def test_idempotency_after_lost_response(self):
        key = str(uuid.uuid4())
        first = self.create(key=key)
        again = self.create(key=key)
        self.assertEqual(first, again)
        self.assertEqual(len(self.call('GET', '/reservations')), 1)
        data = self.reservation(); data['nom_client'] = 'Changed request'
        with self.assertRaises(APIError) as error:
            self.create(data, key)
        self.assertEqual(error.exception.status, 409)

    def test_stale_edit_cannot_overwrite_another_pc(self):
        row = self.create()
        updated = self.call('PUT', f"/reservations/{row['id']}", {'nom_client': 'Premier poste', 'revision': row['revision']})
        self.assertEqual(updated['revision'], row['revision'] + 1)
        with self.assertRaises(APIError) as error:
            self.call('PUT', f"/reservations/{row['id']}", {'nom_client': 'Autre poste', 'revision': row['revision']})
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.call('GET', f"/reservations/{row['id']}")['nom_client'], 'Premier poste')

    def test_simultaneous_payments_and_retry(self):
        row = self.create()
        barrier = threading.Barrier(4)
        keys = [str(uuid.uuid4()) for _ in range(4)]
        payload = {'montant': 400, 'methode': 'Espèce', 'num_caisse': '123', 'revision': row['revision']}
        def pay(n):
            barrier.wait()
            try: return (n, self.call('POST', f"/reservations/{row['id']}/payments", payload, keys[n]))
            except APIError as error: return (n, error.status)
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(pay, range(4)))
        winners = [(n, r) for n, r in results if isinstance(r, dict)]
        self.assertEqual(len(winners), 1)
        n, accepted = winners[0]
        self.assertEqual(self.call('POST', f"/reservations/{row['id']}/payments", payload, keys[n]), accepted)
        actual = self.call('GET', f"/reservations/{row['id']}")
        self.assertEqual(actual['acompte1'], 400)
        self.assertIsNone(actual['acompte2'])
        with self.assertRaises(ValueError):
            self.call('POST', f"/reservations/{row['id']}/payments", dict(payload, montant=700, revision=actual['revision']))
        self.assertEqual(self.call('GET', f"/reservations/{row['id']}")['revision'], actual['revision'])

    def test_multi_hall_transaction_rolls_back(self):
        data = self.reservation(); data['salle'] = 'Chichkhane'; self.create(data)
        data = self.reservation(); data['salles'] = ['Almes', 'Chichkhane']
        with self.assertRaises(APIError): self.call('POST', '/reservations', data)
        self.assertEqual(len(self.call('GET', '/reservations')), 1)

    def test_edit_checks_original_booking_rules(self):
        row = self.create()
        updated=self.call('PUT', f"/reservations/{row['id']}", {'heure_debut': '17:00', 'heure_fin': '19:00', 'revision': row['revision']})
        self.assertEqual(updated['heure_debut'],'17:00')
        with self.assertRaises(APIError):
            self.call('PUT', f"/reservations/{row['id']}", {'heure_debut': '99:00', 'revision': updated['revision']})

    def test_rule_configuration_is_authoritative(self):
        self.call('POST', '/rules', {'nom': 'Créneau spécifique', 'salle': 'Almes', 'creneaux': '17:00-20:00', 'jours': '0,1,2,3,4,5,6', 'pause_min_heures': 2, 'actif': 1})
        data = self.reservation(); data.update(heure_debut='17:00', heure_fin='20:00')
        self.assertEqual(self.create(data)['heure_debut'], '17:00')
        with self.assertRaises(APIError): self.create()

    def test_availability_free_hours_same_room_pause_and_rule_two_hours(self):
        day='2027-02-11'
        request=self.reservation();request.update(date_evenement=day,heure_debut='10:00',heure_fin='12:00')
        self.assertTrue(self.call('GET',f'/availability?date={day}&salles=Almes&start=10:00&end=12:00')['available'])
        self.create(request)
        for start,end in (('10:00','12:00'),('11:00','13:00'),('14:00','16:00')):
            self.assertFalse(self.call('GET',f'/availability?date={day}&salles=Almes&start={start}&end={end}')['available'])
            with self.assertRaises(APIError):self.create(dict(request,heure_debut=start,heure_fin=end))
        self.assertTrue(self.call('GET',f'/availability?date={day}&salles=Chichkhane&start=10:00&end=12:00')['available'])
        self.call('POST','/rules',{'nom':'Deux heures','salle':'Almes','pause_min_heures':2,'actif':1})
        self.assertTrue(self.call('GET',f'/availability?date={day}&salles=Almes&start=14:00&end=16:00')['available'])
        self.create(dict(request,heure_debut='14:00',heure_fin='16:00'))

    def test_free_violin_entitlement_and_weekend(self):
        def booking(day,salle,start,end):
            data=self.reservation();data.update(date_evenement=day,salle=salle,heure_debut=start,heure_fin=end,with_violoniste=1,violoniste_heure_debut='16:00',violoniste_heure_fin='17:00')
            return data
        with self.assertRaises(APIError):self.create(booking('2027-01-16','Almes','19:00','22:00'))
        with self.assertRaises(APIError):self.create(booking('2027-01-17','Chichkhane','19:00','22:00'))
        with self.assertRaises(APIError):self.create(booking('2027-01-18','Chichkhane','15:00','18:00'))
        self.assertEqual(self.create(booking('2027-01-18','Almes','15:00','18:00'))['salle'],'Almes')
        with self.assertRaises(APIError):self.create(dict(booking('2027-01-19','Almes','12:00','15:00'),violoniste_heure_fin='18:00'))
        with self.assertRaises(APIError):self.create(dict(booking('2027-01-19','Almes','12:00','15:00'),violoniste_date='2027-01-23'))
        self.call('POST','/rules',{'nom':'Pause seule','salle':'Chichkhane','pause_min_heures':2,'actif':1})
        self.assertEqual(self.create(booking('2027-01-19','Chichkhane','12:00','15:00'))['salle'],'Chichkhane')

    def test_availability_rejects_malformed_date(self):
        with self.assertRaises(APIError):
            self.call('GET','/availability?date=2027-02-30&salles=Almes&start=10:00&end=12:00')

    def test_next_day_reservation_respects_pause_after_midnight(self):
        data=self.reservation();data.update(date_evenement='2027-02-11',heure_debut='21:00',heure_fin='01:00')
        self.create(data)
        after=dict(data,date_evenement='2027-02-12',heure_debut='03:00',heure_fin='05:00')
        self.assertFalse(self.call('GET','/availability?date=2027-02-12&salles=Almes&start=03:00&end=05:00')['available'])
        with self.assertRaises(APIError):self.create(after)
        after.update(heure_debut='04:00',heure_fin='06:00')
        self.assertTrue(self.call('GET','/availability?date=2027-02-12&salles=Almes&start=04:00&end=06:00')['available'])
        self.create(after)

    def test_multihall_contract_has_only_one_free_violin_hour(self):
        data=self.reservation();data.update(date_evenement='2027-01-22',heure_debut='15:00',heure_fin='18:00',
                                            salles=['Chichkhane','Almes'],with_violoniste=1,
                                            violoniste_heure_debut='16:00',violoniste_heure_fin='17:00')
        availability=self.call('GET','/availability?date=2027-01-22&salles=Chichkhane,Almes&start=15:00&end=18:00&violoniste=1&violoniste_start=16:00&violoniste_end=17:00')
        self.assertTrue(availability['available'])
        created=self.call('POST','/reservations',data)
        self.assertEqual(sum(int(r['with_violoniste']) for r in created),1)
        self.assertEqual(next(r['salle'] for r in created if r['with_violoniste']),'Almes')

    def test_booking_payment_notifications_and_overdue_balance(self):
        day=(date.today()+timedelta(days=30)).isoformat()
        late=(date.today()-timedelta(days=1)).isoformat()
        baseline=self.call('GET','/notifications')['latest']
        booking=self.create(dict(self.reservation(),date_evenement=day,date_reste=late,acompte1=100,date_acompte1=date.today().isoformat()))
        events=self.call('GET',f'/notifications?after={baseline}')['items']
        self.assertEqual(sorted(r['kind'] for r in events),['payment','reservation'])
        self.assertEqual(next(r['amount'] for r in events if r['kind']=='payment'),100)
        alerts=self.call('GET','/payment-alerts')
        self.assertEqual(len(alerts),1);self.assertEqual(alerts[0]['amount'],900)
        self.call('POST',f"/reservations/{booking['id']}/payments",{'montant':200,'methode':'Espèce','revision':booking['revision']})
        events=self.call('GET',f'/notifications?after={baseline}')['items']
        self.assertEqual(len(events),3);self.assertEqual(events[-1]['kind'],'payment');self.assertEqual(events[-1]['amount'],200)
        self.assertEqual(self.call('GET','/payment-alerts')[0]['amount'],700)

    def test_permissions_enforced_on_server_and_sessions_revoked(self):
        new = self.call('POST', '/users', {'username': 'limited', 'password': 'test-password-123', 'nom': 'Employé', 'role': 'employe', 'modules': ['Calendrier']})
        login = self.app.dispatch('POST', '/api/login', {}, {'username': 'limited', 'password': 'test-password-123'})
        self.assertEqual(self.call('GET', '/reservations', token=login['token']), [])
        with self.assertRaises(APIError) as error: self.call('GET', '/users', token=login['token'])
        self.assertEqual(error.exception.status, 403)
        with self.assertRaises(APIError): self.call('POST', '/reservations', self.reservation(), token=login['token'])
        account = next(r for r in self.call('GET', '/users') if r['id'] == new['id'])
        self.call('PUT', f"/users/{new['id']}", {**account, 'actif': 0})
        with self.assertRaises(APIError) as error: self.call('GET', '/reservations', token=login['token'])
        self.assertEqual(error.exception.status, 401)

    def test_collective_pointage_preserves_omar_charge(self):
        emp = self.call('POST', '/employees', {'nom': 'Ouvrier', 'prenom': 'Nuit', 'role': 'Service', 'type_ouvrier': 'nuit', 'salaire_midi': 20, 'salaire_soiree': 30, 'prix_heure_supp': 5})
        day = self.call('POST', '/employees', {'nom': 'Ouvrier', 'prenom': 'Jour', 'role': 'Service', 'type_ouvrier': 'jour', 'salaire_journalier': 50})
        entries = [dict(employee_id=emp['id'], date_pointage='2027-01-15', periode=p, heures_supplementaires=2) for p in ('midi', 'soiree')]
        entries.append(dict(employee_id=day['id'], date_pointage='2027-01-15', periode='journee_complete', heures_supplementaires=0))
        key = str(uuid.uuid4())
        result = self.call('POST', '/pointage/batch', {'entries': entries, 'notes': 'Session'}, key)
        self.assertEqual(result['omarCharge'], 70)
        self.assertEqual(self.call('GET', '/charges-omar')[0]['montant'], 70)
        self.assertEqual(len(self.call('GET', '/pointage')), 3)
        self.assertEqual(self.call('POST', '/pointage/batch', {'entries': entries, 'notes': 'Session'}, key), result)
        with self.assertRaises(APIError): self.call('POST', '/pointage/batch', {'entries': entries})
        self.assertEqual(len(self.call('GET', '/charges-omar')), 1)
        self.assertEqual(self.call('GET', f"/employees/{emp['id']}/fiche")['total_du'], 70)

    def test_encrypted_backup_four_https_copies_and_restore(self):
        row = self.create()
        snapshot = self.app.backups.create()
        self.assertNotIn(b'SQLite format 3', (self.app.backups.root / snapshot['name']).read_bytes())
        server = serve(self.app, '127.0.0.1', 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            configs = []
            for n in range(4):
                replica = self.call('POST', '/replicas', {'name': f'PC-{n + 1}'})
                directory = self.root / f'pc-{n + 1}'
                configuration = self.root / f'replica-{n + 1}.json'
                configuration.write_text(json.dumps({'serverUrl': f'https://127.0.0.1:{server.server_port}', 'certificate': replica['certificate'], 'replicaToken': replica['replicaToken'], 'backupDirectory': str(directory)}))
                configs.append(configuration)
            with ThreadPoolExecutor(4) as pool: list(pool.map(sync_replica, configs))
            self.assertEqual(self.call('GET', '/status')['verifiedCopies'], 5)
            for n in range(4): self.assertEqual(digest(self.root / f'pc-{n + 1}' / snapshot['name']), snapshot['sha256'])
            # An existing corrupted local copy is repaired during the next pass.
            (self.root / 'pc-1' / snapshot['name']).write_bytes(b'corrupt')
            sync_replica(configs[0])
            self.assertEqual(digest(self.root / 'pc-1' / snapshot['name']), snapshot['sha256'])
            restore_backup(self.root / 'pc-1' / snapshot['name'], self.app.backups.key_path, self.root / 'restored')
            conn = sqlite3.connect(self.root / 'restored/marassim.db')
            self.assertEqual(conn.execute('SELECT nom_client FROM reservations WHERE id=?', (row['id'],)).fetchone()[0], row['nom_client'])
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM web_sessions').fetchone()[0], 0)
            conn.close()
            with self.assertRaises(ValueError): restore_backup(self.root / 'pc-1' / snapshot['name'], self.app.backups.key_path, self.root / 'restored')
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_offline_pc_catches_up_and_bad_ack_is_refused(self):
        first = self.app.backups.create()
        replica = self.call('POST', '/replicas', {'name': 'Absent'})
        second = self.app.backups.create()
        with self.assertRaises(APIError):
            self.app.dispatch('POST', '/api/replica/ack', {'Authorization': 'Replica ' + replica['replicaToken']}, {'name': second['name'], 'sha256': 'invalid'})
        self.assertEqual(self.call('GET', '/status')['verifiedCopies'], 1)
        self.assertEqual(len(self.app.backups.manifests()), 2)

    def test_import_preserves_original_bytes(self):
        row = self.create()
        original = self.root / 'legacy.db'
        source = self.app.storage.connect(); target = sqlite3.connect(original)
        source.backup(target); target.close(); source.close()
        before = digest(original)
        imported = Application(self.root / 'imported', original)
        self.assertEqual(digest(original), before)
        with imported.storage.transaction() as conn:
            self.assertEqual(conn.execute('SELECT nom_client FROM reservations WHERE id=?', (row['id'],)).fetchone()[0], row['nom_client'])

    def test_import_real_legacy_schema_without_modifying_source(self):
        original = SERVER.parents[1] / 'marassim.db'
        if not original.exists(): self.skipTest('Base d’origine absente.')
        before = digest(original)
        source = sqlite3.connect(original.as_uri() + '?mode=ro', uri=True)
        expected = {row[0]: source.execute(f'SELECT COUNT(*) FROM {row[0]}').fetchone()[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        source.close()
        imported = Application(self.root / 'real-import', original)
        with imported.storage.transaction() as conn:
            for table, count in expected.items():
                self.assertEqual(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], count)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(digest(original), before)

    def test_payroll_cannot_double_pay_from_stale_employee_balance(self):
        emp = self.call('POST', '/employees', {'nom': 'Test', 'prenom': 'Paie', 'role': 'Service', 'type_ouvrier': 'jour'})
        payload = {'employee_id': emp['id'], 'employeeRevision': emp['revision'], 'date_paiement': '2027-01-15', 'periode_debut': '2027-01-01', 'periode_fin': '2027-01-15', 'montant_base': 100, 'montant_heures_supp': 0, 'montant_total': 50}
        self.call('POST', '/employee-payments', payload)
        with self.assertRaises(APIError) as error: self.call('POST', '/employee-payments', payload)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(len(self.call('GET', '/employee-payments')), 1)

    def test_draft_documents_do_not_create_reservations(self):
        for kind in ('draft-contract', 'draft-arabic'):
            result = self.call('POST', '/exports/' + kind, {'reservation': self.reservation(), 'arabic': {'ar_nom': 'عميل'}})
            self.assertGreater(len(result['base64']), 1000)
        self.assertEqual(self.call('GET', '/reservations'), [])

    def test_empty_rebuilt_server_cannot_delete_client_backups(self):
        replica = self.call('POST', '/replicas', {'name': 'PC-secours'})
        local = self.root / 'surviving-copies'; local.mkdir()
        surviving = local / 'marassim_previous.mrb'; surviving.write_bytes(b'surviving archive')
        surviving.with_name(surviving.name + '.json').write_text(json.dumps({'name': surviving.name, 'created_at': '2026-01-01T19:00:00', 'sha256': digest(surviving), 'key_id': 'previous-server'}))
        server = serve(self.app, '127.0.0.1', 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        config = self.root / 'replica.json'
        config.write_text(json.dumps({'serverUrl': f'https://127.0.0.1:{server.server_port}', 'certificate': replica['certificate'], 'replicaToken': replica['replicaToken'], 'backupDirectory': str(local)}))
        try:
            self.assertEqual(sync_replica(config), 0)
            self.assertTrue(surviving.exists())
            self.app.backups.create()
            sync_replica(config)
            self.assertTrue(surviving.exists())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_export_uses_same_word_and_excel_templates(self):
        import contract_generator, excel_export, legacy_exports
        row = self.create()
        exported = self.call('GET', f"/exports/contract/{row['id']}")
        old_output = self.root / 'old.docx'
        contract_generator.generate_contract(row, old_output)
        def xml_parts(data):
            with zipfile.ZipFile(io.BytesIO(data)) as z: return {name: z.read(name) for name in z.namelist() if name.startswith('word/')}
        self.assertEqual(xml_parts(base64.b64decode(exported['base64'])), xml_parts(old_output.read_bytes()))
        ar = {'ar_nom': 'اسم العميل', 'num_contrat': '1'}
        exported_ar = self.call('POST', f"/exports/arabic/{row['id']}", {'arabic': ar})
        contract_generator.generate_arabic_contract(row, ar, old_output)
        self.assertEqual(xml_parts(base64.b64decode(exported_ar['base64'])), xml_parts(old_output.read_bytes()))
        excel = self.call('GET', '/exports/calendar?year=2027&month=1')
        old_excel = self.root / 'old.xlsx'
        with self.app.storage.transaction(): excel_export.export_month_calendar(2027, 1, old_excel)
        def sheet_parts(data):
            with zipfile.ZipFile(io.BytesIO(data)) as z: return {name: z.read(name) for name in z.namelist() if name.startswith('xl/')}
        self.assertEqual(sheet_parts(base64.b64decode(excel['base64'])), sheet_parts(old_excel.read_bytes()))
        # Exact journal workbook code is copied from the original GUI, not redesigned.
        import ast, textwrap
        legacy = SERVER.parents[1]
        source = (legacy / 'gui.py').read_text('utf-8')
        tree = ast.parse(source)
        for cls_name, writer in [('JournalCaisseTab', legacy_exports._write_tawfik), ('JournalCaisseOmarTab', legacy_exports._write_omar)]:
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
            method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_export_excel')
            code = ast.get_source_segment(source, method)
            start, end = code.index('        wb = openpyxl.Workbook()'), code.index('        wb.save(path)') + len('        wb.save(path)')
            original_body = ast.parse(textwrap.dedent(code[start:end]))
            import inspect
            extracted_body = ast.parse(textwrap.dedent(inspect.getsource(writer))).body[0].body
            self.assertEqual(ast.dump(original_body, include_attributes=False), ast.dump(ast.Module(body=extracted_body, type_ignores=[]), include_attributes=False))


if __name__ == '__main__': unittest.main()
