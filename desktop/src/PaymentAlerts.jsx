import React, { useEffect, useState } from 'react';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { fmtDate, money } from './models';
import './consultation.css';

export function PaymentAlerts({ api, sequence }) {
  const [rows, setRows] = useState([]), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  async function refresh() {
    setLoading(true);
    try { setRows(await api('/payment-alerts')); setError(''); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); const timer = setInterval(refresh, 30000); return () => clearInterval(timer); }, [sequence]);
  return <><div className="page-intro"><div><small className="eyebrow">SUIVI DES ÉCHÉANCES</small><h1>Paiements en retard<span>.</span></h1><p className="muted">Soldes non réglés à la date prévue au contrat, ou 15 jours avant l’événement si aucune date n’est indiquée.</p></div><button className="secondary" onClick={refresh} disabled={loading}><RefreshCw size={17}/>Actualiser</button></div>
    {error && <div className="error-box" role="alert">{error}</div>}
    <section className="panel"><div className="table-toolbar"><AlertTriangle size={19}/><h2>{rows.length} dossier(s) à suivre</h2></div><div className="finance-table consultation-table"><table><thead><tr>{['Bon','Client','Salle','Échéance','Événement','Retard','Solde à recevoir'].map(v=><th key={v}>{v}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.bon}</td><td>{r.client}</td><td>{r.salle}</td><td>{fmtDate(r.dueDate)}</td><td>{fmtDate(r.eventDate)}</td><td>{r.daysLate} jour(s)</td><td>{money(r.amount)}</td></tr>)}</tbody></table>{!rows.length&&<div className="empty">Aucun paiement en retard.</div>}</div></section></>;
}
