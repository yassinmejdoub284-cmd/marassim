"""Optional, consent-based Web Push; deliveries follow a completed LAN upload."""
import hashlib
import json
import os
import time
from urllib.parse import urlparse
from app import APIError

def may_receive(user):
    return user['role']=='admin' or any(m in user['modules'] for m in ('Réservations','Calendrier','Nouvelle réservation','Ajouter un acompte','Rapports avancés','Cash-flow prévu'))

def push_route(pg,user,method,path,payload):
    if not may_receive(user): raise APIError('Notifications de réservation non autorisées.',403)
    public=os.environ.get('VAPID_PUBLIC_KEY','')
    if path=='/push/config' and method=='GET': return {'enabled':bool(public and os.environ.get('VAPID_PRIVATE_KEY') and os.environ.get('VAPID_SUBJECT')),'publicKey':public}
    if path!='/push/subscribe' or method!='POST': raise APIError('Page introuvable.',404)
    sub=payload.get('subscription',{}); endpoint=sub.get('endpoint',''); url=urlparse(endpoint)
    host=url.hostname or ''
    trusted=host=='fcm.googleapis.com' or host=='updates.push.services.mozilla.com' or host.endswith('.push.services.mozilla.com') or host=='web.push.apple.com' or host.endswith('.push.apple.com')
    if url.scheme!='https' or url.username or url.password or url.port not in (None,443) or not trusted or len(json.dumps(sub))>10000 or not all(sub.get('keys',{}).get(k) for k in ('p256dh','auth')):
        raise APIError('Abonnement de notification invalide.')
    identifier=hashlib.sha256(endpoint.encode()).hexdigest()
    with pg.cursor() as cursor:
        if payload.get('remove'):
            cursor.execute('DELETE FROM online_push WHERE id=%s AND user_id=%s',(identifier,user['id']))
        else:
            cursor.execute('INSERT INTO online_push(id,user_id,subscription) VALUES (%s,%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET user_id=excluded.user_id,subscription=excluded.subscription',(identifier,user['id'],json.dumps(sub)))
    return {'ok':True}

def queue_push(cursor,new,old,secret):
    if not old: return  # Initial synchronization is a baseline, not a booking burst.
    from cloud_web import unpack,public_user
    previous,_,_=unpack(old[2],secret)
    try: last=previous.execute('SELECT COALESCE(MAX(id),0) FROM reservation_notifications').fetchone()[0]
    finally: previous.close()
    rows=new.execute('SELECT * FROM reservation_notifications WHERE id>? ORDER BY id',(last,)).fetchall()
    if not rows: return
    recipients=[row for row in new.execute('SELECT * FROM users WHERE actif=1') if may_receive(public_user(new,row))]
    for event in rows:
        payment='kind' in event.keys() and event['kind']=='payment'
        body={'title':'Paiement reçu Marassim' if payment else 'Nouvelle réservation Marassim',
              'body':f"{event['hall']} · {event['event_date']}"+(f" · {float(event['amount'] or 0):.3f} DT" if payment else ''),
              'url':'/','tag':'marassim-event-'+str(event['id'])}
        for row in recipients:
            identifier=f"{row['id']}:{event['id']}"
            cursor.execute('INSERT INTO online_push_outbox(id,user_id,body) VALUES (%s,%s,%s::jsonb) ON CONFLICT(id) DO NOTHING',(identifier,row['id'],json.dumps(body)))

def deliver_push():
    if not os.environ.get('VAPID_PRIVATE_KEY') or not os.environ.get('VAPID_SUBJECT'): return
    from pywebpush import webpush,WebPushException
    from cloud_web import postgres,latest,unpack,public_user
    deadline=time.monotonic()+20
    with postgres() as pg:
        snapshot=latest(pg); conn,_,_=unpack(snapshot['encrypted'],os.environ['MARASSIM_SYNC_SECRET'])
        try:
            with pg.cursor() as cursor:
                cursor.execute('SELECT id,user_id,body FROM online_push_outbox ORDER BY created_at LIMIT 10 FOR UPDATE SKIP LOCKED')
                for identifier,user_id,body in cursor.fetchall():
                    row=conn.execute('SELECT * FROM users WHERE id=? AND actif=1',(user_id,)).fetchone()
                    if not row or not may_receive(public_user(conn,row)):
                        cursor.execute('DELETE FROM online_push_outbox WHERE id=%s',(identifier,)); continue
                    cursor.execute('SELECT id,subscription FROM online_push WHERE user_id=%s',(user_id,))
                    failed=False
                    for sub_id,sub in cursor.fetchall():
                        if time.monotonic()>=deadline: return  # Commit progress; retry the remaining durable outbox on the next transfer.
                        try:
                            webpush(subscription_info=sub,data=json.dumps(body),vapid_private_key=os.environ['VAPID_PRIVATE_KEY'],vapid_claims={'sub':os.environ['VAPID_SUBJECT']},timeout=5)
                        except WebPushException as error:
                            if error.response is not None and error.response.status_code in (404,410): cursor.execute('DELETE FROM online_push WHERE id=%s',(sub_id,))
                            else: failed=True
                    if not failed: cursor.execute('DELETE FROM online_push_outbox WHERE id=%s',(identifier,))
        finally: conn.close()
