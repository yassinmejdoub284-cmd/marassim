import React, { useEffect, useRef, useState } from 'react';
import { Download, RefreshCw, X } from 'lucide-react';
import { schemas, money, fmtDate, today } from './models';
import { monthPeriod } from './OmarJournal';
import './consultation.css';

const extraSchemas = {
  reception: { label: 'Centre de Réception', fields: [
    ['nom_client','Client'],['num_bon','Bon'],['salle','Salle'],['date_evenement','Événement','date'],['slot','Acompte'],['montant_omar','Montant Omar (DT)','number'],['date_acompte','Date de l’acompte','date'],['methode','Méthode'],['statut','État'],['date_accept','Date de validation','date']
  ], columns: ['nom_client','num_bon','date_acompte','montant_omar','statut'] },
  users: { label: 'Gestion des accès', fields: [['username','Identifiant'],['nom','Nom'],['prenom','Prénom'],['role','Rôle'],['actif','Actif','checkbox'],['modules','Modules autorisés']], columns: ['username','nom','prenom','role','actif'] }
};
const configuration = resource => schemas[resource] || { ...extraSchemas[resource], fields: extraSchemas[resource].fields.map(([key,label,type='text'])=>({key,label,type})) };
function valueLabel(field, value, employees = []) {
  if (Array.isArray(value)) return value.join(' · ');
  if (value === null || value === undefined || value === '') return '—';
  if (field.type === 'date') return fmtDate(value);
  if (field.type === 'checkbox') return Number(value) ? 'Oui' : 'Non';
  if (field.key === 'employee_id') { const emp = employees.find(e=>e.id === value); return emp ? `${emp.nom} ${emp.prenom || ''}` : `Employé #${value}`; }
  if (field.label?.includes('(DT)')) return money(value);
  if (field.key === 'statut') return {en_attente:'En attente',accepte:'Accepté',refuse:'Refusé'}[value] || value;
  if (field.key === 'periode') return {midi:'Midi',apres_midi:'Après-midi',soiree:'Soirée',journee_complete:'Journée complète'}[value] || value;
  return String(value);
}
export async function exportSelection(api, resource, rows, allRows, saveFile, notify) {
  if (rows.length > 2000 && rows.length !== allRows.length) throw new Error('Affinez votre recherche pour exporter moins de 2 000 lignes sélectionnées.');
  const query = new URLSearchParams({ resource });
  if (rows.length !== allRows.length) query.set(resource==='reception'?'slots':'ids', [...new Set(rows.map(r=>resource==='reception'?`${r.res_id}:${r.slot}`:r.id))].join(','));
  const result = await saveFile(await api('/exports/table?' + query));
  if (!result?.canceled) notify('Export Excel enregistré.');
}
function ReadModal({ title, close, children }) {
  return <div className="modal-overlay"><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="modal-header"><div><small>CONSULTATION UNIQUEMENT</small><h2>{title}</h2></div><button className="icon-button" aria-label="Fermer la consultation" onClick={close}><X size={20}/></button></div><div className="modal-body">{children}</div></section></div>;
}
export function ReadModule({ resource, api, saveFile, notify, sequence }) {
  const schema = configuration(resource), [rows,setRows]=useState([]), [employees,setEmployees]=useState([]), [search,setSearch]=useState(''), [error,setError]=useState(''), [selected,setSelected]=useState(null), [fiche,setFiche]=useState(null), [busy,setBusy]=useState(false);
  const epoch=useRef(0);
  async function load() {
    const current=++epoch.current;setBusy(true);
    try { const data=await api('/'+resource);if(current!==epoch.current)return;setRows(data);setError('');
      if(['pointage','employee-payments'].includes(resource)) { const options=await api('/employees/options');if(current===epoch.current)setEmployees(options); }
    } catch(e){if(current===epoch.current)setError(e.message);}finally{if(current===epoch.current)setBusy(false);}
  }
  useEffect(()=>{load();return()=>{epoch.current++;};},[resource,sequence]);
  const fields=Object.fromEntries(schema.fields.map(f=>[f.key,f]));
  const filtered=rows.filter(row=>schema.fields.some(f=>valueLabel(f,row[f.key],employees).toLocaleLowerCase('fr').includes(search.toLocaleLowerCase('fr'))));
  async function exportFile(){setBusy(true);try{await exportSelection(api,resource,filtered,rows,saveFile,notify);}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function openFiche(row){try{setFiche(await api(`/employees/${row.id}/fiche`));}catch(e){setError(e.message);}}
  return <><div className="page-intro"><div><small className="eyebrow">CONSULTER & EXPORTER</small><h1>{schema.label}<span>.</span></h1><p className="muted">Les données du serveur, accessibles en lecture seule.</p></div><div className="consultation-actions"><button className="secondary" disabled={busy} onClick={load}><RefreshCw size={17}/>Actualiser</button><button className="primary" disabled={busy} onClick={exportFile}><Download size={17}/>Exporter Excel</button></div></div>
    {error&&<div className="error-box" role="alert">{error}</div>}
    <section className="panel finance-filters"><label className="field consultation-search"><span>Rechercher dans {schema.label.toLocaleLowerCase('fr')}</span><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Nom, date ou désignation"/></label><span className="muted">{filtered.length} ligne(s)</span></section>
    <section className="panel"><div className="finance-table consultation-table"><table><thead><tr>{schema.columns.map(key=><th key={key}>{fields[key]?.label || key}</th>)}<th/></tr></thead><tbody>{filtered.map((row,i)=><tr key={row.id ?? `${row.res_id}-${row.slot}-${i}`}>{schema.columns.map(key=><td key={key}>{valueLabel(fields[key] || {},row[key],employees)}</td>)}<td><button className="secondary compact" onClick={()=>setSelected(row)}>Consulter</button>{resource==='employees'&&<button className="secondary compact" onClick={()=>openFiche(row)}>Fiche & paiements</button>}</td></tr>)}</tbody></table>{!filtered.length&&<div className="empty">Aucune donnée dans cette sélection.</div>}</div></section>
    {selected&&<ReadModal title={schema.label} close={()=>setSelected(null)}><div className="consultation-detail">{schema.fields.map(field=><div key={field.key}><small>{field.label}</small><b>{valueLabel(field,selected[field.key],employees)}</b></div>)}</div></ReadModal>}
    {fiche&&<ReadModal title={`Fiche · ${fiche.employee.nom} ${fiche.employee.prenom || ''}`} close={()=>setFiche(null)}><div className="payment-summary"><span>Total dû<b>{money(fiche.total_du)}</b></span><span>Total payé<b>{money(fiche.total_paye)}</b></span><span>Reste<b>{money(fiche.reste)}</b></span></div><h3>Historique des pointages</h3><div className="finance-table"><table><thead><tr><th>Date</th><th>Période</th><th>Heures supplémentaires</th><th>Notes</th></tr></thead><tbody>{fiche.pointages.map(p=><tr key={p.id}><td>{fmtDate(p.date_pointage)}</td><td>{valueLabel({key:'periode'},p.periode)}</td><td>{p.heures_supplementaires || 0}</td><td>{p.notes || '—'}</td></tr>)}</tbody></table></div><h3>Paiements enregistrés</h3>{fiche.paiements.map(p=><div className="payment-line" key={p.id}><span>{fmtDate(p.date_paiement)} · {p.notes}</span><b>{money(p.montant_total)}</b></div>)}</ReadModal>}
  </>;
}
export function ReadTawfikJournal({ api, saveFile, notify, sequence }) {
  const [period,setPeriod]=useState(monthPeriod(today().slice(0,7))), [data,setData]=useState(null), [error,setError]=useState('');
  const query=new URLSearchParams({...period,caisse:'tawfik'}).toString(),epoch=useRef(0);
  async function load(){const current=++epoch.current;try{const value=await api('/journal?'+query);if(current===epoch.current){setData(value);setError('');}}catch(e){if(current===epoch.current)setError(e.message);}}
  useEffect(()=>{setData(null);load();return()=>{epoch.current++;};},[query,sequence]);
  async function exportFile(){try{await saveFile(await api('/exports/journal?'+query));notify('Journal Excel enregistré.');}catch(e){setError(e.message);}}
  return <><div className="page-intro"><div><small className="eyebrow">CONSULTATION DE CAISSE</small><h1>Journal Caisse Tawfik<span>.</span></h1><p className="muted">Recettes et charges enregistrées sur le serveur.</p></div></div>{error&&<div className="error-box">{error}</div>}<section className="panel finance-filters">{['start','end'].map(key=><label className="field" key={key}><span>{key==='start'?'Du':'Au'}</span><input type="date" value={period[key]} onChange={e=>setPeriod({...period,[key]:e.target.value})}/></label>)}<button className="secondary" onClick={load}><RefreshCw size={17}/>Actualiser</button><button className="primary" onClick={exportFile}><Download size={17}/>Exporter Excel</button></section>{data&&<section className="panel"><div className="finance-table"><table><thead><tr><th>Date</th><th>Désignation</th><th>FN°</th><th>N° Caisse</th><th>Recette</th><th>Charge</th></tr></thead><tbody>{[...data.recettes.map(r=>({...r,income:true})),...data.charges].map((r,i)=><tr key={i}><td>{fmtDate(r.date)}</td><td>{r.designation}</td><td>{r.fn || '—'}</td><td>{r.num_caisse || '—'}</td><td>{r.income?money(r.montant):'—'}</td><td>{!r.income?money(r.montant):'—'}</td></tr>)}</tbody></table></div></section>}</>;
}
export function CalendarExport({ api, saveFile, notify }) {
  const [month,setMonth]=useState(today().slice(0,7)),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  return <><div className="page-intro"><div><small className="eyebrow">LE MODÈLE EXCEL EXISTANT</small><h1>Export du calendrier<span>.</span></h1><p className="muted">Retrouvez le calendrier mensuel avec le modèle de votre application.</p></div></div>{error&&<div className="error-box">{error}</div>}<section className="panel finance-filters"><label className="field"><span>Mois</span><input type="month" value={month} min="2000-01" max="2200-12" onChange={e=>{if(e.target.value)setMonth(e.target.value);}}/></label><button className="primary" disabled={busy} onClick={async()=>{setBusy(true);try{const [year,number]=month.split('-');await saveFile(await api(`/exports/calendar?year=${year}&month=${number}`));notify('Calendrier Excel enregistré.');setError('');}catch(e){setError(e.message);}finally{setBusy(false);}}}><Download size={17}/>Exporter Excel</button></section></>;
}
export function ReadNetwork({ api, sequence }) {
  const [status,setStatus]=useState(null),[error,setError]=useState('');
  useEffect(()=>{let stopped=false;api('/status').then(value=>{if(!stopped){setStatus(value);setError('');}}).catch(e=>{if(!stopped)setError(e.message);});return()=>{stopped=true;};},[sequence]);
  return <><div className="page-intro"><div><small className="eyebrow">SITUATION LORS DE LA DERNIÈRE COPIE</small><h1>Réseau & sauvegardes<span>.</span></h1><p className="muted">Consultez les confirmations des postes ; les réglages restent dans l’application locale.</p></div></div>{error&&<div className="error-box">{error}</div>}{status?.available===false&&<section className="panel"><p>Ce suivi sera disponible après la mise à jour du serveur et sa prochaine synchronisation.</p></section>}{status?.available&&<><div className="cash-balances"><section className="panel"><small>Copies vérifiées</small><b>{status.verifiedCopies} / 5</b></section><section className="panel"><small>Sauvegarde quotidienne</small><b>19:00</b></section><section className="panel"><small>Conservation</small><b>30 jours</b></section><section className="panel"><small>Dernière sauvegarde</small><b>{status.latest ? new Date(status.latest.created_at).toLocaleString('fr-FR') : 'En attente'}</b></section></div><section className="panel"><div className="finance-table"><table><thead><tr><th>Poste</th><th>Dernière confirmation</th><th>État</th></tr></thead><tbody>{status.replicas.map((r,i)=><tr key={i}><td>{r.name}</td><td>{r.last_seen?new Date(r.last_seen).toLocaleString('fr-FR'):'En attente'}</td><td>{r.verified?'Copie vérifiée':r.active?'Copie à actualiser':'Révoqué'}</td></tr>)}</tbody></table></div></section></>}</>;
}
