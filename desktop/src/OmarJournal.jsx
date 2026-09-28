import React, { useEffect, useRef, useState } from 'react';
import { Download, RefreshCw, ChevronLeft, ChevronRight, Wallet } from 'lucide-react';
import { today, fmtDate, money } from './models';
import './consultation.css';

export function monthPeriod(month) {
  const [year, number] = month.split('-').map(Number);
  const last = new Date(year, number, 0).getDate();
  return { start: `${month}-01`, end: `${month}-${String(last).padStart(2, '0')}` };
}
function nextMonth(month, offset) {
  const [year, number] = month.split('-').map(Number), d = new Date(year, number - 1 + offset, 1);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
}
export function OmarJournal({ api, saveFile, notify }) {
  const [month, setMonth] = useState(today().slice(0, 7)), [data, setData] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const period = monthPeriod(month), query = new URLSearchParams({ ...period, caisse: 'omar' }).toString();
  async function load() {
    const current = ++generation.current;
    try { const value = await api('/journal?' + query); if (current === generation.current) { setData(value); setError(''); } }
    catch (e) { if (current === generation.current) setError(e.message); }
  }
  useEffect(() => { setData(null); load(); const timer = setInterval(load, 30000); return () => { generation.current++; clearInterval(timer); }; }, [query]);
  async function exportFile(format) {
    setBusy(true); setError('');
    try { const result = await saveFile(await api('/exports/journal?' + query + '&format=' + format)); if (!result?.canceled) notify('État de caisse enregistré.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <div className="cash-statement"><div className="page-intro"><div><small className="eyebrow">ÉTAT MENSUEL AUTOMATIQUE</small><h1>Caisse Omar<span>.</span></h1><p className="muted">Le solde de fin de mois devient automatiquement le solde de départ du mois suivant.</p></div><Wallet size={30}/></div>
    {error && <div className="error-box" role="alert">{error}</div>}
    <section className="panel finance-filters"><button className="icon-button" aria-label="Mois précédent" onClick={() => setMonth(nextMonth(month,-1))}><ChevronLeft size={18}/></button><label className="field"><span>Mois de caisse</span><input type="month" min="2000-01" max="2200-12" value={month} onChange={e => { if (e.target.value) setMonth(e.target.value); }}/></label><button className="icon-button" aria-label="Mois suivant" onClick={() => setMonth(nextMonth(month,1))}><ChevronRight size={18}/></button><button className="secondary" onClick={load}><RefreshCw size={17}/>Actualiser</button><button className="secondary" disabled={busy || !data} onClick={() => exportFile('xlsx')}><Download size={17}/>Exporter Excel</button><button className="primary" disabled={busy || !data} onClick={() => exportFile('pdf')}><Download size={17}/>État PDF à imprimer</button></section>
    {data ? <><div className="cash-balances">{[['Solde de départ',data.opening],['Débit · recettes',data.income],['Crédit · sorties',data.expense],['Solde de fin',data.closing]].map(([label,value]) => <section className="panel" key={label}><small>{label}</small><b>{money(value)}</b></section>)}</div><section className="panel"><div className="finance-table"><table><thead><tr>{['Date','Désignation','Débit','Crédit','Solde'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>
      <tr className="cash-balance-row"><td>{fmtDate(period.start)}</td><td>SOLDE DE DÉPART</td><td/><td/><td>{money(data.opening)}</td></tr>
      {data.recettes.map((r,n) => <tr key={'income'+n}><td>{fmtDate(r.date)}</td><td>{r.designation}</td><td className="green">{money(r.montant)}</td><td/><td/></tr>)}
      {data.sorties.map((r,n) => <React.Fragment key={'expense'+n}><tr><td>{fmtDate(r.date)}</td><td>{r.designation}</td><td/><td>{money(r.montant)}</td><td/></tr>{r.details?.map((detail,i) => <tr className="cash-detail-row" key={i}><td/><td>{i+1} — {detail.name} ({detail.period} · {money(detail.amount)})</td><td/><td/><td/></tr>)}</React.Fragment>)}
      <tr className="cash-balance-row"><td/><td>TOTAL DES MOUVEMENTS</td><td>{money(data.income)}</td><td>{money(data.expense)}</td><td/></tr><tr className="cash-balance-row"><td>{fmtDate(period.end)}</td><td>SOLDE DE FIN · REPORT AU MOIS SUIVANT</td><td/><td/><td>{money(data.closing)}</td></tr>
    </tbody></table></div></section><p className="finance-note">Solde calculé depuis tout l’historique enregistré : recettes Omar acceptées, recettes manuelles, charges et paiements des employés de nuit. Les lignes de détail expliquent une sortie et ne sont pas comptées une seconde fois.</p>{data.warnings?.map((warning,i)=><div className="error-box" key={i}>{warning}</div>)}</> : <section className="panel"><p className="muted">Génération de l’état mensuel…</p></section>}
  </div>;
}
