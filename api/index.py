# -*- coding: utf-8 -*-
"""
api/index.py — Démonstration web de Marassim (phase de test).

⚠ CE N'EST PAS L'APPLICATION. L'application Marassim est un logiciel de bureau
  Windows (Tkinter), hors ligne, qui ne peut pas tourner sur un serveur.

Cette page existe pour montrer et tester en ligne, depuis n'importe quel
appareil, la partie qui se prête à une démonstration :

  · le calendrier des salles,
  · les règles de réservation saisies,
  · et surtout le TESTEUR DE RÈGLES, qui appelle le vrai moteur
    `rules.validate_reservation()` — le même code que l'application de bureau.

Les données sont fictives (voir api/demo_data.py) et non persistantes.
"""
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import demo_data                      # fixe MARASSIM_DB_* avant tout import
demo_data.build()

import database                       # noqa: E402
import rules                          # noqa: E402
from flask import Flask, request      # noqa: E402

app = Flask(__name__)                 # ← l'objet que Vercel cherche

MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
        "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
COUL = {"Almes": "#3B82F6", "Chichkhane": "#EF4444", "Rayhane": "#22C55E"}

CSS = """
:root{--bg:#F6F8FB;--sf:#fff;--sf2:#F1F5F9;--bd:#E4E9F0;--tx:#0F172A;
--tm:#64748B;--td:#94A3B8;--pr:#4F46E5;--prl:#EEF2FF;--prd:#4338CA;
--ok:#059669;--okl:#ECFDF5;--ko:#DC2626;--kol:#FEF2F2;--vi:#7C3AED;--vil:#F5F3FF;
--wa:#D97706;--wal:#FFFBEB}
@media(prefers-color-scheme:dark){:root{--bg:#0B1220;--sf:#131C2E;--sf2:#1B2537;
--bd:#26324A;--tx:#E8EDF6;--tm:#9AA7BD;--td:#6B7A93;--prl:#1E1B4B;--okl:#052E23;
--kol:#3B0A0A;--vil:#231640;--wal:#3A2606}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.55 "Segoe UI",system-ui,-apple-system,Inter,sans-serif}
a{color:var(--pr)}
.wrap{max-width:1120px;margin:0 auto;padding:0 18px 56px}
header{background:var(--sf);border-bottom:1px solid var(--bd)}
.hd{max-width:1120px;margin:0 auto;padding:18px;display:flex;
align-items:center;gap:14px;flex-wrap:wrap}
.logo{width:40px;height:40px;border-radius:10px;background:var(--pr);color:#fff;
display:grid;place-items:center;font-weight:700;font-size:18px;flex:0 0 auto}
h1{font-size:19px;margin:0}
.sub{color:var(--tm);font-size:12px;margin-top:1px}
nav{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
nav a{padding:8px 14px;border-radius:8px;text-decoration:none;color:var(--tm);
font-weight:600;font-size:13px}
nav a.on{background:var(--pr);color:#fff}
.banner{background:var(--wal);border:1px solid var(--wa);border-radius:10px;
padding:12px 15px;margin:20px 0;font-size:13px;color:var(--tx)}
.banner b{color:var(--wa)}
.card{background:var(--sf);border:1px solid var(--bd);border-radius:13px;
padding:20px;margin-bottom:18px}
.card h2{margin:0 0 4px;font-size:15px}
.card .hint{color:var(--tm);font-size:12.5px;margin:0 0 16px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:11px;letter-spacing:.4px;color:var(--tm);
text-transform:uppercase;padding:9px 10px;background:var(--sf2)}
td{padding:10px;border-top:1px solid var(--bd)}
tr:nth-child(even) td{background:color-mix(in srgb,var(--sf2) 45%,transparent)}
.pill{display:inline-block;padding:3px 9px;border-radius:99px;font-size:11px;
font-weight:700;color:#fff}
.tag{display:inline-block;padding:3px 9px;border-radius:99px;font-size:11px;
font-weight:700;background:var(--sf2);color:var(--tm)}
.tag.ok{background:var(--okl);color:var(--ok)}
.tag.vi{background:var(--vil);color:var(--vi)}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}
.cal .dh{font-size:10.5px;font-weight:700;color:var(--tm);text-align:center;
padding:7px 0;text-transform:uppercase}
.cel{background:var(--sf2);border:1px solid var(--bd);border-radius:8px;
min-height:88px;padding:6px}
.cel.out{opacity:.35}
.cel .n{font-size:12px;font-weight:700;color:var(--tm);text-align:right}
.ev{margin-top:4px;border-radius:5px;padding:3px 5px;font-size:10px;
font-weight:700;color:#fff;line-height:1.35;overflow:hidden}
.ev.vi{background:var(--vi)}
form{display:grid;gap:14px}
.row{display:flex;gap:12px;flex-wrap:wrap}
.fld{flex:1 1 150px;min-width:130px}
label{display:block;font-size:11.5px;font-weight:700;color:var(--tm);
margin-bottom:5px;text-transform:uppercase;letter-spacing:.3px}
input,select{width:100%;padding:10px 11px;border:1px solid var(--bd);
border-radius:8px;background:var(--sf);color:var(--tx);font:inherit}
input:focus,select:focus{outline:2px solid var(--pr);outline-offset:-1px;
border-color:var(--pr)}
.chk{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600}
.chk input{width:auto}
button{background:var(--pr);color:#fff;border:0;border-radius:9px;
padding:12px 22px;font:inherit;font-weight:700;cursor:pointer}
button:hover{background:var(--prd)}
.verdict{border-radius:11px;padding:16px 18px;margin-top:4px;
border:1px solid;font-size:13.5px}
.verdict.ok{background:var(--okl);border-color:var(--ok);color:var(--ok)}
.verdict.ko{background:var(--kol);border-color:var(--ko);color:var(--ko)}
.verdict b{display:block;font-size:15px;margin-bottom:5px}
.verdict .rule{margin-top:9px;font-size:12px;opacity:.85;color:var(--tx)}
code{background:var(--sf2);padding:2px 6px;border-radius:5px;font-size:12px}
footer{color:var(--td);font-size:12px;text-align:center;padding:26px 18px}
.empty{color:var(--td);text-align:center;padding:34px;font-size:13px}
"""


def page(active, body):
    tabs = [("/", "Calendrier"), ("/reservations", "Réservations"),
            ("/regles", "Règles"), ("/tester", "Tester une règle")]
    nav = "".join(
        f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>'
        for h, t in tabs)
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marassim — démonstration</title><style>{CSS}</style></head><body>
<header><div class="hd"><div class="logo">M</div>
<div><h1>Marassim</h1><div class="sub">Complexe de réception — démonstration</div></div>
<nav>{nav}</nav></div></header>
<div class="wrap">
<div class="banner"><b>Démonstration.</b> L'application Marassim est un logiciel
de bureau Windows hors ligne ; cette page en montre une partie pour la phase de
test. Les données affichées sont <b>fictives</b> et ne sont pas conservées. Le
testeur de règles appelle en revanche le <b>vrai moteur</b>
<code>rules.validate_reservation()</code>.</div>
{body}</div>
<footer>Marassim — démonstration web · moteur de règles partagé avec
l'application de bureau</footer></body></html>"""


def _mois_courant():
    try:
        y = int(request.args.get("y") or 0)
        m = int(request.args.get("m") or 0)
        if 1 <= m <= 12 and 2000 <= y <= 2100:
            return y, m
    except (TypeError, ValueError):
        pass
    t = date.today()
    return t.year, t.month


@app.route("/")
def calendrier():
    import calendar as cal
    y, m = _mois_courant()
    first = date(y, m, 1)
    last = date(y, m, cal.monthrange(y, m)[1])
    resas = database.get_reservations_in_range(first.isoformat(), last.isoformat())

    par_jour = {}
    for r in resas:
        par_jour.setdefault(r["date_evenement"], []).append(r)
        if r.get("with_violoniste") and r.get("violoniste_heure_debut"):
            v = dict(r); v["_violon"] = True
            par_jour.setdefault(r.get("violoniste_date") or r["date_evenement"],
                                []).append(v)

    cells = "".join(f'<div class="dh">{j}</div>' for j in JOURS)
    for week in cal.Calendar(firstweekday=0).monthdatescalendar(y, m):
        for d in week:
            out = "" if d.month == m else " out"
            evs = ""
            for r in sorted(par_jour.get(d.isoformat(), []),
                            key=lambda x: x.get("heure_debut") or ""):
                if r.get("_violon"):
                    evs += (f'<div class="ev vi">🎻 '
                            f'{r["violoniste_heure_debut"]}-{r["violoniste_heure_fin"]}</div>')
                else:
                    c = COUL.get(r["salle"], "#64748B")
                    evs += (f'<div class="ev" style="background:{c}">'
                            f'{r["salle"][:3].upper()} {r["heure_debut"]}</div>')
            cells += (f'<div class="cel{out}"><div class="n">{d.day}</div>{evs}</div>')

    prev = (first - timedelta(days=1))
    nxt = (last + timedelta(days=1))
    body = f"""<div class="card">
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px">
<h2 style="margin:0">{MOIS[m-1]} {y}</h2>
<div style="margin-left:auto;display:flex;gap:6px">
<a href="/?y={prev.year}&m={prev.month}" class="tag">‹ {MOIS[prev.month-1][:4]}</a>
<a href="/?y={nxt.year}&m={nxt.month}" class="tag">{MOIS[nxt.month-1][:4]} ›</a></div></div>
<div style="margin-bottom:12px;display:flex;gap:8px;flex-wrap:wrap">
{''.join(f'<span class="pill" style="background:{c}">{s}</span>' for s, c in COUL.items())}
<span class="pill" style="background:#7C3AED">🎻 Violon offert</span></div>
<div class="cal">{cells}</div></div>"""
    return page("/", body)


@app.route("/reservations")
def liste():
    resas = sorted(database.get_all_reservations(),
                   key=lambda r: r["date_evenement"])
    if not resas:
        return page("/reservations",
                    '<div class="card"><div class="empty">Aucune réservation.</div></div>')
    lignes = ""
    for r in resas:
        forfait = float(r.get("forfait") or 0)
        paye = sum(float(r.get(f"acompte{i}") or 0) for i in range(1, 4))
        reste = forfait - paye
        c = COUL.get(r["salle"], "#64748B")
        viol = ('<span class="tag vi">🎻 offert</span>'
                if r.get("with_violoniste") else "")
        statut = ('<span class="tag ok">soldé</span>' if reste <= 0
                  else f'<span class="tag">reste {reste:,.0f} DT</span>')
        lignes += f"""<tr><td><code>{r.get('num_bon') or ''}</code></td>
<td><span class="pill" style="background:{c}">{r['salle']}</span></td>
<td>{r['date_evenement']}</td><td>{r['heure_debut']}–{r['heure_fin']}</td>
<td>{r.get('nom_client') or ''}</td><td>{r.get('type_evenement') or ''}</td>
<td style="text-align:right">{forfait:,.0f} DT</td>
<td>{statut} {viol}</td></tr>"""
    body = f"""<div class="card"><h2>Réservations</h2>
<p class="hint">{len(resas)} réservations fictives, générées pour la démonstration.</p>
<div style="overflow-x:auto"><table><tr><th>N° bon</th><th>Salle</th><th>Date</th>
<th>Créneau</th><th>Client</th><th>Type</th><th style="text-align:right">Forfait</th>
<th>Statut</th></tr>{lignes}</table></div></div>"""
    return page("/reservations", body)


@app.route("/regles")
def regles():
    rs = database.get_all_rules()
    if not rs:
        return page("/regles",
                    '<div class="card"><div class="empty">Aucune règle.</div></div>')
    lignes = ""
    for r in rs:
        cr = rules.parse_creneaux(r["creneaux"])
        creneaux = (", ".join(f"{a}-{b}" for a, b in cr) if cr
                    else '<span style="color:var(--td)">horaires libres</span>')
        periode = ("Toujours" if not (r["date_debut"] or r["date_fin"])
                   else f"{r['date_debut'] or '…'} → {r['date_fin'] or '…'}")
        viol = (f'<span class="tag vi">🎻 {r["violon_debut_min"]}–'
                f'{r["violon_fin_max"]}</span>' if r["violon_gratuit"] else "—")
        salle = "Toutes" if r["salle"] == "*" else r["salle"]
        c = COUL.get(r["salle"], "#64748B")
        lignes += f"""<tr><td><b>{r['nom']}</b><br>
<span style="color:var(--tm);font-size:12px">{r.get('notes') or ''}</span></td>
<td><span class="pill" style="background:{c}">{salle}</span></td>
<td>{periode}</td><td>{rules.jours_label(r['jours'])}</td>
<td>{creneaux}</td><td>{r['pause_min_heures'] or 0} h</td>
<td>{r['heure_fin_max'] or '—'}</td><td>{viol}</td></tr>"""
    body = f"""<div class="card"><h2>Règles de réservation</h2>
<p class="hint">Toute réservation qui sort de la règle applicable est refusée
comme conflit. Ces règles se saisissent dans l'application de bureau.</p>
<div style="overflow-x:auto"><table><tr><th>Règle</th><th>Salle</th><th>Période</th>
<th>Jours</th><th>Créneaux autorisés</th><th>Pause</th><th>Fin max</th>
<th>Violon</th></tr>{lignes}</table></div></div>"""
    return page("/regles", body)


@app.route("/tester", methods=["GET", "POST"])
def tester():
    f = request.form if request.method == "POST" else {}
    salle = f.get("salle") or "Almes"
    d = f.get("date") or (date.today() + timedelta(days=20)).isoformat()
    hd = f.get("hd") or "15:00"
    hf = f.get("hf") or "18:00"
    sono = bool(f.get("sono"))
    viol = bool(f.get("violon"))
    vd = f.get("vd") or "18:00"
    vf = f.get("vf") or "19:00"

    verdict = ""
    if request.method == "POST":
        res = {"salle": salle, "date_evenement": d, "heure_debut": hd,
               "heure_fin": hf, "with_sono": 1 if sono else 0,
               "with_violoniste": 1 if viol else 0,
               "violoniste_date": d if viol else None,
               "violoniste_heure_debut": vd if viol else None,
               "violoniste_heure_fin": vf if viol else None,
               "type_evenement": ""}
        try:
            ok, msg = rules.validate_reservation(res)
        except Exception as ex:
            ok, msg = False, f"Erreur d'analyse : {ex}"
        r = rules.find_matching_rule(salle, d, hd, hf)
        applied = (f'Règle appliquée : {rules.describe_rule(r)}' if r else
                   'Aucune règle ne couvre cette salle à cette date — '
                   'le comportement historique s\'applique.')
        if ok:
            verdict = (f'<div class="verdict ok"><b>✓ Réservation acceptée</b>'
                       f'Le créneau respecte la règle applicable.'
                       f'<div class="rule">{applied}</div></div>')
        else:
            verdict = (f'<div class="verdict ko"><b>✕ Réservation refusée</b>'
                       f'{msg}<div class="rule">{applied}</div></div>')

    def sel(v):
        return "".join(f'<option{" selected" if s == v else ""}>{s}</option>'
                       for s in ("Almes", "Chichkhane", "Rayhane"))

    body = f"""<div class="card"><h2>Tester une règle</h2>
<p class="hint">Ce formulaire appelle <code>rules.validate_reservation()</code> —
exactement la fonction qu'utilise l'application de bureau. Essaie par exemple
Almes 16:00→19:00 (hors créneau), ou Chichkhane 15:00→18:00 avec violon
(non inclus sur ce créneau), ou Rayhane 18:00→22:00 (dépasse 21 h).</p>
<form method="post">
<div class="row">
<div class="fld"><label>Salle</label><select name="salle">{sel(salle)}</select></div>
<div class="fld"><label>Date</label><input type="date" name="date" value="{d}"></div>
<div class="fld"><label>Heure début</label><input name="hd" value="{hd}"></div>
<div class="fld"><label>Heure fin</label><input name="hf" value="{hf}"></div>
</div>
<div class="row">
<label class="chk"><input type="checkbox" name="sono" {'checked' if sono else ''}> Sono</label>
<label class="chk"><input type="checkbox" name="violon" {'checked' if viol else ''}> Violoniste offert</label>
<div class="fld"><label>Violon début</label><input name="vd" value="{vd}"></div>
<div class="fld"><label>Violon fin</label><input name="vf" value="{vf}"></div>
</div>
<div><button type="submit">Vérifier</button></div>
</form>{verdict}</div>"""
    return page("/tester", body)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
