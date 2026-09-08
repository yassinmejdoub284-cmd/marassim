# -*- coding: utf-8 -*-
"""
rules_tab.py — Module « Règles de réservation ».

L'utilisateur saisit ici les conditions de réservation (salle, période, jours,
créneaux horaires, pause, heure de fin max, heure de violoniste offerte).
Toute réservation qui sort de la règle applicable est refusée comme conflit.

Interface construite sur ui_kit — aucun import de gui.py (pas de cycle),
aucune dépendance externe : l'application reste 100 % hors ligne.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import database
import rules as rules_mod
import ui_kit as UI
from ui_kit import T, F, Button, Entry, Card, Chip, Switch, toast

SALLE_CHOICES = [("Almes", "Almes"), ("Chichkhane", "Chichkhane"),
                 ("Rayhane", "Rayhane"), ("*", "Toutes les salles")]
SALLE_LABEL = dict(SALLE_CHOICES)
SALLE_TONE = {"Almes": T["salle_almes"], "Chichkhane": T["salle_chichkhane"],
              "Rayhane": T["salle_rayhane"], "*": T["text_m"]}


# ═══════════════════════════════════════════════════════════════════
#  CONVERSIONS & VALIDATION
# ═══════════════════════════════════════════════════════════════════
def _iso(ddmmyyyy):
    t = (ddmmyyyy or "").strip()
    if not t:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Date invalide : {t} (format attendu JJ/MM/AAAA)")


def _fr(iso):
    if not iso:
        return ""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _hhmm(txt, champ):
    t = (txt or "").strip()
    if not t:
        return None
    try:
        h, m = t.split(":")
        h, m = int(h), int(m)
        assert 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        raise ValueError(f"{champ} : heure invalide « {t} » (format HH:MM)")
    return f"{h:02d}:{m:02d}"


def _num(txt, champ, default=None):
    t = (txt or "").strip().replace(",", ".")
    if not t:
        return default
    try:
        return float(t)
    except ValueError:
        raise ValueError(f"{champ} : nombre invalide « {t} »")


def _fmt(v):
    if v in (None, ""):
        return ""
    f = float(v)
    return str(int(f)) if f == int(f) else str(f)


# ═══════════════════════════════════════════════════════════════════
#  ONGLET
# ═══════════════════════════════════════════════════════════════════
class RulesTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=T["bg"])
        self.app = app
        self.selected_id = None
        self._creneaux = []
        self._build()
        self.refresh()

    # ══════════════════════════════════════════════════════════════
    #  STRUCTURE
    # ══════════════════════════════════════════════════════════════
    def _build(self):
        # ── Bandeau de page ───────────────────────────────────────
        hdr = tk.Frame(self, bg=T["surface"])
        hdr.pack(fill="x")
        left = tk.Frame(hdr, bg=T["surface"])
        left.pack(side="left", padx=24, pady=16)
        tk.Label(left, text="Règles de réservation", bg=T["surface"],
                 fg=T["text"], font=F["title"], anchor="w").pack(anchor="w")
        tk.Label(left, text="Toute réservation qui sort de la règle applicable "
                            "est refusée comme conflit.",
                 bg=T["surface"], fg=T["text_m"], font=F["sm"],
                 anchor="w").pack(anchor="w", pady=(2, 0))

        self.kpi_box = tk.Frame(hdr, bg=T["surface"])
        self.kpi_box.pack(side="right", padx=24)
        tk.Frame(self, bg=T["border"], height=1).pack(fill="x")

        body = tk.Frame(self, bg=T["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=18)
        self._build_list(body)
        self._build_form(body)

    # ── Panneau gauche : liste ────────────────────────────────────
    def _build_list(self, parent):
        card = Card(parent, title="Règles enregistrées",
                    subtitle="Cliquez sur une ligne pour la modifier",
                    accent=T["primary"], padding=0)
        card.pack(side="left", fill="both", expand=True)

        bar = tk.Frame(card.head, bg=T["surface"])
        bar.pack(side="right")
        Button(bar, "Nouvelle règle", icon="+", command=self._new,
               variant="primary", size="sm", surface=T["surface"]).pack()
        card.body.configure(padx=0)

        wrap = tk.Frame(card.body, bg=T["surface"])
        wrap.pack(fill="both", expand=True)

        cols = ("nom", "salle", "periode", "jours", "creneaux", "violon", "actif")
        heads = {"nom": "RÈGLE", "salle": "SALLE", "periode": "PÉRIODE",
                 "jours": "JOURS", "creneaux": "CRÉNEAUX AUTORISÉS",
                 "violon": "VIOLON", "actif": "ÉTAT"}
        # Largeurs de base modestes : le Treeview ne doit pas réclamer plus
        # de place que la fenêtre, sinon il écrase le panneau de droite.
        widths = {"nom": 155, "salle": 82, "periode": 112, "jours": 72,
                  "creneaux": 135, "violon": 52, "actif": 56}
        mins   = {"nom": 120, "salle": 70, "periode": 95,  "jours": 60,
                  "creneaux": 110, "violon": 50, "actif": 54}
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 height=16, selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], minwidth=mins[c], stretch=True,
                             anchor="center" if c in ("violon", "actif") else "w")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 6), pady=6)
        self.tree.pack(fill="both", expand=True, padx=(14, 0), pady=6)
        UI.zebra(self.tree)
        self.tree.tag_configure("off", foreground=T["text_d"])
        self.tree.tag_configure("sel", background=T["primary_l"])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.empty = UI.empty_state(
            wrap, icon="⚖", title="Aucune règle définie",
            hint="Sans règle, l'application applique le comportement historique "
                 "(créneaux 15h-18h / 21h-01h, pause de 3 h).",
            surface=T["surface"])

    # ── Panneau droit : formulaire ────────────────────────────────
    def _build_form(self, parent):
        outer = tk.Frame(parent, bg=T["bg"], width=452)
        outer.pack(side="left", fill="both", padx=(16, 0))
        outer.pack_propagate(False)

        card = Card(outer, padding=0)
        card.pack(fill="both", expand=True)

        head = tk.Frame(card.body, bg=T["surface"])
        head.pack(fill="x", padx=16, pady=(16, 12))
        self.form_title = tk.Label(head, text="Nouvelle règle", bg=T["surface"],
                                   fg=T["text"], font=F["section"], anchor="w")
        self.form_title.pack(side="left")
        self.form_badge = tk.Frame(head, bg=T["surface"])
        self.form_badge.pack(side="right")
        tk.Frame(card.body, bg=T["border"], height=1).pack(fill="x")

        scroll, form = UI.scrollable(card.body, bg=T["surface"])
        scroll.pack(fill="both", expand=True)
        self.form = form

        # ── 1 · Portée ────────────────────────────────────────────
        self._step(form, "1", "Portée de la règle",
                   "Quand cette règle s'applique")
        self.e_nom = self._field(form, "Nom de la règle",
                                 placeholder="ex. Saison haute — Almes")

        self._label(form, "Salle concernée")
        seg = tk.Frame(form, bg=T["surface"])
        seg.pack(fill="x", padx=16, pady=(0, 12))
        self.salle_var = tk.StringVar(value="Almes")
        self._salle_btns = {}
        for key, lbl in SALLE_CHOICES:
            b = tk.Label(seg, text="Toutes" if key == "*" else lbl,
                         font=F["sm_bold"], padx=10, pady=7, cursor="hand2", bd=0)
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e, k=key: self._select_salle(k))
            self._salle_btns[key] = b
        self._paint_salles()

        self._label(form, "Période", "Laisser vide = la règle s'applique toujours")
        per = tk.Frame(form, bg=T["surface"])
        per.pack(fill="x", padx=16, pady=(0, 12))
        self.e_d1 = Entry(per, width=11, placeholder="JJ/MM/AAAA",
                          surface=T["surface"])
        self.e_d1.pack(side="left")
        tk.Label(per, text="→", bg=T["surface"], fg=T["text_d"],
                 font=F["md"]).pack(side="left", padx=9)
        self.e_d2 = Entry(per, width=11, placeholder="JJ/MM/AAAA",
                          surface=T["surface"])
        self.e_d2.pack(side="left")

        self._label(form, "Jours de la semaine")
        jf = tk.Frame(form, bg=T["surface"])
        jf.pack(fill="x", padx=16, pady=(0, 14))
        self.jours_vars, self._jour_btns = {}, {}
        for i, j in enumerate(rules_mod.JOURS_FR):
            v = tk.BooleanVar(value=True)
            self.jours_vars[i] = v
            b = tk.Label(jf, text=j[:3], font=F["sm_bold"], padx=9, pady=6,
                         cursor="hand2", bd=0)
            b.pack(side="left", padx=(0, 3))
            b.bind("<Button-1>", lambda e, k=i: self._toggle_jour(k))
            self._jour_btns[i] = b
        self._paint_jours()

        # ── 2 · Conditions horaires ───────────────────────────────
        self._step(form, "2", "Conditions horaires",
                   "Ce qui est autorisé, et ce qui devient un conflit")

        self._label(form, "Créneaux autorisés",
                    "Une réservation hors de cette liste est refusée. "
                    "Liste vide = horaires libres.")
        add = tk.Frame(form, bg=T["surface"])
        add.pack(fill="x", padx=16, pady=(0, 8))
        self.e_c1 = Entry(add, width=6, justify="center", surface=T["surface"])
        self.e_c1.pack(side="left"); self.e_c1.insert(0, "15:00")
        tk.Label(add, text="→", bg=T["surface"], fg=T["text_d"],
                 font=F["md"]).pack(side="left", padx=7)
        self.e_c2 = Entry(add, width=6, justify="center", surface=T["surface"])
        self.e_c2.pack(side="left"); self.e_c2.insert(0, "18:00")
        Button(add, "Ajouter", command=self._add_creneau, variant="soft",
               size="sm", surface=T["surface"]).pack(side="left", padx=(9, 0))

        self.cren_box = tk.Frame(form, bg=T["surface"])
        self.cren_box.pack(fill="x", padx=16, pady=(0, 14))
        self._render_creneaux()

        self.e_pause = self._field(form, "Pause minimale entre 2 réservations",
                                   hint="En heures. 0 = pas de contrainte.",
                                   width=8, inline=True)
        self.e_pause.insert(0, "3")
        self.e_fin_max = self._field(form, "Heure de fin maximale",
                                     hint="Vide = pas de limite.",
                                     width=8, inline=True, placeholder="HH:MM")
        self.v_sono = tk.BooleanVar(value=False)
        UI.switch_row(form, "Sono obligatoire", self.v_sono,
                      hint="Refuse la réservation si la sono n'est pas cochée.",
                      surface=T["surface"]).pack(fill="x", padx=16, pady=(4, 14))

        # ── 3 · Violoniste ────────────────────────────────────────
        self._step(form, "3", "Heure de violoniste offerte",
                   "Affichée en violet dans le calendrier", color=T["violon"])
        self.v_violon = tk.BooleanVar(value=False)
        UI.switch_row(form, "Violoniste offert avec cette règle", self.v_violon,
                      command=self._toggle_violon,
                      hint="Si désactivé, demander le violon est refusé.",
                      color=T["violon"], surface=T["surface"]
                      ).pack(fill="x", padx=16, pady=(2, 8))

        self.violon_box = tk.Frame(form, bg=T["violon_l"])
        self.violon_box.pack(fill="x", padx=16, pady=(0, 14))
        vb = tk.Frame(self.violon_box, bg=T["violon_l"], padx=14, pady=12)
        vb.pack(fill="x")
        self.e_v1 = self._mini(vb, "Début au plus tôt", "HH:MM")
        self.e_v2 = self._mini(vb, "Fin au plus tard", "HH:MM")
        self.e_vd = self._mini(vb, "Durée maximale (h)", "1")
        self.e_vp = self._mini(vb, "Pause entre 2 passages (h)", "1")
        self._toggle_violon()

        # ── 4 · Divers ────────────────────────────────────────────
        self._step(form, "4", "Divers", "Arbitrage et activation")
        self.e_prio = self._field(form, "Priorité",
                                  hint="Départage deux règles qui se recouvrent. "
                                       "Le plus grand l'emporte.",
                                  width=8, inline=True)
        self.e_prio.insert(0, "0")
        self.v_actif = tk.BooleanVar(value=True)
        UI.switch_row(form, "Règle active", self.v_actif,
                      hint="Désactiver sans supprimer.",
                      color=T["success"], surface=T["surface"]
                      ).pack(fill="x", padx=16, pady=(4, 12))

        self._label(form, "Notes")
        nwrap = tk.Frame(form, bg=T["border"], padx=1, pady=1)
        nwrap.pack(fill="x", padx=16, pady=(0, 16))
        self.t_notes = tk.Text(nwrap, height=3, font=F["sm"], relief="flat",
                               bd=0, highlightthickness=0, bg=T["surface"],
                               fg=T["text"], padx=8, pady=6, wrap="word")
        self.t_notes.pack(fill="x")

        # ── Barre d'actions (fixe, hors scroll) ───────────────────
        tk.Frame(card.body, bg=T["border"], height=1).pack(fill="x")
        act = tk.Frame(card.body, bg=T["surface_2"], padx=16, pady=13)
        act.pack(fill="x")
        Button(act, "Enregistrer", icon="✓", command=self._save,
               variant="primary", surface=T["surface_2"]).pack(side="left")
        Button(act, "Annuler", command=self._new, variant="secondary",
               size="sm", surface=T["surface_2"]).pack(side="left", padx=7)
        self.btn_del = Button(act, "Supprimer", command=self._delete,
                              variant="secondary", size="sm",
                              surface=T["surface_2"])
        self.btn_del.pack(side="right")

        self.status = tk.Label(card.body, text="", bg=T["surface"],
                               fg=T["text_m"], font=F["sm"], wraplength=390,
                               justify="left", anchor="w")
        self.status.pack(fill="x", padx=16, pady=(0, 10))

    # ══════════════════════════════════════════════════════════════
    #  PETITS COMPOSANTS
    # ══════════════════════════════════════════════════════════════
    def _step(self, parent, num, title, hint="", color=None):
        color = color or T["primary"]
        f = tk.Frame(parent, bg=T["surface"])
        f.pack(fill="x", padx=16, pady=(16, 10))
        badge = tk.Frame(f, bg=color, width=22, height=22)
        badge.pack(side="left"); badge.pack_propagate(False)
        tk.Label(badge, text=num, bg=color, fg="white",
                 font=F["sm_bold"]).place(relx=.5, rely=.5, anchor="center")
        txt = tk.Frame(f, bg=T["surface"])
        txt.pack(side="left", padx=(10, 0), fill="x", expand=True)
        tk.Label(txt, text=title, bg=T["surface"], fg=T["text"],
                 font=F["section"], anchor="w").pack(anchor="w")
        if hint:
            tk.Label(txt, text=hint, bg=T["surface"], fg=T["text_m"],
                     font=F["xs"], anchor="w").pack(anchor="w")
        tk.Frame(parent, bg=T["border"], height=1).pack(fill="x", padx=16)

    def _label(self, parent, text, hint=""):
        tk.Label(parent, text=text, bg=T["surface"], fg=T["text_m"],
                 font=F["sm_bold"], anchor="w").pack(
            anchor="w", padx=16, pady=(10, 4))
        if hint:
            tk.Label(parent, text=hint, bg=T["surface"], fg=T["text_d"],
                     font=F["xs"], anchor="w", justify="left",
                     wraplength=370).pack(anchor="w", padx=16, pady=(0, 5))

    def _field(self, parent, label, hint="", width=None, inline=False,
               placeholder=""):
        if inline:
            row = tk.Frame(parent, bg=T["surface"])
            row.pack(fill="x", padx=16, pady=(10, 2))
            txt = tk.Frame(row, bg=T["surface"])
            txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=label, bg=T["surface"], fg=T["text"],
                     font=F["default"], anchor="w").pack(anchor="w")
            if hint:
                tk.Label(txt, text=hint, bg=T["surface"], fg=T["text_m"],
                         font=F["xs"], anchor="w").pack(anchor="w")
            e = Entry(row, width=width, justify="center", placeholder=placeholder,
                      surface=T["surface"])
            e.pack(side="right", padx=(10, 0))
            return e
        self._label(parent, label, hint)
        e = Entry(parent, width=width, placeholder=placeholder,
                  surface=T["surface"])
        e.pack(fill="x", padx=16, pady=(0, 4))
        return e

    def _mini(self, parent, label, placeholder=""):
        row = tk.Frame(parent, bg=T["violon_l"])
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=T["violon_l"], fg=T["violon"],
                 font=F["sm"], anchor="w").pack(side="left")
        e = Entry(row, width=7, justify="center", placeholder=placeholder,
                  surface=T["violon_l"])
        e.pack(side="right")
        return e

    # ── Salle ─────────────────────────────────────────────────────
    def _select_salle(self, key):
        self.salle_var.set(key)
        self._paint_salles()

    def _paint_salles(self):
        cur = self.salle_var.get()
        for k, b in self._salle_btns.items():
            on = k == cur
            b.configure(bg=SALLE_TONE.get(k, T["primary"]) if on else T["surface_2"],
                        fg="white" if on else T["text_m"])

    # ── Jours ─────────────────────────────────────────────────────
    def _toggle_jour(self, i):
        self.jours_vars[i].set(not self.jours_vars[i].get())
        self._paint_jours()

    def _paint_jours(self):
        for i, b in self._jour_btns.items():
            on = self.jours_vars[i].get()
            b.configure(bg=T["primary"] if on else T["surface_2"],
                        fg="white" if on else T["text_m"])

    # ── Créneaux ──────────────────────────────────────────────────
    def _render_creneaux(self):
        for w in self.cren_box.winfo_children():
            w.destroy()
        if not self._creneaux:
            tk.Label(self.cren_box,
                     text="Aucun créneau — les horaires sont libres.",
                     bg=T["surface"], fg=T["text_d"], font=F["xs"],
                     anchor="w").pack(anchor="w")
            return
        for val in self._creneaux:
            row = tk.Frame(self.cren_box, bg=T["primary_l"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"  {val}", bg=T["primary_l"],
                     fg=T["primary_d"], font=F["sm_bold"], anchor="w",
                     padx=8, pady=6).pack(side="left")
            x = tk.Label(row, text="✕", bg=T["primary_l"], fg=T["primary_d"],
                         font=F["sm"], cursor="hand2", padx=10, pady=6)
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, v=val: self._del_creneau(v))

    def _add_creneau(self):
        try:
            a = _hhmm(self.e_c1.get(), "Créneau (début)")
            b = _hhmm(self.e_c2.get(), "Créneau (fin)")
            if not a or not b:
                raise ValueError("Renseigne le début et la fin du créneau.")
        except ValueError as ex:
            self.e_c1.set_error(True); self.e_c2.set_error(True)
            toast(str(ex), "danger", "Créneau invalide")
            return
        self.e_c1.set_error(False); self.e_c2.set_error(False)
        val = f"{a}-{b}"
        if val not in self._creneaux:
            self._creneaux.append(val)
            self._render_creneaux()

    def _del_creneau(self, val):
        if val in self._creneaux:
            self._creneaux.remove(val)
            self._render_creneaux()

    def _toggle_violon(self):
        on = self.v_violon.get()
        for e in (self.e_v1, self.e_v2, self.e_vd, self.e_vp):
            e.set_state("normal" if on else "disabled")

    # ══════════════════════════════════════════════════════════════
    #  DONNÉES
    # ══════════════════════════════════════════════════════════════
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        rows = database.get_all_rules()
        for r in rows:
            periode = (f"{_fr(r['date_debut']) or '…'} → {_fr(r['date_fin']) or '…'}"
                       if (r["date_debut"] or r["date_fin"]) else "Toujours")
            cr = rules_mod.parse_creneaux(r["creneaux"])
            self.tree.insert(
                "", "end", iid=str(r["id"]),
                values=(r["nom"],
                        "Toutes" if r["salle"] == "*" else r["salle"],
                        periode, rules_mod.jours_label(r["jours"]),
                        ", ".join(f"{a}-{b}" for a, b in cr) if cr else "Libres",
                        "🎻 oui" if r["violon_gratuit"] else "—",
                        "● actif" if r["actif"] else "○ inactif"),
                tags=() if r["actif"] else ("off",))
        self.tree.restripe()

        if rows:
            self.empty.pack_forget()
            self.tree.pack(fill="both", expand=True, padx=(14, 0), pady=6)
        else:
            self.tree.pack_forget()
            self.empty.pack(fill="both", expand=True)
        self._render_kpis(rows)

    def _render_kpis(self, rows):
        for w in self.kpi_box.winfo_children():
            w.destroy()
        actives = sum(1 for r in rows if r["actif"])
        violon = sum(1 for r in rows if r["actif"] and r["violon_gratuit"])
        for txt, tone in ((f"{len(rows)} règle(s)", "neutral"),
                          (f"{actives} active(s)", "success"),
                          (f"{violon} avec violon", "violon")):
            Chip(self.kpi_box, txt, tone=tone, dot=True,
                 surface=T["surface"]).pack(side="left", padx=(0, 7))

    def _on_select(self, _=None):
        sel = self.tree.selection()
        if sel:
            self._load(int(sel[0]))

    # ── Formulaire ────────────────────────────────────────────────
    def _new(self):
        self.selected_id = None
        self.form_title.configure(text="Nouvelle règle")
        for w in self.form_badge.winfo_children():
            w.destroy()
        self.tree.selection_remove(*self.tree.selection())
        for e in (self.e_nom, self.e_d1, self.e_d2, self.e_fin_max,
                  self.e_v1, self.e_v2, self.e_vd, self.e_vp):
            e.set_state("normal"); e.delete(0, "end"); e.set_error(False)
        self._select_salle("Almes")
        for v in self.jours_vars.values():
            v.set(True)
        self._paint_jours()
        self._creneaux = []
        self._render_creneaux()
        self.e_pause.delete(0, "end"); self.e_pause.insert(0, "3")
        self.e_prio.delete(0, "end"); self.e_prio.insert(0, "0")
        self.v_sono.set(False); self.v_violon.set(False); self.v_actif.set(True)
        self.t_notes.delete("1.0", "end")
        self._toggle_violon()
        self.btn_del.configure(state="disabled")
        self.status.configure(text="")

    def _load(self, rule_id):
        r = database.get_rule(rule_id)
        if not r:
            return
        self._new()
        self.selected_id = rule_id
        self.form_title.configure(text=r["nom"] or f"Règle #{rule_id}")
        Chip(self.form_badge, f"#{rule_id}", tone="primary",
             surface=T["surface"]).pack()
        self.e_nom.insert(0, r["nom"] or "")
        self._select_salle(r["salle"] if r["salle"] in SALLE_LABEL else "Almes")
        if r["date_debut"]:
            self.e_d1.insert(0, _fr(r["date_debut"]))
        if r["date_fin"]:
            self.e_d2.insert(0, _fr(r["date_fin"]))
        days = rules_mod.parse_jours(r["jours"])
        for i, v in self.jours_vars.items():
            v.set(i in days)
        self._paint_jours()
        self._creneaux = [f"{a}-{b}" for a, b in
                          rules_mod.parse_creneaux(r["creneaux"])]
        self._render_creneaux()
        self.e_pause.delete(0, "end"); self.e_pause.insert(0, _fmt(r["pause_min_heures"]))
        if r["heure_fin_max"]:
            self.e_fin_max.insert(0, r["heure_fin_max"])
        self.v_sono.set(bool(r["sono_obligatoire"]))
        self.v_violon.set(bool(r["violon_gratuit"]))
        self._toggle_violon()
        if r["violon_gratuit"]:
            for e, val in ((self.e_v1, r["violon_debut_min"]),
                           (self.e_v2, r["violon_fin_max"]),
                           (self.e_vd, _fmt(r["violon_duree_max"])),
                           (self.e_vp, _fmt(r["violon_pause_heures"]))):
                if val:
                    e.insert(0, val)
        self.e_prio.delete(0, "end"); self.e_prio.insert(0, str(int(r["priorite"] or 0)))
        self.v_actif.set(bool(r["actif"]))
        if r["notes"]:
            self.t_notes.insert("1.0", r["notes"])
        self.btn_del.configure(state="normal")
        self.status.configure(text=rules_mod.describe_rule(r), fg=T["text_m"])

    def _collect(self):
        for e in (self.e_nom, self.e_d1, self.e_d2, self.e_pause,
                  self.e_fin_max, self.e_prio):
            e.set_error(False)
        nom = self.e_nom.get().strip()
        if not nom:
            self.e_nom.set_error(True)
            raise ValueError("Le nom de la règle est obligatoire.")
        d1, d2 = _iso(self.e_d1.get()), _iso(self.e_d2.get())
        if d1 and d2 and d1 > d2:
            self.e_d1.set_error(True); self.e_d2.set_error(True)
            raise ValueError("La date de début est postérieure à la date de fin.")
        days = {i for i, v in self.jours_vars.items() if v.get()}
        if not days:
            raise ValueError("Sélectionne au moins un jour de la semaine.")

        data = {
            "nom": nom,
            "salle": self.salle_var.get(),
            "date_debut": d1, "date_fin": d2,
            "jours": rules_mod.format_jours(days),
            "creneaux": ";".join(self._creneaux),
            "pause_min_heures": _num(self.e_pause.get(), "Pause minimale", 0) or 0,
            "heure_fin_max": _hhmm(self.e_fin_max.get(), "Heure de fin max"),
            "sono_obligatoire": 1 if self.v_sono.get() else 0,
            "violon_gratuit": 1 if self.v_violon.get() else 0,
            "violon_debut_min": None, "violon_fin_max": None,
            "violon_duree_max": None, "violon_pause_heures": 0,
            "priorite": int(_num(self.e_prio.get(), "Priorité", 0) or 0),
            "actif": 1 if self.v_actif.get() else 0,
            "notes": self.t_notes.get("1.0", "end").strip(),
        }
        if self.v_violon.get():
            data["violon_debut_min"] = _hhmm(self.e_v1.get(), "Violon — début")
            data["violon_fin_max"] = _hhmm(self.e_v2.get(), "Violon — fin")
            data["violon_duree_max"] = _num(self.e_vd.get(), "Violon — durée max")
            data["violon_pause_heures"] = _num(self.e_vp.get(), "Violon — pause", 1) or 0
            if (data["violon_debut_min"] and data["violon_fin_max"]
                    and data["violon_debut_min"] >= data["violon_fin_max"]):
                self.e_v1.set_error(True); self.e_v2.set_error(True)
                raise ValueError("Violon : le début doit précéder la fin.")
        return data

    def _save(self):
        try:
            data = self._collect()
        except ValueError as ex:
            self.status.configure(text=str(ex), fg=T["danger"])
            toast(str(ex), "danger", "Règle invalide")
            return
        if self.selected_id:
            database.update_rule(self.selected_id, data)
            msg = f"Règle « {data['nom']} » mise à jour."
        else:
            self.selected_id = database.insert_rule(data)
            msg = f"Règle « {data['nom']} » créée."
        self.refresh()
        self.tree.selection_set(str(self.selected_id))
        self.status.configure(
            text=rules_mod.describe_rule(database.get_rule(self.selected_id)),
            fg=T["text_m"])
        toast(msg, "success", "Enregistré")
        if hasattr(self.app, "refresh_list"):
            self.app.refresh_list()

    def _delete(self):
        if not self.selected_id:
            return
        r = database.get_rule(self.selected_id)
        if not messagebox.askyesno(
                "Confirmer la suppression",
                f"Supprimer définitivement la règle « {r['nom']} » ?\n\n"
                "Les réservations qui en dépendaient repasseront sous la règle "
                "suivante, ou sous le comportement par défaut."):
            return
        database.delete_rule(self.selected_id)
        self._new()
        self.refresh()
        toast(f"Règle « {r['nom']} » supprimée.", "warning", "Supprimé")
