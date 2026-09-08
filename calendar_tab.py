"""
calendar_tab.py — Calendrier mensuel redesigné (UI/UX v3)
3 sous-colonnes par jour : Almes | Chichkhane | Rayhane
"""
import calendar
import tkinter as tk
from datetime import date

import rules
import database

# ── Palette : alignée sur les design tokens de ui_kit ───────────────────────
import ui_kit as UI
from ui_kit import T as TOK

BG_APP      = TOK["bg"]
BG_SIDEBAR  = TOK["nav"]
BG_DAY_HDR  = TOK["surface_2"]
BG_CELL     = TOK["surface"]
BG_WEEKEND  = "#FBFCFE"
BG_TODAY    = TOK["primary_l"]
BG_TODAY_BD = TOK["primary"]
BG_EMPTY    = TOK["surface_2"]
BORDER      = TOK["border"]
FG_NUM      = TOK["text"]
FG_WKND     = TOK["text_d"]
FG_TODAY    = TOK["primary"]

SC = {
    "Almes":      {"hdr": "#1D4ED8", "bg": TOK["salle_almes"],      "fg": "#FFFFFF", "light": "#DBEAFE"},
    "Chichkhane": {"hdr": "#B91C1C", "bg": TOK["salle_chichkhane"], "fg": "#FFFFFF", "light": "#FEE2E2"},
    "Rayhane":    {"hdr": "#15803D", "bg": TOK["salle_rayhane"],    "fg": "#FFFFFF", "light": "#DCFCE7"},
}
ABBR = {"Almes": "ALM", "Chichkhane": "CHK", "Rayhane": "RAY"}

# Heure de violoniste offerte : badge violet distinct des vraies réservations
VIOLON = {"bg": TOK["violon"], "fg": "#FFFFFF", "light": TOK["violon_l"]}

JOURS_SHORT  = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
MOIS_FR      = ["Janvier","Février","Mars","Avril","Mai","Juin",
                "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]


def _mk_lbl(parent, txt, cbg, cfg, si, ci):
    lbl = tk.Label(parent, text=txt, bg=cbg, fg=cfg,
                   font=("Segoe UI", 8, "bold"),
                   anchor="center", pady=4, cursor="hand2")
    lbl.grid(row=si + 1, column=ci, sticky="nsew", padx=1, pady=1)
    return lbl


# ── Tooltip ──────────────────────────────────────────────────────────────────
class _Tooltip:
    def __init__(self, widget, text: str):
        self._widget = widget
        self._text   = text
        self._win    = None
        widget.bind("<Enter>",   self._show, add="+")
        widget.bind("<Leave>",   self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _show(self, event=None):
        if self._win or not self._text:
            return
        x = self._widget.winfo_rootx() + 24
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        outer = tk.Frame(tw, bg="#1A2B45", bd=1, relief="solid")
        outer.pack()
        tk.Label(outer, text=self._text,
                 bg="#1A2B45", fg="white",
                 font=("Segoe UI", 9),
                 justify="left",
                 padx=12, pady=8).pack()

    def _hide(self, event=None):
        if self._win:
            self._win.destroy()
            self._win = None


# ── Main widget ───────────────────────────────────────────────────────────────
class YearCalendarTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_APP)
        self.app   = app
        self.today = date.today()
        self.year  = self.today.year
        self.month = self.today.month
        self.visible     = {s: tk.BooleanVar(value=True) for s in rules.SALLES}
        self.visible_all = tk.BooleanVar(value=True)

        self._build_topbar()
        self._build_area()
        self.bind("<Configure>", self._on_configure)
        self.render()

    # ── Top bar ───────────────────────────────────────────────────
    def _build_topbar(self):
        self._topbar = tk.Frame(self, bg=TOK["surface"])
        self._topbar.pack(side="top", fill="x")
        inner = tk.Frame(self._topbar, bg=TOK["surface"])
        inner.pack(fill="x", padx=20, pady=13)

        # ── Titre + navigation ────────────────────────────────────
        left = tk.Frame(inner, bg=TOK["surface"])
        left.pack(side="left")
        self.nav_lbl = tk.Label(left, text="", bg=TOK["surface"], fg=TOK["text"],
                                font=UI.F["title"], anchor="w", width=20)
        self.nav_lbl.pack(side="left")

        nav = tk.Frame(left, bg=TOK["surface_2"], padx=3, pady=3)
        nav.pack(side="left", padx=(14, 0))

        def _arrow(text, cmd, tip=""):
            b = tk.Label(nav, text=text, bg=TOK["surface_2"], fg=TOK["text_m"],
                         font=UI.F["sm_bold"], padx=9, pady=5, cursor="hand2")
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.configure(bg=TOK["surface"],
                                                    fg=TOK["primary"]))
            b.bind("<Leave>", lambda e: b.configure(bg=TOK["surface_2"],
                                                    fg=TOK["text_m"]))
            return b

        _arrow("«", self._prev_year)
        _arrow("‹", self._prev_month)
        _arrow("›", self._next_month)
        _arrow("»", self._next_year)

        UI.Button(left, "Aujourd'hui", command=self._go_today, variant="soft",
                  size="sm", surface=TOK["surface"]).pack(side="left", padx=(10, 0))

        # ── Filtres par salle ─────────────────────────────────────
        legend = tk.Frame(inner, bg=TOK["surface"])
        legend.pack(side="right")
        self._salle_pills = {}
        for salle in rules.SALLES:
            p = tk.Frame(legend, bg=TOK["surface_2"], cursor="hand2")
            p.pack(side="left", padx=(0, 7))
            dot = tk.Frame(p, bg=SC[salle]["bg"], width=9, height=9)
            dot.pack(side="left", padx=(11, 0), pady=8); dot.pack_propagate(False)
            lb = tk.Label(p, text=salle, bg=TOK["surface_2"], fg=TOK["text"],
                          font=UI.F["sm_bold"], padx=8, pady=6, cursor="hand2")
            lb.pack(side="left")
            self._salle_pills[salle] = (p, lb, dot)
            for w in (p, lb, dot):
                w.bind("<Button-1>", lambda e, sl=salle: self._toggle_salle(sl))

        tk.Frame(legend, bg=TOK["border"], width=1, height=22).pack(
            side="left", padx=(4, 10), fill="y")

        self._all_pill = tk.Label(legend, text="Tout le complexe",
                                  bg=TOK["surface_2"], fg=TOK["text_m"],
                                  font=UI.F["sm_bold"], padx=12, pady=7,
                                  cursor="hand2")
        self._all_pill.pack(side="left")
        self._all_pill.bind("<Button-1>", lambda e: self._toggle_all())
        self._paint_pills()

    def _paint_pills(self):
        for salle, (p, lb, dot) in self._salle_pills.items():
            on = self.visible[salle].get()
            bg = SC[salle]["light"] if on else TOK["surface_2"]
            fg = SC[salle]["hdr"] if on else TOK["text_d"]
            p.configure(bg=bg); lb.configure(bg=bg, fg=fg)
            dot.configure(bg=SC[salle]["bg"] if on else TOK["border_s"])
        allon = all(v.get() for v in self.visible.values())
        self.visible_all.set(allon)
        self._all_pill.configure(
            bg=TOK["primary_l"] if allon else TOK["surface_2"],
            fg=TOK["primary_d"] if allon else TOK["text_m"])

    def _toggle_salle(self, salle):
        self.visible[salle].set(not self.visible[salle].get())
        self._paint_pills()
        self.render()

    # ── Calendar grid area ────────────────────────────────────────
    def _build_area(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self._area = tk.Frame(self, bg=BORDER)
        self._area.pack(side="top", fill="both", expand=True, padx=18, pady=16)
        for c in range(7):
            self._area.columnconfigure(c, weight=1, minsize=50)
        self._area.rowconfigure(0, weight=0)
        for r in range(1, 7):
            self._area.rowconfigure(r, weight=1, minsize=60)

    def _on_configure(self, event=None):
        self._area.update_idletasks()

    # ── Navigation ────────────────────────────────────────────────
    def _toggle_all(self):
        v = not all(bv.get() for bv in self.visible.values())
        for bv in self.visible.values():
            bv.set(v)
        self._paint_pills()
        self.render()

    def _prev_month(self):
        self.month -= 1
        if self.month < 1: self.month, self.year = 12, self.year - 1
        self.render()

    def _next_month(self):
        self.month += 1
        if self.month > 12: self.month, self.year = 1, self.year + 1
        self.render()

    def _prev_year(self):  self.year -= 1; self.render()
    def _next_year(self):  self.year += 1; self.render()
    def _go_today(self):
        self.year, self.month = self.today.year, self.today.month
        self.render()

    def render_year(self): self.render()

    # ── Render ────────────────────────────────────────────────────
    def render(self):
        self.nav_lbl.configure(text=f"{MOIS_FR[self.month-1]}  {self.year}")

        for w in self._area.winfo_children():
            w.destroy()

        last_day = calendar.monthrange(self.year, self.month)[1]
        month_start = date(self.year, self.month, 1).isoformat()
        month_end   = date(self.year, self.month, last_day).isoformat()

        # Fetch reservations whose event date falls in the month
        resas = database.get_reservations_in_range(month_start, month_end)

        # Also fetch reservations whose *violoniste_date* falls in the month
        # (the main event may be on a different day/month)
        conn = database.get_connection()
        viol_rows = conn.execute(
            "SELECT * FROM reservations "
            "WHERE with_violoniste=1 AND violoniste_date BETWEEN ? AND ? "
            "ORDER BY violoniste_date",
            (month_start, month_end),
        ).fetchall()
        conn.close()
        extra_viol = [dict(r) for r in viol_rows
                      if r["date_evenement"] < month_start or r["date_evenement"] > month_end]

        by_date: dict = {}
        for r in resas:
            by_date.setdefault(r["date_evenement"], []).append(r)

        # Inject virtual Rayhane entries for violoniste slots not already in the month range
        for r in extra_viol:
            vdate = r["violoniste_date"]
            if vdate:
                # Build a lightweight virtual entry that looks like a Rayhane reservation
                virtual = dict(r)
                virtual["salle"]        = "Rayhane"
                virtual["heure_debut"]  = r.get("violoniste_heure_debut") or ""
                virtual["heure_fin"]    = r.get("violoniste_heure_fin") or ""
                virtual["_is_violon"]   = True
                virtual["salle_origine"] = r.get("salle")
                by_date.setdefault(vdate, []).append(virtual)

        # For reservations already in the month, also add a Rayhane entry when
        # the violoniste_date is set (may equal date_evenement or differ)
        for r in resas:
            if not r.get("with_violoniste"):
                continue
            vdate = r.get("violoniste_date") or r["date_evenement"]
            if month_start <= vdate <= month_end:
                virtual = dict(r)
                virtual["salle"]       = "Rayhane"
                virtual["heure_debut"] = r.get("violoniste_heure_debut") or ""
                virtual["heure_fin"]   = r.get("violoniste_heure_fin") or ""
                virtual["_is_violon"]  = True
                virtual["salle_origine"] = r.get("salle")
                by_date.setdefault(vdate, []).append(virtual)

        vis = {s for s, v in self.visible.items() if v.get()}

        # Day-of-week headers
        for ci, j in enumerate(JOURS_SHORT):
            is_wknd = ci >= 5
            fg = TOK["danger"] if is_wknd else TOK["text_m"]
            tk.Label(self._area,
                     text=j.upper(),
                     bg=BG_DAY_HDR, fg=fg,
                     font=UI.F["xs_bold"],
                     pady=10, anchor="center"
                     ).grid(row=0, column=ci, sticky="nsew", padx=1, pady=(0, 1))

        # Weeks
        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(self.year, self.month)
        while len(weeks) < 6:
            weeks.append([0] * 7)

        for ri, week in enumerate(weeks):
            for ci, day_num in enumerate(week):
                is_empty   = day_num == 0
                is_today   = (not is_empty and
                              date(self.year, self.month, day_num) == self.today)
                is_weekend = ci >= 5

                if is_empty:     bg = BG_EMPTY
                elif is_today:   bg = BG_TODAY
                elif is_weekend: bg = BG_WEEKEND
                else:            bg = BG_CELL

                day_res = []
                if not is_empty:
                    iso = date(self.year, self.month, day_num).isoformat()
                    day_res = [r for r in by_date.get(iso, [])
                               if r["salle"] in vis]

                cell = self._make_cell(
                    day_num, bg, is_today, is_weekend, is_empty, day_res, vis)
                cell.grid(row=ri + 1, column=ci,
                          sticky="nsew", padx=1, pady=1)

    # ── Cell ──────────────────────────────────────────────────────
    def _make_cell(self, day_num, bg, is_today, is_weekend, is_empty, day_res, vis):
        cell = tk.Frame(self._area, bg=bg, highlightthickness=1,
                        highlightbackground=BG_TODAY_BD if is_today else BORDER)
        cell.rowconfigure(1, weight=1)
        cell.columnconfigure(0, weight=1)

        if is_empty:
            return cell

        # Day number
        if is_today:
            num_fr = tk.Frame(cell, bg=BG_TODAY_BD, padx=6, pady=4)
            num_fr.grid(row=0, column=0, sticky="ne")
            tk.Label(num_fr, text=str(day_num),
                     bg=BG_TODAY_BD, fg="white",
                     font=("Segoe UI", 11, "bold")).pack()
        else:
            fg = FG_WKND if is_weekend else FG_NUM
            tk.Label(cell, text=str(day_num),
                     bg=bg, fg=fg,
                     font=("Segoe UI", 11, "bold"),
                     anchor="ne", padx=6, pady=4
                     ).grid(row=0, column=0, sticky="ew")

        active = [s for s in rules.SALLES if s in vis]
        if not active:
            return cell

        sub = tk.Frame(cell, bg=bg)
        sub.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 3))
        for ci in range(len(active)):
            sub.columnconfigure(ci, weight=1)

        # Hall abbreviation headers (small)
        for ci, salle in enumerate(active):
            tk.Label(sub, text=ABBR[salle],
                     bg=SC[salle]["hdr"], fg="white",
                     font=("Segoe UI", 7, "bold"),
                     pady=2, anchor="center"
                     ).grid(row=0, column=ci, sticky="ew", padx=1)

        # Reservation slots
        by_salle = {s: [r for r in day_res if r["salle"] == s] for s in active}
        max_s = max((len(v) for v in by_salle.values()), default=0)

        for si in range(max(max_s, 1)):
            for ci, salle in enumerate(active):
                lst = by_salle[salle]
                if si < len(lst):
                    r   = lst[si]
                    is_violon = bool(r.get("_is_violon"))
                    txt = f"{r['heure_debut']}-{r['heure_fin']}"
                    if is_violon:
                        txt = f"🎻 {txt}"

                    # Violon offert → violet ; temporaire → jaune ; sinon salle
                    if is_violon:
                        cbg = VIOLON["bg"]
                        cfg = VIOLON["fg"]
                    elif r.get("is_temporaire"):
                        cbg = "#FDE68A"   # amber-200
                        cfg = "#78350F"   # amber-900
                    else:
                        cbg = SC[salle]["bg"]
                        cfg = SC[salle]["fg"]

                    forfait  = float(r.get("forfait") or 0)
                    acomptes = sum(float(r.get(f"acompte{i}") or 0) for i in range(1, 4))
                    reste    = forfait - acomptes
                    nom      = (r.get("nom_client") or "—").strip()
                    type_evt = (r.get("type_evenement") or "—").strip()
                    statut   = ("⏳ TEMPORAIRE" if r.get("is_temporaire")
                                else (r.get("statut_paiement") or "En attente").strip())
                    if is_violon:
                        lines = [
                            "🎻  HEURE DE VIOLONISTE OFFERTE",
                            f"👤  {nom}",
                            f"⏰  {r['heure_debut']} → {r['heure_fin']}",
                            f"📍  Espace Rayhane",
                            f"🔗  Contrat {r.get('num_bon') or '#' + str(r.get('id'))}"
                            f" — {r.get('salle_origine') or ''}".rstrip(" —"),
                            f"📅  Événement principal : {r.get('date_evenement')}",
                        ]
                        _Tooltip(_mk_lbl(sub, txt, cbg, cfg, si, ci), "\n".join(lines))
                        continue
                    lines = [
                        f"👤  {nom}",
                        f"🎉  {type_evt}",
                        f"⏰  {r['heure_debut']} → {r['heure_fin']}",
                        f"💰  Forfait : {forfait:,.3f} DT",
                        f"✅  Payé    : {acomptes:,.3f} DT",
                        f"⏳  Reste   : {reste:,.3f} DT",
                        f"📋  {statut}",
                    ]
                    if r.get("with_violoniste"):
                        lines.append(
                            f"🎻  Violoniste {r.get('violoniste_heure_debut','')}→{r.get('violoniste_heure_fin','')}")
                    tooltip_txt = "\n".join(lines)
                else:
                    txt, cbg, cfg = "", bg, bg
                    tooltip_txt = ""

                lbl = tk.Label(sub, text=txt,
                               bg=cbg, fg=cfg,
                               font=("Segoe UI", 8, "bold"),
                               anchor="center", pady=4,
                               cursor="hand2" if txt else "")
                lbl.grid(row=si + 1, column=ci,
                         sticky="nsew", padx=1, pady=1)
                if tooltip_txt:
                    _Tooltip(lbl, tooltip_txt)

        return cell
