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


class _StripVercelPrefix:
    """Rend l'application insensible au préfixe ajouté par Vercel.

    Vercel réécrit `/` en `/api/index` avant d'appeler la fonction : Flask
    recevait un chemin qu'aucune route ne déclarait et répondait 404. On
    retire ce préfixe pour que `/`, `/regles`… fonctionnent aussi bien en
    local qu'en ligne, quelle que soit la façon dont Vercel route.
    """

    PREFIXES = ("/api/index.py", "/api/index", "/api")

    def __init__(self, wsgi_app):
        self._app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "") or "/"
        for pref in self.PREFIXES:
            if path == pref:
                environ["PATH_INFO"] = "/"
                break
            if path.startswith(pref + "/"):
                environ["PATH_INFO"] = path[len(pref):]
                break
        return self._app(environ, start_response)


app.wsgi_app = _StripVercelPrefix(app.wsgi_app)


@app.errorhandler(404)
def _introuvable(_):
    return page("", """<div class="card"><h2>Page introuvable</h2>
<p class="hint">Cette adresse n'existe pas dans la démonstration.</p>
<div style="display:flex;gap:8px;flex-wrap:wrap">
<a href="/" class="tag">Calendrier</a>
<a href="/reservations" class="tag">Réservations</a>
<a href="/regles" class="tag">Règles</a>
<a href="/tester" class="tag">Tester une règle</a></div></div>"""), 404

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
            ("/acomptes", "Acomptes"), ("/journal", "Caisse"),
            ("/charges", "Charges"), ("/employes", "Employés"),
            ("/pointage", "Pointage"), ("/regles", "Règles"),
            ("/tester", "Tester")]
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



def _euro(v):
    return f"{float(v or 0):,.0f} DT".replace(",", " ")


@app.route("/acomptes")
def acomptes():
    resas = sorted(database.get_all_reservations(),
                   key=lambda r: r["date_evenement"])
    tot_f = tot_p = 0.0
    lignes = ""
    for r in resas:
        forfait = float(r.get("forfait") or 0)
        paye = sum(float(r.get(f"acompte{i}") or 0) for i in range(1, 4))
        reste = forfait - paye
        tot_f += forfait; tot_p += paye
        pct = int(paye / forfait * 100) if forfait else 0
        barre = (f'<div style="background:var(--sf2);border-radius:99px;height:7px;'
                 f'overflow:hidden;min-width:90px"><div style="width:{min(pct,100)}%;'
                 f'height:100%;background:{"var(--ok)" if reste<=0 else "var(--pr)"}">'
                 f'</div></div>')
        details = " · ".join(
            f'{_euro(r.get(f"acompte{i}"))} le {r.get(f"date_acompte{i}")}'
            for i in range(1, 4) if r.get(f"acompte{i}"))
        c = COUL.get(r["salle"], "#64748B")
        lignes += f"""<tr><td><code>{r.get('num_bon') or ''}</code></td>
<td>{r.get('nom_client') or ''}<br><span style="color:var(--tm);font-size:11.5px">
{r['date_evenement']} · <span class="pill" style="background:{c};font-size:10px">
{r['salle']}</span></span></td>
<td style="font-size:11.5px;color:var(--tm)">{details or '—'}</td>
<td style="text-align:right">{_euro(forfait)}</td>
<td style="text-align:right">{_euro(paye)}</td>
<td style="text-align:right;font-weight:700;
color:{'var(--ok)' if reste<=0 else 'var(--tx)'}">{_euro(reste)}</td>
<td style="min-width:110px">{barre}<span style="font-size:11px;color:var(--tm)">
{pct}%</span></td></tr>"""
    reste_tot = tot_f - tot_p
    body = f"""<div class="card"><h2>Acomptes et soldes</h2>
<p class="hint">Suivi des encaissements par contrat. Dans l'application, les
acomptes s'ajoutent depuis le module « Ajouter un acompte ».</p>
<div class="row" style="margin-bottom:16px">
<div class="fld"><label>Total forfaits</label>
<div style="font-size:21px;font-weight:700">{_euro(tot_f)}</div></div>
<div class="fld"><label>Encaissé</label>
<div style="font-size:21px;font-weight:700;color:var(--ok)">{_euro(tot_p)}</div></div>
<div class="fld"><label>Reste à encaisser</label>
<div style="font-size:21px;font-weight:700;color:var(--wa)">{_euro(reste_tot)}</div></div>
</div>
<div style="overflow-x:auto"><table><tr><th>N° bon</th><th>Client</th>
<th>Versements</th><th style="text-align:right">Forfait</th>
<th style="text-align:right">Payé</th><th style="text-align:right">Reste</th>
<th>Avancement</th></tr>{lignes}</table></div></div>"""
    return page("/acomptes", body)


@app.route("/journal")
def journal():
    y, m = _mois_courant()
    import calendar as cal
    debut = date(y, m, 1).isoformat()
    fin = date(y, m, cal.monthrange(y, m)[1]).isoformat()
    j = database.get_journal_caisse(debut, fin)
    rec, chg = j["recettes"], j["charges"]
    tr = sum(x["montant"] for x in rec)
    tc = sum(x["montant"] for x in chg)

    lr = "".join(f"""<tr><td>{x['date']}</td><td>{x['designation']}</td>
<td><code>{x.get('num_caisse') or ''}</code></td>
<td style="text-align:right;color:var(--ok);font-weight:700">
+{_euro(x['montant'])}</td></tr>""" for x in rec) or \
        '<tr><td colspan="4" class="empty">Aucune recette sur la période.</td></tr>'
    lc = "".join(f"""<tr><td>{x['date']}</td><td>{x['designation']}</td>
<td style="text-align:right;color:var(--ko);font-weight:700">
−{_euro(x['montant'])}</td></tr>""" for x in chg) or \
        '<tr><td colspan="3" class="empty">Aucune charge sur la période.</td></tr>'

    prev = date(y, m, 1) - timedelta(days=1)
    nxt = date(y, m, cal.monthrange(y, m)[1]) + timedelta(days=1)
    solde = tr - tc
    body = f"""<div class="card">
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px">
<h2 style="margin:0">Journal de caisse — {MOIS[m-1]} {y}</h2>
<div style="margin-left:auto;display:flex;gap:6px">
<a href="/journal?y={prev.year}&m={prev.month}" class="tag">‹ {MOIS[prev.month-1][:4]}</a>
<a href="/journal?y={nxt.year}&m={nxt.month}" class="tag">{MOIS[nxt.month-1][:4]} ›</a></div></div>
<p class="hint">Recettes = acomptes en espèces avec numéro de caisse. Charges =
dépenses saisies sur la période.</p>
<div class="row" style="margin-bottom:16px">
<div class="fld"><label>Recettes</label>
<div style="font-size:21px;font-weight:700;color:var(--ok)">{_euro(tr)}</div></div>
<div class="fld"><label>Charges</label>
<div style="font-size:21px;font-weight:700;color:var(--ko)">{_euro(tc)}</div></div>
<div class="fld"><label>Solde</label>
<div style="font-size:21px;font-weight:700;
color:{'var(--ok)' if solde>=0 else 'var(--ko)'}">{_euro(solde)}</div></div></div>
<div class="row" style="align-items:flex-start">
<div style="flex:1 1 340px"><h2 style="font-size:13px">Recettes</h2>
<table><tr><th>Date</th><th>Désignation</th><th>Caisse</th>
<th style="text-align:right">Montant</th></tr>{lr}</table></div>
<div style="flex:1 1 300px"><h2 style="font-size:13px">Charges</h2>
<table><tr><th>Date</th><th>Désignation</th>
<th style="text-align:right">Montant</th></tr>{lc}</table></div></div></div>"""
    return page("/journal", body)


@app.route("/charges")
def charges():
    a, b = database.get_all_charges(), database.get_all_charges_omar()

    def bloc(titre, rows, hint):
        tot = sum(float(r["montant"]) for r in rows)
        lignes = "".join(f"""<tr><td>{r['date_encaissement']}</td>
<td>{r['designation']}</td><td style="text-align:right;font-weight:700">
{_euro(r['montant'])}</td></tr>""" for r in rows) or \
            '<tr><td colspan="3" class="empty">Aucune charge.</td></tr>'
        return f"""<div style="flex:1 1 330px"><h2 style="font-size:14px">{titre}</h2>
<p class="hint">{hint}</p>
<table><tr><th>Date</th><th>Désignation</th>
<th style="text-align:right">Montant</th></tr>{lignes}
<tr><td colspan="2" style="font-weight:700">Total</td>
<td style="text-align:right;font-weight:700;color:var(--ko)">{_euro(tot)}</td></tr>
</table></div>"""

    body = f"""<div class="card"><h2>Charges</h2>
<p class="hint">Deux caisses distinctes, comme dans l'application.</p>
<div class="row" style="align-items:flex-start">
{bloc('Caisse principale', a, 'Dépenses du complexe.')}
{bloc('Caisse Omar', b, 'Dépenses suivies séparément.')}
</div></div>"""
    return page("/charges", body)


@app.route("/employes")
def employes():
    emps = database.get_all_employees()
    if not emps:
        return page("/employes",
                    '<div class="card"><div class="empty">Aucun employé.</div></div>')
    lignes = ""
    for e in emps:
        fiche = database.get_employee_fiche_data(e["id"]) or {}
        du = fiche.get("total_du", 0) or 0
        paye = fiche.get("total_paye", 0) or 0
        reste = du - paye
        nb = len(fiche.get("pointages", []) or [])
        typ = (e.get("type_ouvrier") or "jour").lower()
        badge = ('<span class="tag vi">nuit</span>' if typ == "nuit"
                 else '<span class="tag">jour</span>')
        lignes += f"""<tr><td><b>{e['prenom']} {e['nom']}</b></td>
<td>{e.get('role') or ''}</td><td>{badge}</td>
<td style="text-align:right">{_euro(e.get('salaire_journalier'))}</td>
<td style="text-align:right">{_euro(e.get('prix_heure_supp'))}</td>
<td style="text-align:center">{nb}</td>
<td style="text-align:right">{_euro(du)}</td>
<td style="text-align:right">{_euro(paye)}</td>
<td style="text-align:right;font-weight:700;
color:{'var(--ok)' if reste<=0 else 'var(--wa)'}">{_euro(reste)}</td></tr>"""
    body = f"""<div class="card"><h2>Employés</h2>
<p class="hint">Tarifs, pointages comptabilisés et solde dû — calculés par
<code>database.get_employee_fiche_data()</code>, la même fonction que
l'application.</p>
<div style="overflow-x:auto"><table><tr><th>Employé</th><th>Poste</th><th>Type</th>
<th style="text-align:right">Salaire/jour</th><th style="text-align:right">H. supp</th>
<th style="text-align:center">Pointages</th><th style="text-align:right">Total dû</th>
<th style="text-align:right">Payé</th><th style="text-align:right">Reste</th></tr>
{lignes}</table></div></div>"""
    return page("/employes", body)


@app.route("/pointage")
def pointage():
    rows = database.get_all_pointage()
    emps = {e["id"]: e for e in database.get_all_employees()}
    if not rows:
        return page("/pointage",
                    '<div class="card"><div class="empty">Aucun pointage.</div></div>')
    label = {"midi": "Midi", "apres_midi": "Après-midi", "soiree": "Soirée",
             "journee_complete": "Journée complète"}
    lignes = ""
    for r in sorted(rows, key=lambda x: (x["date_pointage"], x["employee_id"]),
                    reverse=True):
        e = emps.get(r["employee_id"], {})
        per = label.get(r.get("periode") or "", r.get("periode") or "—")
        supp = float(r.get("heures_supplementaires") or 0)
        lignes += f"""<tr><td>{r['date_pointage']}</td>
<td><b>{e.get('prenom','')} {e.get('nom','')}</b><br>
<span style="color:var(--tm);font-size:11.5px">{e.get('role','')}</span></td>
<td><span class="tag">{per}</span></td>
<td>{r.get('heure_arrivee') or '—'} → {r.get('heure_depart') or '—'}</td>
<td style="text-align:right">{supp:.0f} h</td></tr>"""
    body = f"""<div class="card"><h2>Pointage</h2>
<p class="hint">{len(rows)} pointages enregistrés. Dans l'application, la saisie
se fait en trois étapes : type d'ouvrier, période, puis sélection des employés.</p>
<div style="overflow-x:auto"><table><tr><th>Date</th><th>Employé</th>
<th>Période</th><th>Horaires</th><th style="text-align:right">H. supp</th></tr>
{lignes}</table></div></div>"""
    return page("/pointage", body)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
