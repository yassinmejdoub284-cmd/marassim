"""
database.py — Couche d'accès aux données (SQLite) pour Marassim.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marassim.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    num_bon TEXT,
    salle TEXT NOT NULL,                 -- 'Almes' | 'Chichkhane' | 'Gazon'
    date_evenement TEXT NOT NULL,        -- 'YYYY-MM-DD'
    heure_debut TEXT NOT NULL,           -- 'HH:MM'
    heure_fin TEXT NOT NULL,             -- 'HH:MM' (peut être < heure_debut si ça dépasse minuit)
    type_evenement TEXT,
    nb_places INTEGER,
    forfait REAL,

    nom_client TEXT,
    cin TEXT,
    date_cin TEXT,
    tel1 TEXT,
    tel2 TEXT,

    lieu_contrat TEXT,
    date_contrat TEXT,
    heure_contrat TEXT,
    dossier_traite_par TEXT,

    with_violoniste INTEGER DEFAULT 0,
    violoniste_heure_debut TEXT,
    violoniste_heure_fin TEXT,

    with_sono INTEGER DEFAULT 0,

    acompte1 REAL, date_acompte1 TEXT, fn1 TEXT,
    acompte2 REAL, date_acompte2 TEXT, fn2 TEXT,
    acompte3 REAL, date_acompte3 TEXT, fn3 TEXT,

    statut_paiement TEXT,

    -- Champs additionnels du formulaire (v2)
    blocage_journee INTEGER DEFAULT 0,
    forfait_type TEXT,              -- 'Forfait' ou 'Extra'
    methode_paiement TEXT,          -- 'Espèce' | 'Chèque' | 'Virement' ...
    caisse TEXT,
    tresorerie TEXT,
    reste_acompte REAL,
    date_reste TEXT,
    details_extra TEXT,
    opt_espace_gazon INTEGER DEFAULT 0,
    opt_tourniquet INTEGER DEFAULT 0,
    opt_logiciel INTEGER DEFAULT 0,
    opt_invitations INTEGER DEFAULT 0,
    n_facture TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Colonnes ajoutées après la v1 : (nom, type SQL) — utilisées pour migrer
# une base marassim.db existante sans perdre les données.
_V2_COLUMNS = [
    ("blocage_journee", "INTEGER DEFAULT 0"),
    ("forfait_type", "TEXT"),
    ("methode_paiement", "TEXT"),
    ("caisse", "TEXT"),
    ("tresorerie", "TEXT"),
    ("reste_acompte", "REAL"),
    ("date_reste", "TEXT"),
    ("details_extra", "TEXT"),
    ("opt_espace_gazon", "INTEGER DEFAULT 0"),
    ("opt_tourniquet", "INTEGER DEFAULT 0"),
    ("opt_logiciel", "INTEGER DEFAULT 0"),
    ("opt_invitations", "INTEGER DEFAULT 0"),
    ("n_facture", "TEXT"),
    # Colonnes v3 — infos chèque/virement/effet
    ("num_cheque_virement", "TEXT"),
    ("banque", "TEXT"),
    ("date_cheque_virement", "TEXT"),
    # Colonnes v4 — signature et statut paiement explicite
    ("date_signature", "TEXT"),
    # Colonnes v5 — numéro de caisse par acompte (Caisse Tawfik)
    ("num_caisse1", "TEXT"),
    ("num_caisse2", "TEXT"),
    ("num_caisse3", "TEXT"),
    # Colonnes v9 — numéro caisse Omar par acompte
    ("num_caisse_omar1", "TEXT"),
    ("num_caisse_omar2", "TEXT"),
    ("num_caisse_omar3", "TEXT"),
    # Colonnes v6 — méthode par acompte (Espèce/Chèque/Virement/Effet)
    ("methode_acompte1", "TEXT"),
    ("methode_acompte2", "TEXT"),
    ("methode_acompte3", "TEXT"),
    # Colonnes v7 — date dédiée salle Rayhane pour l'option violoniste
    ("violoniste_date", "TEXT"),
    # Colonnes v8 — lieu de délivrance de la CIN
    ("lieu_cin", "TEXT"),
    # Colonnes v10 — statut réception Caisse Omar par slot (NULL | 'accepte' | 'refuse')
    ("omar_statut1", "TEXT"),
    ("omar_statut2", "TEXT"),
    ("omar_statut3", "TEXT"),
    # Colonnes v10 — date d'acceptation Omar par slot
    ("omar_date_accept1", "TEXT"),
    ("omar_date_accept2", "TEXT"),
    ("omar_date_accept3", "TEXT"),
    # Colonnes v11 — réservation temporaire
    ("is_temporaire", "INTEGER DEFAULT 0"),
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn):
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(reservations)")}
    for col_name, col_type in _V2_COLUMNS:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE reservations ADD COLUMN {col_name} {col_type}")
    # Employees table migrations
    emp_cols = {row["name"] for row in conn.execute("PRAGMA table_info(employees)")}
    if "type_ouvrier" not in emp_cols:
        conn.execute("ALTER TABLE employees ADD COLUMN type_ouvrier TEXT DEFAULT 'jour'")
    if "salaire_minimum" not in emp_cols:
        conn.execute("ALTER TABLE employees ADD COLUMN salaire_minimum REAL DEFAULT 0")
    conn.commit()


SCHEMA_CHARGES = """
CREATE TABLE IF NOT EXISTS charges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_encaissement TEXT NOT NULL,   -- 'YYYY-MM-DD'
    designation TEXT NOT NULL,
    montant REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_CHARGES_OMAR = """
CREATE TABLE IF NOT EXISTS charges_omar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_encaissement TEXT NOT NULL,   -- 'YYYY-MM-DD'
    designation TEXT NOT NULL,
    montant REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_RECETTES_OMAR_EXTRA = """
CREATE TABLE IF NOT EXISTS recettes_omar_extra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_recette TEXT NOT NULL,        -- 'YYYY-MM-DD'
    designation TEXT NOT NULL,
    montant REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_EMPLOYEES = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    role TEXT NOT NULL,
    icone TEXT,
    salaire_journalier REAL DEFAULT 0,
    prix_heure_supp REAL DEFAULT 0,
    salaire_midi REAL DEFAULT 0,
    salaire_apres_midi REAL DEFAULT 0,
    salaire_soiree REAL DEFAULT 0,
    salaire_minimum REAL DEFAULT 0,    -- applicable pour ouvrier de jour uniquement
    type_ouvrier TEXT DEFAULT 'jour',  -- 'jour' | 'nuit'
    actif INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_POINTAGE = """
CREATE TABLE IF NOT EXISTS pointage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    date_pointage TEXT NOT NULL,       -- 'YYYY-MM-DD'
    heure_arrivee TEXT,                -- 'HH:MM'
    heure_depart TEXT,                 -- 'HH:MM'
    heures_supplementaires REAL DEFAULT 0,
    periode TEXT,                      -- 'midi' | 'apres_midi' | 'soiree' | 'journee_complete'
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
"""

SCHEMA_PAIEMENT_EMPLOYEES = """
CREATE TABLE IF NOT EXISTS paiement_employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    date_paiement TEXT NOT NULL,       -- 'YYYY-MM-DD'
    periode_debut TEXT NOT NULL,       -- 'YYYY-MM-DD'
    periode_fin TEXT NOT NULL,         -- 'YYYY-MM-DD'
    montant_base REAL DEFAULT 0,
    montant_heures_supp REAL DEFAULT 0,
    montant_total REAL NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
"""


# ═══════════════════════════════════════════════════════════════════
#  RÈGLES DE RÉSERVATION (module "Règles")
# ═══════════════════════════════════════════════════════════════════
SCHEMA_RULES = """
CREATE TABLE IF NOT EXISTS reservation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    salle TEXT NOT NULL,               -- 'Almes' | 'Chichkhane' | 'Rayhane' | '*'
    date_debut TEXT,                   -- 'YYYY-MM-DD' ; NULL = pas de borne
    date_fin TEXT,                     -- 'YYYY-MM-DD' ; NULL = pas de borne
    jours TEXT,                        -- '0,1,2,3,4,5,6' (0=lundi) ; '' = tous
    creneaux TEXT,                     -- '15:00-18:00;21:00-01:00' ; '' = libre
    pause_min_heures REAL DEFAULT 0,   -- battement obligatoire même salle
    heure_fin_max TEXT,                -- 'HH:MM' ; NULL = pas de limite
    sono_obligatoire INTEGER DEFAULT 0,
    violon_gratuit INTEGER DEFAULT 0,  -- cette règle donne droit au violon offert
    violon_debut_min TEXT,             -- 'HH:MM' ; NULL = pas de borne
    violon_fin_max TEXT,               -- 'HH:MM' ; NULL = pas de borne
    violon_duree_max REAL,             -- heures ; NULL = pas de limite
    violon_pause_heures REAL DEFAULT 1,
    priorite INTEGER DEFAULT 0,        -- plus grand = évalué en premier
    actif INTEGER DEFAULT 1,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def insert_rule(data: dict) -> int:
    conn = get_connection()
    cols = list(data.keys())
    sql = (f"INSERT INTO reservation_rules ({','.join(cols)}) "
           f"VALUES ({','.join(['?'] * len(cols))})")
    cur = conn.execute(sql, [data[c] for c in cols])
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_rule(rule_id: int, data: dict):
    if not data:
        return
    conn = get_connection()
    sets = ", ".join(f"{k}=?" for k in data)
    conn.execute(f"UPDATE reservation_rules SET {sets} WHERE id=?",
                 list(data.values()) + [rule_id])
    conn.commit()
    conn.close()


def delete_rule(rule_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM reservation_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


def get_rule(rule_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM reservation_rules WHERE id=?",
                       (rule_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_rules(actif_only: bool = False):
    conn = get_connection()
    sql = "SELECT * FROM reservation_rules"
    if actif_only:
        sql += " WHERE actif=1"
    sql += " ORDER BY priorite DESC, salle, id"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_rules_for_salle(salle: str):
    """Règles actives applicables à une salle (y compris les règles '*')."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reservation_rules WHERE actif=1 AND (salle=? OR salle='*') "
        "ORDER BY priorite DESC, id DESC",
        (salle,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_violoniste_bookings(date_str: str):
    """Toutes les heures de violon réservées à une date (tous contrats confondus)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, num_bon, nom_client, salle, date_evenement, "
        "       violoniste_date, violoniste_heure_debut, violoniste_heure_fin "
        "FROM reservations "
        "WHERE with_violoniste=1 "
        "  AND COALESCE(violoniste_date, date_evenement)=? "
        "  AND violoniste_heure_debut IS NOT NULL "
        "  AND violoniste_heure_fin IS NOT NULL",
        (date_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def init_db():
    conn = get_connection()
    conn.execute(SCHEMA)
    conn.execute(SCHEMA_CHARGES)
    conn.execute(SCHEMA_CHARGES_OMAR)
    conn.execute(SCHEMA_RECETTES_OMAR_EXTRA)
    conn.execute(SCHEMA_EMPLOYEES)
    conn.execute(SCHEMA_POINTAGE)
    conn.execute(SCHEMA_PAIEMENT_EMPLOYEES)
    conn.execute(SCHEMA_RULES)
    conn.commit()
    _migrate(conn)
    conn.close()


def insert_reservation(data: dict) -> int:
    conn = get_connection()
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO reservations ({','.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [data[c] for c in cols])
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def delete_reservation(res_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM reservations WHERE id=?", (res_id,))
    conn.commit()
    conn.close()


def get_reservation(res_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM reservations WHERE id=?", (res_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_reservations(order_by="date_evenement"):
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM reservations ORDER BY {order_by}").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_reservations_for_date(date_str: str, salle: str = None):
    conn = get_connection()
    if salle:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE date_evenement=? AND salle=?",
            (date_str, salle),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE date_evenement=?", (date_str,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_reservations_in_range(start_date: str, end_date: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reservations WHERE date_evenement BETWEEN ? AND ? ORDER BY date_evenement",
        (start_date, end_date),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_reservations(query: str):
    """Recherche par tel1/tel2, cin, date_evenement, num_bon, n_facture."""
    conn = get_connection()
    q = f"%{query}%"
    rows = conn.execute(
        """SELECT * FROM reservations WHERE
           tel1 LIKE ? OR tel2 LIKE ? OR cin LIKE ? OR
           date_evenement LIKE ? OR num_bon LIKE ? OR n_facture LIKE ?
           ORDER BY date_evenement DESC""",
        (q, q, q, q, q, q),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_acompte(res_id: int, montant: float, methode: str,
                num_ref: str, banque: str, date_ref: str,
                num_caisse: str = "", num_caisse_omar: str = "") -> dict:
    """Ajoute un acompte dans le prochain slot libre (acompte1/2/3).
    - methode  : 'Espèce' | 'Chèque' | 'Virement' | 'Effet'
    - num_ref  : numéro de chèque/virement/effet (stocké dans fnN)
    - num_caisse : numéro de caisse (FN° sur le bon)
    Retourne la réservation mise à jour.
    """
    from datetime import date as _date
    conn = get_connection()
    row = conn.execute("SELECT * FROM reservations WHERE id=?", (res_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Réservation {res_id} introuvable.")
    res = dict(row)

    forfait = float(res.get("forfait") or 0)
    total = sum(float(res.get(f"acompte{i}") or 0) for i in range(1, 4))

    if forfait > 0 and total >= forfait:
        conn.close()
        raise ValueError("Le forfait est déjà intégralement payé.")

    if total + montant > forfait and forfait > 0:
        raise ValueError(
            f"Ce montant dépasse le forfait. Maximum autorisé : {forfait - total:.3f} DT."
        )

    slot = None
    for i in range(1, 4):
        if not res.get(f"acompte{i}"):
            slot = i
            break
    if slot is None:
        conn.close()
        raise ValueError("Les 3 slots d'acompte sont déjà utilisés.")

    today_iso = _date.today().isoformat()
    new_total = total + montant
    new_statut = None
    if forfait > 0 and abs(new_total - forfait) < 0.001:
        new_statut = f"SOLDE LE {_date.today().strftime('%d/%m/%Y')}"

    # fn = numéro de pièce (chèque/virement), methode_acompte = Espèce/Chèque/…
    conn.execute(
        f"UPDATE reservations SET acompte{slot}=?, date_acompte{slot}=?,"
        f" fn{slot}=?, methode_acompte{slot}=?, num_caisse{slot}=?,"
        f" num_caisse_omar{slot}=?, statut_paiement=? WHERE id=?",
        (montant, today_iso, num_ref or None, methode, num_caisse or None,
         num_caisse_omar or None, new_statut, res_id),
    )
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM reservations WHERE id=?", (res_id,)).fetchone())
    conn.close()
    return updated

# ---------------------------------------------------------------- Journal de caisse
def get_journal_caisse(start_date: str, end_date: str) -> dict:
    """Recettes = acomptes en ESPÈCES avec numéro de caisse Tawfik (num_caisseN renseigné)
    dont la date tombe dans la période.
    Dépenses = charges de la période.
    """
    from datetime import datetime as _dt
    conn = get_connection()

    recettes = []
    rows = conn.execute("SELECT * FROM reservations ORDER BY date_acompte1, date_acompte2, date_acompte3").fetchall()

    for r in rows:
        res = dict(r)
        # Dernier slot payé = celui qui a soldé (pour déterminer SOLDE vs ACOMPTE)
        last_paid_slot = max(
            (i for i in range(1, 4) if res.get(f"acompte{i}")),
            default=0,
        )
        statut_line = (res.get("statut_paiement") or "").upper()

        for slot in range(1, 4):
            d = res.get(f"date_acompte{slot}")
            montant = res.get(f"acompte{slot}")
            if not d or not montant:
                continue
            if not (start_date <= d <= end_date):
                continue

            # Filtrer espèces uniquement
            methode = (res.get(f"methode_acompte{slot}") or "").strip()
            # Fallback : si la colonne methode_acompte n'est pas encore remplie
            # (anciennes réservations), on regarde fn
            if not methode:
                methode = (res.get(f"fn{slot}") or "").strip()
            is_espece = methode.lower().startswith("esp") or methode == ""
            if not is_espece:
                continue

            # Filtrer Caisse Tawfik uniquement (num_caisseN renseigné)
            num_caisse_val = (res.get(f"num_caisse{slot}") or "").strip()
            if not num_caisse_val:
                continue

            # Préfixe SOLDE si c'est le dernier acompte ET que la réservation est soldée
            if slot == last_paid_slot and "SOLDE" in statut_line:
                prefix = "SOLDE"
            else:
                prefix = "ACOMPTE"

            salle = (res.get("salle") or "").upper()
            heure = res.get("heure_debut") or ""
            try:
                date_evt_fmt = _dt.strptime(res.get("date_evenement", ""), "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                date_evt_fmt = res.get("date_evenement", "")

            designation = (
                f"{prefix} {(res.get('nom_client') or '').upper()} "
                f"SOIREE {date_evt_fmt} {salle} {heure}"
            )
            fn = res.get(f"fn{slot}") or ""
            num_caisse = res.get(f"num_caisse{slot}") or ""

            recettes.append({
                "date": d,
                "designation": designation,
                "fn": fn,
                "num_caisse": num_caisse,
                "montant": float(montant),
                "res_id": res.get("id"),
                "slot": slot,
            })

    recettes.sort(key=lambda x: (x["date"], x["res_id"], x["slot"]))

    # Charges
    charges_rows = conn.execute(
        "SELECT * FROM charges WHERE date_encaissement BETWEEN ? AND ? ORDER BY date_encaissement",
        (start_date, end_date),
    ).fetchall()
    charges = []
    for c in charges_rows:
        try:
            d_fmt_display = _dt.strptime(c["date_encaissement"], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            d_fmt_display = c["date_encaissement"]
        charges.append({
            "date": c["date_encaissement"],
            "date_fmt": d_fmt_display,
            "designation": c["designation"],
            "montant": float(c["montant"]),
        })

    conn.close()
    return {"recettes": recettes, "charges": charges}


# ---------------------------------------------------------------- Journal de caisse Omar
def get_journal_caisse_omar(start_date: str, end_date: str) -> dict:
    """
    Recettes  = acomptes dont num_caisse_omarN est renseigné et dont la date
                tombe dans la période (= montant saisi dans 'Caisse Omar').
    Sorties   = charges_omar + paiements employés de la période.
    """
    from datetime import datetime as _dt
    conn = get_connection()

    # ── Recettes : champs num_caisse_omarN non vides ─────────────
    recettes = []
    rows = conn.execute(
        "SELECT * FROM reservations"
    ).fetchall()

    for r in rows:
        res = dict(r)
        last_paid_slot = max(
            (i for i in range(1, 4) if res.get(f"acompte{i}")),
            default=0,
        )
        statut_line = (res.get("statut_paiement") or "").upper()

        for slot in range(1, 4):
            num_caisse_omar = (res.get(f"num_caisse_omar{slot}") or "").strip()
            if not num_caisse_omar:
                continue
            # num_caisse_omar stores the amount the user typed in "Caisse Omar" field
            try:
                montant_omar = float(num_caisse_omar)
            except ValueError:
                continue  # not a numeric amount, skip
            if montant_omar <= 0:
                continue
            # N'inclure dans le journal QUE les acomptes acceptés par Omar
            omar_statut = (res.get(f"omar_statut{slot}") or "").strip()
            if omar_statut != "accepte":
                continue
            d = res.get(f"date_acompte{slot}")
            if not d:
                continue
            if not (start_date <= d <= end_date):
                continue

            if slot == last_paid_slot and "SOLDE" in statut_line:
                prefix = "SOLDE"
            else:
                prefix = "ACOMPTE"

            salle = (res.get("salle") or "").upper()
            heure = res.get("heure_debut") or ""
            try:
                date_evt_fmt = _dt.strptime(
                    res.get("date_evenement", ""), "%Y-%m-%d"
                ).strftime("%d/%m/%Y")
            except Exception:
                date_evt_fmt = res.get("date_evenement", "")

            designation = (
                f"{prefix} {(res.get('nom_client') or '').upper()} "
                f"SOIREE {date_evt_fmt} {salle} {heure}"
            )
            recettes.append({
                "date":            d,
                "designation":     designation,
                "num_caisse_omar": num_caisse_omar,
                "montant":         montant_omar,
            })

    recettes.sort(key=lambda x: x["date"])

    # ── Recettes manuelles (recettes_omar_extra) ──────────────────
    extra_rows = conn.execute(
        "SELECT * FROM recettes_omar_extra "
        "WHERE date_recette BETWEEN ? AND ? ORDER BY date_recette, id",
        (start_date, end_date),
    ).fetchall()
    for e in extra_rows:
        recettes.append({
            "date":            e["date_recette"],
            "designation":     e["designation"],
            "num_caisse_omar": "",
            "montant":         float(e["montant"]),
            "extra_id":        e["id"],
        })

    recettes.sort(key=lambda x: x["date"])

    # ── Sorties : charges Omar ────────────────────────────────────
    charges_rows = conn.execute(
        "SELECT * FROM charges_omar "
        "WHERE date_encaissement BETWEEN ? AND ? ORDER BY date_encaissement",
        (start_date, end_date),
    ).fetchall()
    sorties = []
    for c in charges_rows:
        try:
            d_fmt = _dt.strptime(c["date_encaissement"], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            d_fmt = c["date_encaissement"]
        sorties.append({
            "date":        c["date_encaissement"],
            "date_fmt":    d_fmt,
            "designation": c["designation"],
            "montant":     float(c["montant"]),
            "type":        "charge",
        })

    # ── Sorties : paiements employés (ouvriers de nuit uniquement) ──
    # Les ouvriers de jour sont payés sur une autre caisse — ne pas les inclure ici.
    pay_rows = conn.execute(
        "SELECT p.*, e.nom, e.prenom, e.type_ouvrier "
        "FROM paiement_employees p "
        "LEFT JOIN employees e ON p.employee_id = e.id "
        "WHERE p.date_paiement BETWEEN ? AND ? ORDER BY p.date_paiement",
        (start_date, end_date),
    ).fetchall()
    for p in pay_rows:
        p = dict(p)
        # Exclure les ouvriers de jour
        if (p.get("type_ouvrier") or "nuit") == "jour":
            continue
        try:
            d_fmt = _dt.strptime(p["date_paiement"], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            d_fmt = p["date_paiement"]
        nom_emp = f"{p.get('nom') or ''} {p.get('prenom') or ''}".strip()
        sorties.append({
            "date":        p["date_paiement"],
            "date_fmt":    d_fmt,
            "designation": f"PAIEMENT EMPLOYE — {nom_emp}",
            "montant":     float(p.get("montant_total") or 0),
            "type":        "employe",
        })

    sorties.sort(key=lambda x: x["date"])

    conn.close()
    return {"recettes": recettes, "sorties": sorties}

# ================================================================
#  CENTRE DE RÉCEPTION — acomptes Caisse Omar en attente / traités
# ================================================================

def get_acomptes_caisse_omar() -> list:
    """Retourne tous les slots d'acompte qui ont un montant Caisse Omar saisi,
    avec leur statut Omar (NULL=en attente, 'accepte', 'refuse').
    Chaque entrée est un dict plat représentant un slot individuel.
    """
    from datetime import datetime as _dt
    conn = get_connection()
    rows = conn.execute("SELECT * FROM reservations ORDER BY id DESC").fetchall()
    conn.close()

    result = []
    for r in rows:
        res = dict(r)
        for slot in range(1, 4):
            raw = (res.get(f"num_caisse_omar{slot}") or "").strip()
            if not raw:
                continue
            try:
                montant_omar = float(raw)
            except ValueError:
                continue
            if montant_omar <= 0:
                continue

            d_acompte = res.get(f"date_acompte{slot}") or ""
            try:
                d_fmt = _dt.strptime(d_acompte, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                d_fmt = d_acompte

            statut = (res.get(f"omar_statut{slot}") or "").strip() or "en_attente"
            date_accept = res.get(f"omar_date_accept{slot}") or ""
            try:
                date_accept_fmt = _dt.strptime(date_accept, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                date_accept_fmt = date_accept

            result.append({
                "res_id":           res["id"],
                "num_bon":          res.get("num_bon") or "",
                "nom_client":       res.get("nom_client") or "",
                "salle":            res.get("salle") or "",
                "date_evenement":   res.get("date_evenement") or "",
                "slot":             slot,
                "montant_omar":     montant_omar,
                "date_acompte":     d_acompte,
                "date_acompte_fmt": d_fmt,
                "methode":          (res.get(f"methode_acompte{slot}") or "").strip(),
                "statut":           statut,
                "date_accept":      date_accept,
                "date_accept_fmt":  date_accept_fmt,
            })

    return result


def update_omar_statut(res_id: int, slot: int, statut: str) -> None:
    """Met à jour le statut Omar d'un slot d'acompte.
    statut : 'accepte' | 'refuse' | None (remet en attente)
    Enregistre la date d'acceptation si statut == 'accepte'.
    """
    from datetime import date as _date
    if slot not in (1, 2, 3):
        raise ValueError(f"Slot invalide : {slot}")
    conn = get_connection()
    if statut == "accepte":
        date_accept = _date.today().isoformat()
        conn.execute(
            f"UPDATE reservations SET omar_statut{slot}=?, omar_date_accept{slot}=? WHERE id=?",
            (statut, date_accept, res_id),
        )
    else:
        conn.execute(
            f"UPDATE reservations SET omar_statut{slot}=?, omar_date_accept{slot}=NULL WHERE id=?",
            (statut if statut else None, res_id),
        )
    conn.commit()
    conn.close()


def insert_charge(date_encaissement: str, designation: str, montant: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO charges (date_encaissement, designation, montant) VALUES (?, ?, ?)",
        (date_encaissement, designation, montant),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_all_charges(order_by="date_encaissement DESC"):
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM charges ORDER BY {order_by}").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_charge(charge_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM charges WHERE id=?", (charge_id,))
    conn.commit()
    conn.close()


# ================================================================
#  CHARGES OMAR — Gestion des charges (caisse Omar)
# ================================================================
def insert_charge_omar(date_encaissement: str, designation: str, montant: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO charges_omar (date_encaissement, designation, montant) VALUES (?, ?, ?)",
        (date_encaissement, designation, montant),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_all_charges_omar(order_by="date_encaissement DESC"):
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM charges_omar ORDER BY {order_by}").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_charge_omar(charge_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM charges_omar WHERE id=?", (charge_id,))
    conn.commit()
    conn.close()


# ================================================================
#  RECETTES OMAR EXTRA — recettes manuelles (caisse Omar)
# ================================================================
def insert_recette_omar_extra(date_recette: str, designation: str, montant: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO recettes_omar_extra (date_recette, designation, montant) VALUES (?, ?, ?)",
        (date_recette, designation, montant),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_recettes_omar_extra(start_date: str, end_date: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recettes_omar_extra "
        "WHERE date_recette BETWEEN ? AND ? ORDER BY date_recette, id",
        (start_date, end_date),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_recette_omar_extra(rec_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM recettes_omar_extra WHERE id=?", (rec_id,))
    conn.commit()
    conn.close()
def insert_employee(data: dict) -> int:
    """Ajoute un nouvel employé."""
    conn = get_connection()
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO employees ({','.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [data[c] for c in cols])
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_all_employees(actif_only=True):
    """Récupère tous les employés."""
    conn = get_connection()
    if actif_only:
        rows = conn.execute("SELECT * FROM employees WHERE actif=1 ORDER BY nom, prenom").fetchall()
    else:
        rows = conn.execute("SELECT * FROM employees ORDER BY nom, prenom").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_employee(emp_id: int):
    """Récupère un employé par son ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_employee(emp_id: int, data: dict):
    """Met à jour un employé."""
    conn = get_connection()
    sets = ", ".join(f"{k}=?" for k in data)
    conn.execute(f"UPDATE employees SET {sets} WHERE id=?", list(data.values()) + [emp_id])
    conn.commit()
    conn.close()


def delete_employee(emp_id: int):
    """Désactive un employé (soft delete)."""
    conn = get_connection()
    conn.execute("UPDATE employees SET actif=0 WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()


# ================================================================
#  POINTAGE — Gestion de la présence
# ================================================================
def insert_pointage(data: dict) -> int:
    """Ajoute un pointage."""
    conn = get_connection()
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO pointage ({','.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [data[c] for c in cols])
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_pointage_by_employee(emp_id: int, start_date: str = None, end_date: str = None):
    """Récupère les pointages d'un employé."""
    conn = get_connection()
    if start_date and end_date:
        rows = conn.execute(
            "SELECT * FROM pointage WHERE employee_id=? AND date_pointage BETWEEN ? AND ? ORDER BY date_pointage DESC",
            (emp_id, start_date, end_date)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM pointage WHERE employee_id=? ORDER BY date_pointage DESC",
            (emp_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_pointage(date_str: str = None):
    """Récupère tous les pointages (optionnel: pour une date spécifique)."""
    conn = get_connection()
    if date_str:
        rows = conn.execute(
            "SELECT p.*, e.nom, e.prenom, e.type_ouvrier "
            "FROM pointage p LEFT JOIN employees e ON p.employee_id=e.id "
            "WHERE p.date_pointage=? ORDER BY e.nom",
            (date_str,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, e.nom, e.prenom, e.type_ouvrier "
            "FROM pointage p LEFT JOIN employees e ON p.employee_id=e.id "
            "ORDER BY p.date_pointage DESC LIMIT 100"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ================================================================
#  PAIEMENT EMPLOYEES — Gestion des paiements
# ================================================================
def insert_paiement_employee(data: dict) -> int:
    """Ajoute un paiement employé."""
    conn = get_connection()
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO paiement_employees ({','.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [data[c] for c in cols])
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_paiements_by_employee(emp_id: int):
    """Récupère les paiements d'un employé."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM paiement_employees WHERE employee_id=? ORDER BY date_paiement DESC",
        (emp_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_paiements_employees():
    """Récupère tous les paiements des employés."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT p.*, e.nom, e.prenom FROM paiement_employees p LEFT JOIN employees e ON p.employee_id=e.id ORDER BY p.date_paiement DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ================================================================
#  FICHE EMPLOYÉ — données complètes pour la fiche individuelle
# ================================================================
def get_employee_fiche_data(emp_id: int) -> dict:
    """
    Retourne un dict avec :
      - employee   : dict de l'employé
      - pointages  : liste de pointages triés par date ASC
      - paiements  : liste des paiements enregistrés
      - total_du   : somme des tarifs de tous les pointages
      - total_paye : somme de tous les paiements
      - reste      : total_du - total_paye
    """
    conn = get_connection()

    emp_row = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not emp_row:
        conn.close()
        return {}
    emp = dict(emp_row)

    # Tarifs selon la période
    TAR = {
        "midi":             float(emp.get("salaire_midi")       or 0),
        "apres_midi":       float(emp.get("salaire_apres_midi") or 0),
        "soiree":           float(emp.get("salaire_soiree")     or 0),
        "journee_complete": float(emp.get("salaire_journalier") or 0),
    }

    pointage_rows = conn.execute(
        "SELECT * FROM pointage WHERE employee_id=? ORDER BY date_pointage ASC, periode ASC",
        (emp_id,)
    ).fetchall()
    pointages = []
    total_du = 0.0
    for r in pointage_rows:
        p     = dict(r)
        tarif = TAR.get(p.get("periode") or "", 0.0)
        hs    = float(p.get("heures_supplementaires") or 0)
        hs_amt = hs * float(emp.get("prix_heure_supp") or 0)
        p["tarif"]  = tarif + hs_amt
        p["hs_amt"] = hs_amt
        total_du   += tarif + hs_amt
        pointages.append(p)

    paiement_rows = conn.execute(
        "SELECT * FROM paiement_employees WHERE employee_id=? ORDER BY date_paiement ASC",
        (emp_id,)
    ).fetchall()
    paiements = [dict(r) for r in paiement_rows]
    total_paye = sum(float(p.get("montant_total") or 0) for p in paiements)

    conn.close()
    return {
        "employee": emp,
        "pointages": pointages,
        "paiements": paiements,
        "total_du":   total_du,
        "total_paye": total_paye,
        "reste":      total_du - total_paye,
    }
