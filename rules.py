"""
rules.py — Moteur de règles de réservation du complexe Marassim.

Depuis la v12, les règles sont SAISIES PAR L'UTILISATEUR dans le module
« Règles de réservation » (table `reservation_rules`). Une règle décrit,
pour une salle + une période + des jours de semaine :
  - les créneaux horaires autorisés,
  - la pause minimale entre deux réservations de la même salle,
  - l'heure de fin maximale,
  - le droit à l'heure de violoniste offerte et sa fenêtre horaire.
Toute réservation qui sort de la règle applicable est un CONFLIT.

Si aucune règle n'est saisie pour une salle/date, on retombe sur les
constantes historiques ci-dessous (comportement d'origine).

⚠️ Certaines règles décrites par le client contiennent des zones d'ombre.
Les hypothèses prises sont signalées par des commentaires "HYPOTHÈSE:".
Si une règle ne correspond pas à la réalité du complexe, modifie les
constantes / fonctions ci-dessous — tout le reste de l'application
(gui.py, database.py) appelle uniquement `validate_reservation()`.
"""
from datetime import datetime, timedelta
import re

SALLES = ["Almes", "Chichkhane", "Rayhane"]

# Couleurs signature de chaque salle (utilisées dans excel_export.py ET gui.py)
# Format hexadécimal SANS # pour openpyxl (utilisé tel quel) ; gui.py ajoute le #.
SALLE_COLORS = {
    "Almes": "5B9BD5",       # bleu
    "Chichkhane": "ED7D7D",  # rouge / rose
    "Rayhane": "8FD19E",     # vert (espace gazon Rayhane)
}

SALLE_INITIALES = {"Almes": "A", "Chichkhane": "C", "Rayhane": "R"}

# Les horaires sont libres par défaut. Une règle peut restreindre les créneaux.
SALLE_SLOTS = []

# Pause obligatoire entre deux réservations de la MÊME salle (heures)
PAUSE_SALLE_HEURES = 3

# Pause obligatoire entre deux réservations de l'option Violoniste / Gazon (heures)
PAUSE_GAZON_HEURES = 1

# Heure de fin max pour l'option violoniste (espace Rayhane)
VIOLONISTE_HEURE_FIN_MAX = "21:00"

# Heure de fin max pour une réception organisée directement dans l'espace gazon
GAZON_RECEPTION_HEURE_FIN_MAX = "21:00"

# Jours interdits pour l'option violoniste quand elle nécessite la sono (0=lundi ... 6=dimanche)
JOURS_INTERDITS_VIOLONISTE_AVEC_SONO = {5, 6}  # samedi, dimanche

# Fenêtre bloquée sur Almes/Chichkhane le jour où le Gazon est réservé en réception principale
GAZON_BLOCK_WINDOW = ("18:00", "21:00")


def _to_minutes(hhmm: str) -> int:
    if not isinstance(hhmm, str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', hhmm):
        raise ValueError('Heure invalide : utilisez HH:MM.')
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _interval_minutes(start: str, end: str):
    """Retourne (début, fin) en minutes depuis 00:00, en gérant le passage minuit
    (ex: 21:00-01:00 -> fin = 25:00 en minutes équivalentes)."""
    s = _to_minutes(start)
    e = _to_minutes(end)
    if e <= s:
        e += 24 * 60
    return s, e


def _overlaps(startA, endA, startB, endB, pause_minutes=0):
    """True si [A] et [B] se chevauchent, en exigeant en plus `pause_minutes`
    de battement entre les deux (donc deux créneaux collés sans pause
    suffisante sont aussi considérés en conflit)."""
    aS, aE = _interval_minutes(startA, endA)
    bS, bE = _interval_minutes(startB, endB)
    aE += pause_minutes
    bE += pause_minutes
    return aS < bE and bS < aE


def check_salle_slot_conflict(db, salle, date_evenement, heure_debut, heure_fin, exclude_id=None, pause_hours=None):
    """Vérifie la salle et sa pause, y compris autour d'un passage de minuit."""
    from database import get_reservations_for_date

    if pause_hours is None:
        rule = find_matching_rule(salle, date_evenement, heure_debut, heure_fin)
        pause_hours = rule.get('pause_min_heures') if rule else PAUSE_SALLE_HEURES
    pause = max(2, min(3, float(pause_hours or PAUSE_SALLE_HEURES)))
    start, end = _interval_minutes(heure_debut, heure_fin)
    event_day = datetime.strptime(date_evenement, '%Y-%m-%d')
    for offset in (-1, 0, 1):
        existing_day = (event_day + timedelta(days=offset)).strftime('%Y-%m-%d')
        for res in get_reservations_for_date(existing_day, salle):
            if exclude_id and res['id'] == exclude_id:
                continue
            old_start, old_end = _interval_minutes(res['heure_debut'], res['heure_fin'])
            old_start += offset * 1440
            old_end += offset * 1440
            old_rule = find_matching_rule(salle, existing_day, res['heure_debut'], res['heure_fin'])
            old_pause = max(2, min(3, float(old_rule.get('pause_min_heures') or 3))) if old_rule else PAUSE_SALLE_HEURES
            effective_pause = max(pause, old_pause)
            if start < old_end and old_start < end:
                return False, (f"Conflit : la salle {salle} est déjà réservée le "
                               f"{existing_day} de {res['heure_debut']} à {res['heure_fin']}.")
            if start < old_end + int(effective_pause * 60) and old_start < end + int(effective_pause * 60):
                return False, (f"Conflit : il faut au moins {effective_pause:g}h de pause "
                               f"entre deux réservations de {salle} (réservation existante "
                               f"{res['heure_debut']}-{res['heure_fin']} le {existing_day}).")
    return True, ""


def is_eligible_for_free_violoniste(salle, slot):
    """Toutes les réservations sont éligibles à l'heure gratuite de violoniste
    SAUF les contrats Chichkhane du créneau 15h-18h."""
    if salle == "Chichkhane" and slot == "15:00-18:00":
        return False
    return True


def check_violoniste_slot(db, date_evenement, heure_debut, heure_fin, with_sono,
                           exclude_id=None):
    """Valide un créneau d'option violoniste dans l'espace Gazon/Rayhane :
    - doit se terminer au plus tard à 21h00
    - l'espace Gazon doit être libre à cette heure (avec 1h de pause exigée
      entre deux passages)
    - si l'option nécessite la sono, elle est interdite samedi et dimanche
      (HYPOTHÈSE sur la phrase "si condition de sono ... sauf samedi et dimanche")
    """
    s, e = _interval_minutes(heure_debut, heure_fin)
    max_e = _to_minutes(VIOLONISTE_HEURE_FIN_MAX)
    if e > max_e:
        return False, f"L'option violoniste doit se terminer au plus tard à {VIOLONISTE_HEURE_FIN_MAX}."

    d = datetime.strptime(date_evenement, "%Y-%m-%d")
    if d.weekday() in JOURS_INTERDITS_VIOLONISTE_AVEC_SONO:
        return False, "L'heure de violoniste offerte n'est pas disponible le samedi ni le dimanche."

    from database import get_reservations_for_date
    existing_gazon = get_reservations_for_date(date_evenement, "Rayhane")
    for res in existing_gazon:
        if exclude_id and res["id"] == exclude_id:
            continue
        if _overlaps(heure_debut, heure_fin, res["heure_debut"], res["heure_fin"],
                     pause_minutes=PAUSE_GAZON_HEURES * 60):
            return False, (f"L'espace Gazon (Rayhane) n'est pas libre à cette heure "
                            f"(pause de {PAUSE_GAZON_HEURES}h requise ; réservation existante "
                            f"{res['heure_debut']}-{res['heure_fin']}).")
    return True, ""


def check_gazon_reception(db, date_evenement, heure_debut, heure_fin, with_sono,
                           exclude_id=None):
    """Valide la disponibilité de Rayhane avec la même pause que les salles."""
    return check_salle_slot_conflict(db, 'Rayhane', date_evenement, heure_debut, heure_fin, exclude_id)


def check_salle_blocked_by_gazon_reception(db, salle, date_evenement, heure_debut, heure_fin,
                                            exclude_id=None):
    """Si une réception Gazon existe déjà ce jour-là, interdit toute réservation
    Almes/Chichkhane qui chevauche 18h-21h."""
    from database import get_reservations_for_date
    gazon_events = get_reservations_for_date(date_evenement, "Rayhane")
    has_gazon_reception = any(
        (g.get("type_evenement") or "").lower() == "reception" for g in gazon_events
    )
    if not has_gazon_reception:
        return True, ""
    if _overlaps(heure_debut, heure_fin, GAZON_BLOCK_WINDOW[0], GAZON_BLOCK_WINDOW[1],
                 pause_minutes=0):
        return False, (f"Impossible : une réception est déjà organisée dans l'espace Gazon "
                        f"ce {date_evenement}, ce qui bloque {salle} sur "
                        f"{GAZON_BLOCK_WINDOW[0]}-{GAZON_BLOCK_WINDOW[1]}.")
    return True, ""


def validate_reservation(res: dict, exclude_id=None, complexe=False):
    """Point d'entrée unique de validation. `res` est un dict avec au minimum :
    salle, date_evenement, heure_debut, heure_fin, type_evenement,
    with_violoniste, violoniste_heure_debut, violoniste_heure_fin, with_sono.

    Si `complexe=True`, la réservation fait partie d'une réservation
    "Toute la complexe" (toutes les salles) : les contraintes de créneaux
    fixes, de gazon et de fenêtre bloquée ne s'appliquent pas — seule la
    vérification de conflit (salle déjà occupée) est effectuée.

    Retourne (ok: bool, message: str).
    """
    salle = res["salle"]
    date_evenement = res["date_evenement"]
    heure_debut = res["heure_debut"]
    heure_fin = res["heure_fin"]

    try:
        start, end = _interval_minutes(heure_debut, heure_fin)
    except (ValueError, AttributeError):
        return False, 'Heures invalides : utilisez HH:MM.'
    if not 0 <= start < 1440 or not start < end <= start + 1440 or heure_debut == heure_fin:
        return False, 'Créneau horaire invalide.'
    if res.get('with_violoniste'):
        if salle == 'Rayhane' or not is_eligible_for_free_violoniste(salle, f'{heure_debut}-{heure_fin}'):
            return False, "L'heure de violoniste offerte n'est pas incluse pour Chichkhane de 15h à 18h ni pour un contrat Rayhane."
        v_debut, v_fin = res.get('violoniste_heure_debut'), res.get('violoniste_heure_fin')
        if not v_debut or not v_fin:
            return False, "Précise l'heure de début et de fin du violoniste."
        try:
            vs, ve = _interval_minutes(v_debut, v_fin)
            v_date = datetime.strptime(res.get('violoniste_date') or date_evenement, '%Y-%m-%d')
        except (ValueError, TypeError):
            return False, 'Date ou heures du violoniste invalides.'
        if not 0 <= vs < 1440 or ve - vs != 60 or ve > _to_minutes(VIOLONISTE_HEURE_FIN_MAX):
            return False, "L'heure offerte à Rayhane doit durer exactement une heure et finir au plus tard à 21h."
        if v_date.weekday() in (5, 6):
            return False, "L'heure de violoniste offerte n'est pas disponible le samedi ni le dimanche."

    if salle not in SALLES:
        return False, f"Salle inconnue : {salle}"

    # ── Règle saisie par l'utilisateur (module « Règles de réservation ») ──
    # Si une règle couvre cette salle + cette date, elle fait autorité :
    # toute réservation qui en sort est un conflit.
    if not complexe:
        rule = find_matching_rule(salle, date_evenement, heure_debut, heure_fin)
        if rule:
            return _validate_with_rule(rule, res, exclude_id)

    if complexe:
        # Toute la complexe : on vérifie uniquement les conflits de disponibilité
        ok, msg = check_salle_slot_conflict(None, salle, date_evenement, heure_debut, heure_fin,
                                             exclude_id)
        if not ok:
            return ok, msg
        if res.get('with_violoniste'):
            return check_violoniste_conflicts(res.get('violoniste_date') or date_evenement,
                                              v_debut, v_fin, exclude_id=exclude_id)
        return True, "OK"

    if salle in ("Almes", "Chichkhane"):
        ok, msg = check_salle_slot_conflict(None, salle, date_evenement, heure_debut, heure_fin,
                                             exclude_id)
        if not ok:
            return ok, msg

    elif salle == "Rayhane":
        ok, msg = check_gazon_reception(None, date_evenement, heure_debut, heure_fin,
                                         res.get("with_sono", 0), exclude_id)
        if not ok:
            return ok, msg

    # Option violoniste (facultative, s'ajoute à une réservation Almes/Chichkhane)
    if res.get("with_violoniste"):
        v_date = res.get("violoniste_date") or date_evenement
        ok, msg = check_violoniste_conflicts(v_date, v_debut, v_fin,
                                             exclude_id=exclude_id)
        if not ok:
            return ok, msg

    return True, "OK"


# ═══════════════════════════════════════════════════════════════════
#  MOTEUR DE RÈGLES CONFIGURABLES (table reservation_rules)
# ═══════════════════════════════════════════════════════════════════
JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def parse_creneaux(txt):
    """'15:00-18:00;21:00-01:00' -> [('15:00','18:00'), ('21:00','01:00')]"""
    out = []
    for part in (txt or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part or "-" not in part:
            continue
        a, b = part.split("-", 1)
        out.append((a.strip(), b.strip()))
    return out


def format_creneaux(pairs):
    return ";".join(f"{a}-{b}" for a, b in pairs)


def parse_jours(txt):
    """'0,5,6' -> {0,5,6} ; '' ou None -> tous les jours."""
    if not txt or not str(txt).strip():
        return set(range(7))
    out = set()
    for part in str(txt).replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit() and 0 <= int(part) <= 6:
            out.add(int(part))
    return out or set(range(7))


def format_jours(days):
    return ",".join(str(d) for d in sorted(days))


def jours_label(txt):
    days = parse_jours(txt)
    if days == set(range(7)):
        return "Tous"
    return ", ".join(JOURS_FR[d][:3] for d in sorted(days))


def rule_applies(rule, salle, date_evenement):
    """La règle couvre-t-elle cette salle et cette date ?"""
    if rule.get("salle") not in (salle, "*"):
        return False
    if rule.get("date_debut") and date_evenement < rule["date_debut"]:
        return False
    if rule.get("date_fin") and date_evenement > rule["date_fin"]:
        return False
    d = datetime.strptime(date_evenement, "%Y-%m-%d")
    return d.weekday() in parse_jours(rule.get("jours"))


def find_matching_rule(salle, date_evenement, heure_debut=None, heure_fin=None):
    """Retourne la règle active applicable à (salle, date[, créneau]), ou None.

    Sélection en deux temps :

    1. On garde les règles actives dont la salle, la période et le jour de
       semaine couvrent la réservation.
    2. Si le créneau demandé est connu, on privilégie les règles qui
       l'autorisent (liste de créneaux le contenant, ou horaires libres).
       Cela permet d'écrire une règle par créneau — p.ex. « Chichkhane
       15h-18h : pas de violon » et « Chichkhane 21h-01h : violon offert ».
       Si AUCUNE règle n'autorise le créneau, on retient quand même la plus
       pertinente afin de renvoyer un refus explicite « hors créneau ».

    Départage : priorité décroissante, puis règle avec créneaux explicites
    avant règle à horaires libres, puis salle précise avant '*', puis la
    plus récente.
    """
    from database import get_rules_for_salle
    try:
        candidates = get_rules_for_salle(salle)
    except Exception:
        return None
    matching = [r for r in candidates if rule_applies(r, salle, date_evenement)]
    if not matching:
        return None

    def _key(r):
        return (int(r.get("priorite") or 0),
                1 if parse_creneaux(r.get("creneaux")) else 0,
                1 if r.get("salle") != "*" else 0,
                int(r.get("id") or 0))

    if heure_debut and heure_fin:
        autorisent = []
        for r in matching:
            cr = parse_creneaux(r.get("creneaux"))
            if not cr or (heure_debut, heure_fin) in cr:
                autorisent.append(r)
        if autorisent:
            matching = autorisent

    matching.sort(key=_key, reverse=True)
    return matching[0]


def describe_rule(rule):
    """Résumé lisible d'une règle, pour l'UI et les messages de conflit."""
    if not rule:
        return "Aucune règle (comportement par défaut)"
    bits = [f"« {rule['nom']} »", rule["salle"] if rule["salle"] != "*" else "Toutes salles"]
    if rule.get("date_debut") or rule.get("date_fin"):
        bits.append(f"{rule.get('date_debut') or '…'} → {rule.get('date_fin') or '…'}")
    bits.append(f"jours : {jours_label(rule.get('jours'))}")
    cr = parse_creneaux(rule.get("creneaux"))
    bits.append("créneaux : " + (", ".join(f"{a}-{b}" for a, b in cr) if cr else "libres"))
    if rule.get("pause_min_heures"):
        bits.append(f"pause {rule['pause_min_heures']}h")
    if rule.get("heure_fin_max"):
        bits.append(f"fin ≤ {rule['heure_fin_max']}")
    if rule.get("violon_debut_min") or rule.get("violon_fin_max"):
        w = f"{rule.get('violon_debut_min') or '…'}–{rule.get('violon_fin_max') or '…'}"
        bits.append(f"fenêtre du violon ({w})")
    return " | ".join(bits)


def check_violoniste_conflicts(date_str, heure_debut, heure_fin,
                               pause_heures=PAUSE_GAZON_HEURES, exclude_id=None):
    """Vérifie que le créneau de violon demandé est libre dans l'espace Rayhane.

    Contrôle DEUX sources (l'ancienne version n'en contrôlait qu'une, ce qui
    laissait passer deux violons au même moment) :
      1. les réservations principales de la salle Rayhane,
      2. les heures de violon déjà accordées à d'autres contrats.
    """
    from database import get_reservations_for_date, get_violoniste_bookings
    pause = int(pause_heures * 60)

    for res in get_reservations_for_date(date_str, "Rayhane"):
        if exclude_id and res["id"] == exclude_id:
            continue
        if _overlaps(heure_debut, heure_fin, res["heure_debut"], res["heure_fin"],
                     pause_minutes=pause):
            return False, (f"Espace Rayhane occupé le {date_str} de "
                           f"{res['heure_debut']} à {res['heure_fin']} "
                           f"(pause de {pause_heures}h requise).")

    for v in get_violoniste_bookings(date_str):
        if exclude_id and v["id"] == exclude_id:
            continue
        if _overlaps(heure_debut, heure_fin,
                     v["violoniste_heure_debut"], v["violoniste_heure_fin"],
                     pause_minutes=pause):
            return False, (f"Heure de violoniste déjà accordée le {date_str} de "
                           f"{v['violoniste_heure_debut']} à {v['violoniste_heure_fin']} "
                           f"(contrat {v.get('num_bon') or '#' + str(v['id'])} — "
                           f"{v.get('nom_client') or 'client'}).")
    return True, ""


def _validate_with_rule(rule, res, exclude_id=None):
    """Valide une réservation contre une règle saisie par l'utilisateur.
    Tout ce qui dépasse la règle = conflit."""
    salle = res["salle"]
    date_evenement = res["date_evenement"]
    heure_debut = res["heure_debut"]
    heure_fin = res["heure_fin"]
    prefix = f"Règle « {rule['nom']} » : "

    # ── Créneaux autorisés ────────────────────────────────────────
    creneaux = parse_creneaux(rule.get("creneaux"))
    if creneaux:
        if (heure_debut, heure_fin) not in creneaux:
            libelles = ", ".join(f"{a}-{b}" for a, b in creneaux)
            return False, (prefix + f"{salle} n'est réservable que sur les créneaux "
                                    f"{libelles}. Créneau demandé : {heure_debut}-{heure_fin}.")

    # ── Heure de fin maximale ─────────────────────────────────────
    if rule.get("heure_fin_max"):
        _, e = _interval_minutes(heure_debut, heure_fin)
        if e > _to_minutes(rule["heure_fin_max"]):
            return False, (prefix + f"la réservation doit se terminer au plus tard "
                                    f"à {rule['heure_fin_max']} (demandé : {heure_fin}).")

    # ── Sono obligatoire ──────────────────────────────────────────
    if rule.get("sono_obligatoire") and not res.get("with_sono"):
        return False, prefix + "la sono est obligatoire pour cette réservation."

    # ── Pause minimale entre deux réservations de la même salle ───
    ok, message = check_salle_slot_conflict(None, salle, date_evenement, heure_debut, heure_fin,
                                             exclude_id, rule.get('pause_min_heures'))
    if not ok:
        return False, prefix + message

    # ── Heure de violoniste offerte ───────────────────────────────
    if res.get("with_violoniste"):
        v_debut = res.get("violoniste_heure_debut")
        v_fin = res.get("violoniste_heure_fin")
        if not v_debut or not v_fin:
            return False, "Précise l'heure de début et de fin du violoniste."
        v_date = res.get("violoniste_date") or date_evenement

        vs, ve = _interval_minutes(v_debut, v_fin)
        if rule.get("violon_debut_min") and vs < _to_minutes(rule["violon_debut_min"]):
            return False, (prefix + f"le violoniste ne peut pas commencer avant "
                                    f"{rule['violon_debut_min']}.")
        if rule.get("violon_fin_max") and ve > _to_minutes(rule["violon_fin_max"]):
            return False, (prefix + f"le violoniste doit se terminer au plus tard à "
                                    f"{rule['violon_fin_max']}.")
        if rule.get("violon_duree_max"):
            if (ve - vs) > float(rule["violon_duree_max"]) * 60:
                return False, (prefix + f"le violoniste offert est limité à "
                                        f"{rule['violon_duree_max']}h.")
        ok, msg = check_violoniste_conflicts(
            v_date, v_debut, v_fin,
            pause_heures=float(rule.get("violon_pause_heures") or 0),
            exclude_id=exclude_id)
        if not ok:
            return False, msg

    return True, "OK"
