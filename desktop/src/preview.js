// Explicit visual preview only. Never used in Electron; no production data or writes.
import { today, halls, schemas } from './models';
import { previewReport, previewForecast } from './preview-finance';
const month = today().slice(0, 8);
const rows = [
  [2, 'Almes', 'Yasmine & Ahmed', '21:00', '01:00', 8200, 2500], [5, 'Chichkhane', 'Sarra Ben Ali', '15:00', '18:00', 5400, 1800],
  [8, 'Rayhane', 'Réception Famille Mansour', '16:00', '20:00', 4600, 1500], [11, 'Almes', 'Amira & Mohamed', '21:00', '01:00', 8500, 3000],
  [12, 'Chichkhane', 'Inès & Khalil', '21:00', '01:00', 7600, 2000], [16, 'Almes', 'Fiançailles Nour', '15:00', '18:00', 4800, 2000],
  [18, 'Rayhane', 'Anniversaire Lina', '16:00', '20:00', 3200, 1200], [19, 'Chichkhane', 'Hana & Aziz', '21:00', '01:00', 7200, 3000],
  [22, 'Almes', 'Malek & Rania', '21:00', '01:00', 8600, 2500], [24, 'Chichkhane', 'Meriem & Wassim', '15:00', '18:00', 5200, 2000],
  [26, 'Almes', 'Mariage Salma', '21:00', '01:00', 8500, 0], [27, 'Rayhane', 'Réception privée', '16:00', '20:00', 4000, 1000],
].map(([day, salle, nom_client, heure_debut, heure_fin, forfait, acompte1], n) => ({ id: n + 1, num_bon: `BON-2026-${String(n + 1).padStart(4, '0')}`, salle, nom_client, date_evenement: month + String(day).padStart(2, '0'), heure_debut, heure_fin, forfait, acompte1, date_acompte1: month + '01', methode_acompte1: 'Espèce', num_caisse1: String(n + 11), tel1: '20 000 000', type_evenement: 'Mariage', revision: 1, is_temporaire: n === 10 ? 1 : 0 }));
const user = { id: 1, username: 'preview', nom: 'Marassim', prenom: 'Équipe', role: 'admin', actif: 1, modules: [] };
const wrap = value => Promise.resolve({ ok: true, value });
export const previewBridge = {
  config: () => wrap({ mode: 'server', serverUrl: 'https://192.168.1.10:7443', configured: true }),
  request: (path, options = {}) => {
    if (path === '/login') return wrap({ user });
    if (path === '/health') return wrap({ ok: true, needsSetup: false });
    if (path === '/me') return wrap(user);
    if (options.method && options.method !== 'GET') return Promise.resolve({ ok: false, error: 'L’aperçu est en lecture seule. Utilisez l’application Electron pour enregistrer.' });
    const url = new URL(path, 'http://preview.local');
    if (url.pathname === '/availability') {
      const date=url.searchParams.get('date'), start=url.searchParams.get('start'), end=url.searchParams.get('end'), selected=(url.searchParams.get('salles')||'').split(',');
      const toMin=t=>Number(t.slice(0,2))*60+Number(t.slice(3));
      const interval=(a,b)=>[toMin(a),toMin(b)+(toMin(b)<=toMin(a)?1440:0)];
      const [a,b]=interval(start,end), requested=Date.parse(date+'T00:00:00Z');
      const violin=url.searchParams.get('violoniste')==='1', violinDate=url.searchParams.get('violoniste_date')||date;
      const violinWeekend=[0,6].includes(new Date(violinDate+'T12:00:00Z').getUTCDay());
      const rooms=selected.map(salle=>{
        const conflict=rows.find(r=>r.salle===salle&&r.id!==Number(url.searchParams.get('exclude'))&&(()=>{const offset=Math.round((Date.parse(r.date_evenement+'T00:00:00Z')-requested)/86400000);if(Math.abs(offset)>1)return false;const [c,d]=interval(r.heure_debut,r.heure_fin);return a<d+offset*1440+180&&c+offset*1440<b+180;})());
        const violinBlocked=violin&&(violinWeekend||(selected.every(s=>s==='Rayhane'||s==='Chichkhane')&&start==='15:00'&&end==='18:00'));
        return {salle,available:!conflict&&!violinBlocked,message:conflict?`${salle} déjà réservé à ${conflict.heure_debut}–${conflict.heure_fin}, pause de 3 h requise.`:violinBlocked?'Heure de violoniste offerte indisponible pour ce contrat ou ce jour.':'Disponible'};
      });
      return wrap({available:rooms.every(r=>r.available),rooms,checkedAt:new Date().toISOString()});
    }
    if (url.pathname === '/payment-alerts') return wrap([]);
    if (url.pathname === '/notifications') return wrap({serverId:'preview',latest:0,items:[]});
    if (url.pathname === '/reports') return wrap(previewReport(rows,url.searchParams));
    if (url.pathname === '/forecast') return wrap(previewForecast(rows,url.searchParams));
    if (path === '/reservations') return wrap(rows);
    if (url.pathname === '/pointage/events') return wrap(rows.filter(r => !r.is_temporaire && r.date_evenement === url.searchParams.get('date')).map(({id,salle,date_evenement,heure_debut,heure_fin}) => ({id,salle,date_evenement,heure_debut,heure_fin})));
    if (path.startsWith('/reservations/')) return wrap(rows.find(r => r.id === Number(path.split('/')[2])));
    if (path === '/users') return wrap([user]);
    if (path === '/employees/options') return wrap([]);
    if (path === '/status') return wrap({ server: 'MARASSIM-SERVEUR', fingerprint: 'a7c419afae4f21d94b181d0cc0a92c62d37d5ad7cc321b24f8b741c2f9abc311', latest: { name: 'preview.mrb', created_at: new Date().toISOString() }, replicas: [], verifiedCopies: 1, backupHour: '19:00', retentionDays: 30 });
    if (url.pathname === '/journal' && url.searchParams.get('caisse') === 'omar') {
      const start = url.searchParams.get('start') || month+'01', end = url.searchParams.get('end') || today();
      const history = rows.filter(r => !r.is_temporaire).map(r => ({date:r.date_acompte1, designation:`ACOMPTE CLIENT ${r.nom_client} · ${r.salle}`, montant:500}));
      const recettes = history.filter(r => r.date >= start && r.date <= end), opening = history.filter(r => r.date < start).reduce((sum,r) => sum+r.montant,0), income = recettes.reduce((sum,r) => sum+r.montant,0);
      return wrap({recettes,sorties:[],period:{start,end},opening,income,expense:0,closing:opening+income,net:income,warnings:[]});
    }
    if (path.startsWith('/journal')) return wrap({ recettes: rows.map(r => ({ date: month + '01', designation: `ACOMPTE ${r.nom_client} ${r.salle}`, montant: r.acompte1, fn: '', num_caisse: r.num_caisse1 })), charges: [], sorties: [] });
    if (path === '/reception' || path in schemas || Object.keys(schemas).some(k => path === '/' + k)) return wrap([]);
    return Promise.resolve({ ok: false, error: 'Cette action est disponible dans l’application Electron.' });
  },
  logout: () => wrap({ ok: true }),
  resetConnection: () => wrap({ ok: true }),
  saveFile: () => Promise.resolve({ ok: false, error: 'Les exports sont disponibles dans l’application Electron.' })
};
