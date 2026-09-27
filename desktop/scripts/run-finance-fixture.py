"""Local fictitious fixture for UI verification; never uses a production database."""
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from app import Application, serve
from analytics import month_after
root = Path(__file__).resolve().parents[1]/'test-results/ui-finance-fixture'
application = Application(root)
with application.storage.transaction() as conn:
    exists = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
if not exists:
    application.dispatch('POST','/api/setup',{'X-Bootstrap-Key':application.bootstrap.read_text()},{'username':'ui-test','password':'ui-test-password'})
token = application.dispatch('POST','/api/login',{}, {'username':'ui-test','password':'ui-test-password'})['token']
def call(path,body):
    return application.dispatch('POST','/api'+path,{'Authorization':'Bearer '+token,'Idempotency-Key':str(uuid.uuid4())},body)
with application.storage.transaction() as conn:
    has_rows = conn.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
if not has_rows:
    base = date.today().replace(day=1)
    for n in range(15):
        hall = ['Almes','Chichkhane','Rayhane'][n%3]
        day = month_after(base,n//6).replace(day=3+(n%6)*4)
        call('/reservations',dict(salle=hall,nom_client=['Mariage Yasmine & Ahmed','Réception Famille Ben Ali','Fiançailles Nour'][n%3],date_evenement=day.isoformat(),heure_debut='16:00' if hall=='Rayhane' else '21:00',heure_fin='20:00' if hall=='Rayhane' else '01:00',forfait=4500+n*350,acompte1=1500,date_acompte1=base.isoformat(),methode_acompte1='Espèce',num_caisse1=str(n+1),with_sono=1,type_evenement=['Mariage','Réception','Fiançailles'][n%3],is_temporaire=1 if n==5 else 0))
    call('/forecast-items',dict(due_date=(date.today()+timedelta(days=2)).isoformat(),designation='Loyer des salles',direction='out',amount=8500,category='Loyer',frequency='monthly',repeat_until=month_after(date.today(),6).isoformat()))
    call('/forecast-items',dict(due_date=(date.today()+timedelta(days=5)).isoformat(),designation='Préparation et entretien',direction='out',amount=3000,category='Entretien'))
server = serve(application,'127.0.0.1',18744,insecure=True)
try: server.serve_forever()
finally: server.server_close()
