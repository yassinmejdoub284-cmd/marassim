# -*- coding: utf-8 -*-
"""
api/demo_data.py — Jeu de données FICTIF pour la démonstration web.

Aucune donnée client réelle : l'URL Vercel est publique. Les noms, téléphones
et numéros de CIN ci-dessous sont inventés.

La base est reconstruite dans /tmp à chaque démarrage d'instance — c'est le
seul emplacement inscriptible sur Vercel, et il est éphémère par nature.
"""
import os
from datetime import date, timedelta

DEMO_DB = "/tmp/marassim_demo.db"
os.environ.setdefault("MARASSIM_DB_BACKEND", "sqlite")
os.environ.setdefault("MARASSIM_DB_PATH", DEMO_DB)

CLIENTS = [
    ("Amine Chaabane", "06 12 34 56", "Mariage"),
    ("Sonia Trabelsi", "06 22 11 90", "Fiançailles"),
    ("Karim Bouzid", "06 44 78 12", "Anniversaire"),
    ("Leila Ben Ammar", "06 91 23 44", "Mariage"),
    ("Hatem Gharbi", "06 55 66 77", "Circoncision"),
    ("Nadia Zouari", "06 33 21 08", "Mariage"),
    ("Slim Mansour", "06 77 45 90", "Réception"),
    ("Rania Khelifi", "06 18 92 34", "Fiançailles"),
]

REGLES = [
    dict(nom="Almes — créneaux standard", salle="Almes", date_debut=None,
         date_fin=None, jours="", creneaux="15:00-18:00;21:00-01:00",
         pause_min_heures=3, heure_fin_max=None, sono_obligatoire=0,
         violon_gratuit=1, violon_debut_min="18:00", violon_fin_max="21:00",
         violon_duree_max=1, violon_pause_heures=1, priorite=0, actif=1,
         notes="Violoniste offert 1 h dans l'espace Rayhane."),
    dict(nom="Chichkhane — soirée 21h", salle="Chichkhane", date_debut=None,
         date_fin=None, jours="", creneaux="21:00-01:00", pause_min_heures=3,
         heure_fin_max=None, sono_obligatoire=0, violon_gratuit=1,
         violon_debut_min="18:00", violon_fin_max="21:00", violon_duree_max=1,
         violon_pause_heures=1, priorite=0, actif=1, notes="Violoniste offert."),
    dict(nom="Chichkhane — après-midi (sans violon)", salle="Chichkhane",
         date_debut=None, date_fin=None, jours="", creneaux="15:00-18:00",
         pause_min_heures=3, heure_fin_max=None, sono_obligatoire=0,
         violon_gratuit=0, violon_debut_min=None, violon_fin_max=None,
         violon_duree_max=None, violon_pause_heures=1, priorite=0, actif=1,
         notes="Pas d'heure de violoniste offerte sur ce créneau."),
    dict(nom="Rayhane — réception", salle="Rayhane", date_debut=None,
         date_fin=None, jours="", creneaux="", pause_min_heures=1,
         heure_fin_max="21:00", sono_obligatoire=1, violon_gratuit=0,
         violon_debut_min=None, violon_fin_max=None, violon_duree_max=None,
         violon_pause_heures=1, priorite=0, actif=1,
         notes="Horaires libres, fin 21 h au plus tard, sono obligatoire."),
]


def build():
    """(Re)construit la base de démonstration si elle n'existe pas."""
    if os.path.exists(DEMO_DB) and os.path.getsize(DEMO_DB) > 20000:
        return DEMO_DB

    import database
    database.init_db()

    conn = database.get_connection()
    conn.execute("DELETE FROM reservations")
    conn.execute("DELETE FROM reservation_rules")
    conn.commit()
    conn.close()

    for r in REGLES:
        database.insert_rule(r)

    base = date.today().replace(day=1)
    plan = [
        (2,  "Almes",      "15:00", "18:00", 0, None, None),
        (2,  "Almes",      "21:00", "01:00", 1, "18:00", "19:00"),
        (5,  "Chichkhane", "21:00", "01:00", 1, "19:30", "20:30"),
        (9,  "Almes",      "15:00", "18:00", 0, None, None),
        (12, "Rayhane",    "17:30", "20:45", 0, None, None),
        (16, "Chichkhane", "15:00", "18:00", 0, None, None),
        (19, "Almes",      "21:00", "01:00", 1, "18:00", "19:00"),
        (23, "Chichkhane", "21:00", "01:00", 0, None, None),
        (26, "Almes",      "15:00", "18:00", 0, None, None),
        (30, "Rayhane",    "16:00", "20:00", 0, None, None),
    ]
    for i, (jour, salle, hd, hf, viol, vd, vf) in enumerate(plan):
        nom, tel, typ = CLIENTS[i % len(CLIENTS)]
        try:
            d = base + timedelta(days=jour - 1)
        except Exception:
            continue
        forfait = 6000 + (i % 4) * 1000
        database.insert_reservation_with_bon({
            "salle": salle, "date_evenement": d.isoformat(),
            "heure_debut": hd, "heure_fin": hf,
            "type_evenement": typ, "nom_client": nom, "tel1": tel,
            "nb_places": 200 + i * 25, "forfait": float(forfait),
            "acompte1": float(forfait) * (0.3 if i % 3 else 1.0),
            "date_acompte1": d.isoformat(),
            "with_sono": 1 if salle == "Rayhane" else 0,
            "with_violoniste": viol,
            "violoniste_date": d.isoformat() if viol else None,
            "violoniste_heure_debut": vd, "violoniste_heure_fin": vf,
            "statut_paiement": "SOLDÉ" if i % 3 == 0 else None,
        }, prefix="BON")
    return DEMO_DB
