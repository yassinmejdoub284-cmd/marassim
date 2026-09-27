import React, { useEffect, useRef, useState } from 'react';
import { Bell, BellRing, X } from 'lucide-react';
import { fmtDate } from './models';
export function Notifications({ api,user,native,cloud=false }) {
  const [items,setItems]=useState([]),[open,setOpen]=useState(false),[error,setError]=useState(''),[enabled,setEnabled]=useState(localStorage.getItem('marassim.notifications.enabled')==='1'),[unread,setUnread]=useState(0);
  const allowed=user && (user.role==='admin'||['Réservations','Calendrier','Rapports avancés','Cash-flow prévu'].some(m=>user.modules.includes(m)));
  const cursor=useRef(null),key=useRef(null),enabledRef=useRef(enabled); enabledRef.current=enabled;
  useEffect(()=>{
    if(!allowed) return;
    let stopped=false,running=false;
    async function load() {
      if(running) return; running=true;
      try {
        const result=await api('/notifications'+(cursor.current===null?'':'?after='+cursor.current));
        if(stopped) return;
        if(!key.current) { key.current=`marassim.notifications.${result.serverId}.${user.id}`; const saved=localStorage.getItem(key.current); cursor.current=saved===null?result.latest:Number(saved); }
        else {
          const fresh=result.items;
          if(fresh.length) {
            setItems(old=>[...fresh.slice().reverse(),...old].slice(0,30)); setUnread(n=>n+fresh.length);
            const message={title:fresh.length===1?'Nouvelle réservation Marassim':`${fresh.length} nouvelles réservations Marassim`,body:`${fresh[fresh.length-1].hall} · ${fmtDate(fresh[fresh.length-1].event_date)}`};
            if(enabledRef.current && native) await native(message).catch(()=>{});
            else if(enabledRef.current && !cloud && 'Notification' in window && Notification.permission==='granted') new Notification(message.title,{body:message.body,icon:'/icon.svg'});
          }
          cursor.current=result.latest;
        }
        localStorage.setItem(key.current,String(cursor.current));
      } catch { /* Connection failures already appear in the main connection banner. */ }
      finally { running=false; }
    }
    load(); const timer=setInterval(load,cloud?30000:5000);
    return ()=>{stopped=true;clearInterval(timer);cursor.current=null;key.current=null;};
  },[user?.id,allowed,cloud]);
  async function enable() {
    setError('');
    try {
      if(native) { setEnabled(true); localStorage.setItem('marassim.notifications.enabled','1'); return; }
      if(!('Notification' in window) || !('serviceWorker' in navigator)) throw new Error('Les notifications ne sont pas disponibles dans ce navigateur.');
      const config=cloud ? await api('/push/config'):null;
      if(cloud && !config.enabled) throw new Error('Le service de notifications en ligne doit être configuré sur Vercel.');
      const permission=await Notification.requestPermission();
      if(permission!=='granted') throw new Error('Autorisez les notifications dans les réglages de ce navigateur.');
      if(cloud) {
        const registration=await navigator.serviceWorker.ready;
        const value=config.publicKey.replace(/-/g,'+').replace(/_/g,'/'); const bytes=Uint8Array.from(atob(value+'='.repeat((4-value.length%4)%4)),c=>c.charCodeAt(0));
        const subscription=await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});
        await api('/push/subscribe',{method:'POST',body:{subscription:subscription.toJSON()}});
      }
      setEnabled(true);localStorage.setItem('marassim.notifications.enabled','1');
    } catch(e) {setError(e.message);}
  }
  if(!allowed) return null;
  return <div className="notification-control"><button className="icon-button" aria-label={`Notifications${unread?` · ${unread} nouvelle(s)`:''}`} onClick={()=>{setOpen(!open);if(!open)setUnread(0);}}><Bell size={19}/>{unread>0 && <i className="notification-count">{Math.min(unread,99)}</i>}</button>{open && <section className="notification-popover"><div className="notification-heading"><h2>Notifications</h2><button className="icon-button" aria-label="Fermer les notifications" onClick={()=>setOpen(false)}><X size={17}/></button></div><p className="muted">{cloud?'Les nouvelles réservations apparaissent après la synchronisation en ligne.':'Nouvelles réservations enregistrées sur le serveur local.'}</p>{!enabled && <button className="secondary compact" onClick={enable}><BellRing size={15}/>Activer les notifications {cloud?'push':''}</button>}{enabled && <small className="green">Notifications activées sur cet appareil</small>}{error && <p className="red" role="alert">{error}</p>}<div className="notification-list">{items.length?items.map(r=><article key={r.id}><b>Nouvelle réservation · {r.hall}</b><small>{fmtDate(r.event_date)} · {r.bon || 'Nouveau bon'}</small></article>):<p className="muted">Aucune nouvelle réservation depuis votre dernière consultation.</p>}</div></section>}</div>;
}
