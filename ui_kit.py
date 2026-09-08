# -*- coding: utf-8 -*-
"""
ui_kit.py — Bibliothèque de composants UI pour Marassim.

100 % Tkinter / stdlib : aucune dépendance externe, aucun accès réseau.
L'application reste un simple `python main.py` et se package avec PyInstaller.

Contenu :
  · TOKENS      — palette, typographie, rayons, espacements
  · install_theme(root)  — thème ttk complet (Treeview, Combobox, Scrollbar…)
  · anim / lerp — micro-animations (hover, focus, slide)
  · Button      — bouton arrondi, variantes, icône, état désactivé
  · Entry       — champ avec anneau de focus animé et placeholder
  · Card        — carte blanche avec ombre douce et en-tête optionnel
  · Chip        — pastille de statut
  · Switch      — interrupteur animé
  · Toast       — notification non bloquante (remplace messagebox.showinfo)
  · EmptyState  — état vide illustré
  · StatTile    — tuile de chiffre clé
  · SegmentedControl — sélecteur type iOS/React
"""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

# ═══════════════════════════════════════════════════════════════════
#  TOKENS
# ═══════════════════════════════════════════════════════════════════
T = {
    # Surfaces
    "bg":          "#F6F8FB",
    "surface":     "#FFFFFF",
    "surface_2":   "#F1F5F9",
    "surface_3":   "#E8EDF3",
    "overlay":     "#0F172A",

    # Bordures
    "border":      "#E4E9F0",
    "border_s":    "#CBD5E1",
    "shadow":      "#DDE3EC",
    "shadow_s":    "#C7D0DE",

    # Texte
    "text":        "#0F172A",
    "text_m":      "#64748B",
    "text_d":      "#94A3B8",
    "text_inv":    "#FFFFFF",

    # Marque
    "primary":     "#4F46E5",
    "primary_d":   "#4338CA",
    "primary_l":   "#EEF2FF",
    "primary_b":   "#C7D2FE",

    "accent":      "#0EA5E9",
    "accent_l":    "#E0F2FE",

    # Sémantique
    "success":     "#059669",
    "success_d":   "#047857",
    "success_l":   "#ECFDF5",
    "danger":      "#DC2626",
    "danger_d":    "#B91C1C",
    "danger_l":    "#FEF2F2",
    "warning":     "#D97706",
    "warning_d":   "#B45309",
    "warning_l":   "#FFFBEB",
    "violon":      "#7C3AED",
    "violon_l":    "#F5F3FF",

    # Navigation
    "nav":         "#101828",
    "nav_h":       "#1D2939",
    "nav_sel":     "#4F46E5",
    "nav_txt":     "#98A2B3",
    "nav_txt_a":   "#FFFFFF",
    "nav_sep":     "#1D2939",

    # Salles
    "salle_almes":      "#3B82F6",
    "salle_chichkhane": "#EF4444",
    "salle_rayhane":    "#22C55E",
}

R = {"sm": 6, "md": 9, "lg": 13, "xl": 18, "full": 999}
SP = {"xs": 4, "sm": 8, "md": 12, "lg": 18, "xl": 26}


def _pick_family():
    """Choisit la meilleure police disponible sans dépendance externe."""
    try:
        fams = set(tkfont.families())
    except Exception:
        fams = set()
    for f in ("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text",
              "Helvetica Neue", "DejaVu Sans", "Arial"):
        if f in fams:
            return f
    return "TkDefaultFont"


FAMILY = None   # rempli par install_theme()
F = {}          # rempli par install_theme()


def _build_fonts():
    global FAMILY, F
    FAMILY = _pick_family()
    mono = "Cascadia Mono" if "Cascadia Mono" in set(tkfont.families()) else "Consolas"
    F.update({
        "xs":       (FAMILY, 8),
        "sm":       (FAMILY, 9),
        "default":  (FAMILY, 10),
        "md":       (FAMILY, 11),
        "bold":     (FAMILY, 10, "bold"),
        "sm_bold":  (FAMILY, 9, "bold"),
        "xs_bold":  (FAMILY, 8, "bold"),
        "section":  (FAMILY, 11, "bold"),
        "title":    (FAMILY, 16, "bold"),
        "h1":       (FAMILY, 21, "bold"),
        "id":       (FAMILY, 19, "bold"),
        "nav":      (FAMILY, 10),
        "nav_b":    (FAMILY, 10, "bold"),
        "mono":     (mono, 10),
        "kpi":      (FAMILY, 22, "bold"),
    })
    return F


# ═══════════════════════════════════════════════════════════════════
#  COULEURS & ANIMATION
# ═══════════════════════════════════════════════════════════════════
def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb2hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def lerp(c1, c2, t):
    """Interpolation linéaire entre deux couleurs hex. t ∈ [0,1]."""
    a, b = _hex2rgb(c1), _hex2rgb(c2)
    return _rgb2hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def mix(color, other, amount):
    return lerp(color, other, amount)


def lighten(color, amount=0.85):
    return lerp(color, "#FFFFFF", amount)


def darken(color, amount=0.15):
    return lerp(color, "#000000", amount)


def _ease(t):
    """ease-out cubic — la courbe utilisée par la plupart des UI web."""
    return 1 - (1 - t) ** 3


def anim(widget, apply_fn, steps=8, delay=14):
    """Anime `apply_fn(t)` de t=0 à t=1 en `steps` images (ease-out).

    Chaque nouvelle animation sur le même widget annule la précédente,
    ce qui évite les scintillements quand la souris passe vite.
    """
    prev = getattr(widget, "_anim_job", None)
    if prev:
        try:
            widget.after_cancel(prev)
        except Exception:
            pass

    def step(i):
        if not widget.winfo_exists():
            return
        t = _ease(i / steps)
        try:
            apply_fn(t)
        except tk.TclError:
            return
        if i < steps:
            widget._anim_job = widget.after(delay, step, i + 1)
        else:
            widget._anim_job = None

    step(0)


# ═══════════════════════════════════════════════════════════════════
#  THÈME TTK
# ═══════════════════════════════════════════════════════════════════
def install_theme(root=None):
    """Applique le thème ttk complet. À appeler une fois après tk.Tk()."""
    _build_fonts()
    s = ttk.Style()
    s.theme_use("clam")

    s.configure(".", background=T["bg"], foreground=T["text"],
                font=F["default"], bordercolor=T["border"],
                focuscolor=T["primary"])

    # ── Frames & labels ───────────────────────────────────────────
    s.configure("TFrame", background=T["bg"])
    s.configure("Card.TFrame", background=T["surface"], relief="flat")
    s.configure("TLabelframe", background=T["surface"], bordercolor=T["border"],
                relief="solid", borderwidth=1)
    s.configure("TLabelframe.Label", background=T["surface"],
                foreground=T["text"], font=F["section"])
    s.configure("TLabel", background=T["bg"], foreground=T["text"], font=F["default"])
    for name, fg, bg, fnt in (
            ("Title", T["text"], T["bg"], F["title"]),
            ("Section", T["text"], T["surface"], F["section"]),
            ("Muted", T["text_m"], T["bg"], F["sm"]),
            ("ID", T["primary"], T["bg"], F["id"]),
            ("Success", T["success"], T["bg"], F["bold"]),
            ("Danger", T["danger"], T["bg"], F["bold"]),
            ("Warning", T["warning"], T["bg"], F["bold"]),
            ("Card", T["text"], T["surface"], F["default"]),
            ("CardMuted", T["text_m"], T["surface"], F["sm"])):
        s.configure(f"{name}.TLabel", foreground=fg, background=bg, font=fnt)

    # ── Entry / Combobox / Spinbox ────────────────────────────────
    for st in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(st, fieldbackground=T["surface"], background=T["surface"],
                    bordercolor=T["border"], lightcolor=T["border"],
                    darkcolor=T["border"], insertcolor=T["text"],
                    arrowcolor=T["text_m"], padding=(10, 7), font=F["default"],
                    relief="flat")
        s.map(st,
              bordercolor=[("focus", T["primary"]), ("hover", T["border_s"])],
              lightcolor=[("focus", T["primary"])],
              darkcolor=[("focus", T["primary"])],
              fieldbackground=[("readonly", T["surface_2"]),
                               ("disabled", T["surface_2"])],
              foreground=[("disabled", T["text_d"])],
              arrowcolor=[("hover", T["primary"])])
    root and root.option_add("*TCombobox*Listbox.background", T["surface"])
    root and root.option_add("*TCombobox*Listbox.foreground", T["text"])
    root and root.option_add("*TCombobox*Listbox.selectBackground", T["primary"])
    root and root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root and root.option_add("*TCombobox*Listbox.font", F["default"])
    root and root.option_add("*TCombobox*Listbox.borderWidth", 0)

    # ── Boutons ttk (conservés pour compatibilité) ────────────────
    variants = {
        "TButton":          (T["primary"], T["primary_d"], "white", F["bold"], (16, 8)),
        "Success.TButton":  (T["success"], T["success_d"], "white", F["bold"], (16, 8)),
        "Danger.TButton":   (T["danger"],  T["danger_d"],  "white", F["bold"], (16, 8)),
        "Sm.TButton":       (T["primary"], T["primary_d"], "white", F["sm_bold"], (11, 5)),
        "SmDanger.TButton": (T["danger"],  T["danger_d"],  "white", F["sm_bold"], (11, 5)),
    }
    for name, (bg, hover, fg, fnt, pad) in variants.items():
        s.configure(name, background=bg, foreground=fg, font=fnt, padding=pad,
                    relief="flat", borderwidth=0, focusthickness=0)
        s.map(name, background=[("pressed", darken(hover, .08)), ("active", hover)],
              foreground=[("active", fg), ("disabled", T["text_d"])])
    s.configure("Secondary.TButton", background=T["surface"], foreground=T["text"],
                font=F["bold"], padding=(16, 8), relief="solid", borderwidth=1,
                bordercolor=T["border_s"])
    s.map("Secondary.TButton", background=[("active", T["surface_2"])],
          bordercolor=[("active", T["border_s"])])

    # ── Checkbutton / Radiobutton ─────────────────────────────────
    for st in ("TCheckbutton", "TRadiobutton"):
        s.configure(st, background=T["surface"], foreground=T["text"],
                    font=F["default"], focuscolor=T["surface"],
                    indicatorcolor=T["surface"], bordercolor=T["border_s"])
        s.map(st, indicatorcolor=[("selected", T["primary"]),
                                  ("pressed", T["primary_d"])],
              foreground=[("disabled", T["text_d"])])

    # ── Treeview — présent dans presque tous les onglets ──────────
    s.configure("Treeview",
                background=T["surface"], fieldbackground=T["surface"],
                foreground=T["text"], font=F["default"], rowheight=34,
                bordercolor=T["border"], borderwidth=0, relief="flat")
    s.configure("Treeview.Heading",
                background=T["surface_2"], foreground=T["text_m"],
                font=F["sm_bold"], relief="flat", padding=(10, 9),
                bordercolor=T["border"], borderwidth=0)
    s.map("Treeview",
          background=[("selected", T["primary_l"])],
          foreground=[("selected", T["primary_d"])])
    s.map("Treeview.Heading",
          background=[("active", T["surface_3"])],
          foreground=[("active", T["text"])])
    s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    # ── Scrollbars fines ──────────────────────────────────────────
    for orient in ("Vertical", "Horizontal"):
        s.configure(f"{orient}.TScrollbar", background=T["border_s"],
                    troughcolor=T["bg"], bordercolor=T["bg"],
                    arrowcolor=T["bg"], darkcolor=T["bg"], lightcolor=T["bg"],
                    width=9, arrowsize=0, relief="flat")
        s.map(f"{orient}.TScrollbar", background=[("active", T["text_d"])])
    s.layout("Vertical.TScrollbar",
             [("Vertical.Scrollbar.trough",
               {"children": [("Vertical.Scrollbar.thumb",
                              {"expand": "1", "sticky": "nswe"})],
                "sticky": "ns"})])
    s.layout("Horizontal.TScrollbar",
             [("Horizontal.Scrollbar.trough",
               {"children": [("Horizontal.Scrollbar.thumb",
                              {"expand": "1", "sticky": "nswe"})],
                "sticky": "ew"})])

    s.configure("Horizontal.TProgressbar", background=T["primary"],
                troughcolor=T["surface_3"], borderwidth=0, thickness=6)
    s.configure("TNotebook", background=T["bg"], borderwidth=0)
    s.configure("TNotebook.Tab", background=T["bg"], foreground=T["bg"],
                font=F["sm"], padding=[0, 0])
    s.configure("TSeparator", background=T["border"])
    return s


def zebra(tree):
    """Active les lignes alternées + le survol sur un Treeview."""
    tree.tag_configure("odd", background=T["surface"])
    tree.tag_configure("even", background="#FAFBFD")
    tree.tag_configure("muted", foreground=T["text_d"])
    tree.tag_configure("ok", foreground=T["success"])
    tree.tag_configure("ko", foreground=T["danger"])

    def restripe(_=None):
        for i, iid in enumerate(tree.get_children()):
            tags = [t for t in tree.item(iid, "tags") if t not in ("odd", "even")]
            tree.item(iid, tags=tags + ["even" if i % 2 else "odd"])
    tree.restripe = restripe
    return tree


# ═══════════════════════════════════════════════════════════════════
#  PRIMITIVES DE DESSIN
# ═══════════════════════════════════════════════════════════════════
def round_rect(cv, x1, y1, x2, y2, r, **kw):
    """Rectangle à coins arrondis sur un Canvas (polygone lissé)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
           x1 + r, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


# ═══════════════════════════════════════════════════════════════════
#  BUTTON
# ═══════════════════════════════════════════════════════════════════
class Button(tk.Canvas):
    """Bouton arrondi animé. Variantes : primary, secondary, ghost,
    success, danger, warning, violon."""

    VARIANTS = {
        "primary":   dict(bg=T["primary"], fg="white",      bd=None),
        "success":   dict(bg=T["success"], fg="white",      bd=None),
        "danger":    dict(bg=T["danger"],  fg="white",      bd=None),
        "warning":   dict(bg=T["warning"], fg="white",      bd=None),
        "violon":    dict(bg=T["violon"],  fg="white",      bd=None),
        "secondary": dict(bg=T["surface"], fg=T["text"],    bd=T["border_s"]),
        "ghost":     dict(bg=None,         fg=T["text_m"],  bd=None),
        "soft":      dict(bg=T["primary_l"], fg=T["primary_d"], bd=None),
    }

    def __init__(self, parent, text, command=None, variant="primary",
                 icon=None, size="md", width=None, radius=None,
                 font=None, state="normal", **kw):
        self._surface = kw.pop("surface", None) or _parent_bg(parent)
        super().__init__(parent, bg=self._surface, highlightthickness=0,
                         bd=0, cursor="hand2", takefocus=1, **kw)
        v = self.VARIANTS.get(variant, self.VARIANTS["primary"])
        self._variant = variant
        self._base = v["bg"] or self._surface
        self._fg = v["fg"]
        self._bd = v["bd"]
        self._cmd = command
        self._icon = icon
        self._text = text
        self._state = state
        self._hovering = False

        px, py, fnt = {"sm": (12, 6, F["sm_bold"]),
                       "md": (18, 9, F["bold"]),
                       "lg": (24, 12, F["md"])}.get(size, (18, 9, F["bold"]))
        self._font = font or fnt
        self._px, self._py = px, py
        self._radius = radius if radius is not None else R["md"]
        self._cur = self._base

        w, h = self._measure()
        self.configure(width=width or w, height=h)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<space>", lambda e: self.invoke())
        self._draw()

    # ── géométrie ─────────────────────────────────────────────────
    @property
    def label(self):
        return f"{self._icon}  {self._text}" if self._icon else self._text

    def _measure(self):
        f = tkfont.Font(font=self._font)
        return (f.measure(self.label) + self._px * 2,
                f.metrics("linespace") + self._py * 2)

    def _hover_color(self):
        if self._variant == "secondary":
            return T["surface_2"]
        if self._variant == "ghost":
            return T["surface_2"]
        if self._variant == "soft":
            return T["primary_b"]
        return darken(self._base, 0.12)

    # ── rendu ─────────────────────────────────────────────────────
    def _draw(self, fill=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        disabled = self._state == "disabled"
        fill = fill or self._cur
        if disabled:
            fill = T["surface_2"]
        fg = T["text_d"] if disabled else self._fg

        if self._variant == "ghost" and not self._hovering and not disabled:
            fill = self._surface

        # Ombre portée douce (uniquement variantes pleines, au repos)
        if self._variant in ("primary", "success", "danger", "warning", "violon") \
                and not disabled:
            round_rect(self, 1, 3, w - 1, h, self._radius,
                       fill=lerp(self._surface, self._base, .22), outline="")

        round_rect(self, 0, 0, w - 1, h - 3, self._radius, fill=fill,
                   outline=self._bd or fill, width=1 if self._bd else 1)
        self.create_text(w / 2, (h - 3) / 2, text=self.label, fill=fg,
                         font=self._font, anchor="center")

    def _animate_to(self, target):
        start = self._cur

        def apply(t):
            self._cur = lerp(start, target, t)
            self._draw()
        anim(self, apply, steps=6, delay=12)

    # ── événements ────────────────────────────────────────────────
    def _enter(self, _=None):
        if self._state == "disabled":
            return
        self._hovering = True
        self._animate_to(self._hover_color())

    def _leave(self, _=None):
        self._hovering = False
        if self._state == "disabled":
            return
        self._animate_to(self._base)

    def _press(self, _=None):
        if self._state == "disabled":
            return
        self._cur = darken(self._hover_color(), .1)
        self._draw()

    def _release(self, _=None):
        if self._state == "disabled":
            return
        self._animate_to(self._hover_color() if self._hovering else self._base)
        if self._cmd:
            self._cmd()

    def invoke(self):
        if self._state != "disabled" and self._cmd:
            self._cmd()

    # ── API ───────────────────────────────────────────────────────
    def configure(self, **kw):
        redraw = False
        if "text" in kw:
            self._text = kw.pop("text"); redraw = True
        if "icon" in kw:
            self._icon = kw.pop("icon"); redraw = True
        if "command" in kw:
            self._cmd = kw.pop("command")
        if "state" in kw:
            self._state = kw.pop("state")
            self.configure_cursor()
            redraw = True
        if "fg" in kw:
            self._fg = kw.pop("fg"); redraw = True
        if kw:
            super().configure(**kw)
        if redraw:
            self._cur = self._base
            self._draw()
    config = configure

    def configure_cursor(self):
        try:
            super().configure(cursor="" if self._state == "disabled" else "hand2")
        except tk.TclError:
            pass


def _parent_bg(w):
    try:
        return w.cget("bg")
    except Exception:
        try:
            return ttk.Style().lookup(w.winfo_class(), "background") or T["surface"]
        except Exception:
            return T["surface"]


# ═══════════════════════════════════════════════════════════════════
#  ENTRY
# ═══════════════════════════════════════════════════════════════════
class Entry(tk.Frame):
    """Champ de saisie avec anneau de focus animé, placeholder et état d'erreur."""

    def __init__(self, parent, width=None, justify="left", font=None,
                 state="normal", textvariable=None, placeholder="",
                 surface=None, **kw):
        self._surface = surface or _parent_bg(parent)
        super().__init__(parent, bg=T["border"], padx=1, pady=1)
        self._inner = tk.Frame(self, bg=T["surface"])
        self._inner.pack(fill="both", expand=True)
        self._entry = tk.Entry(
            self._inner, relief="flat", bg=T["surface"], fg=T["text"],
            insertbackground=T["primary"], insertwidth=2,
            font=font or F["default"], justify=justify,
            highlightthickness=0, bd=0, selectbackground=T["primary_b"],
            selectforeground=T["text"])
        if textvariable:
            self._entry.configure(textvariable=textvariable)
        if width:
            self._entry.configure(width=width)
        self._entry.pack(fill="both", expand=True, padx=9, pady=7)

        self._placeholder = placeholder
        self._ph_on = False
        self._error = False
        self._entry.bind("<FocusIn>", self._focus_in, add="+")
        self._entry.bind("<FocusOut>", self._focus_out, add="+")
        if placeholder:
            self._show_ph()

        self.set_state(state)

    # ── anneau de focus ───────────────────────────────────────────
    def _ring(self, color):
        def apply(t):
            self.configure(bg=lerp(self.cget("bg"), color, t if t else 1))
        try:
            anim(self, lambda t: super(Entry, self).configure(
                bg=lerp(self._ring_from, color, t)), steps=5, delay=10)
        except Exception:
            super().configure(bg=color)

    def _focus_in(self, _=None):
        if self._ph_on:
            self._hide_ph()
        self._ring_from = self.cget("bg")
        self._ring(T["danger"] if self._error else T["primary"])

    def _focus_out(self, _=None):
        self._ring_from = self.cget("bg")
        self._ring(T["danger"] if self._error else T["border"])
        if self._placeholder and not self._entry.get().strip():
            self._show_ph()

    def _show_ph(self):
        self._ph_on = True
        self._entry.configure(fg=T["text_d"])
        self._entry.delete(0, "end")
        self._entry.insert(0, self._placeholder)

    def _hide_ph(self):
        self._ph_on = False
        self._entry.delete(0, "end")
        self._entry.configure(fg=T["text"])

    # ── API ───────────────────────────────────────────────────────
    def set_error(self, on=True):
        self._error = bool(on)
        super().configure(bg=T["danger"] if on else T["border"])
        self._inner.configure(bg=T["danger_l"] if on else T["surface"])
        self._entry.configure(bg=T["danger_l"] if on else T["surface"])

    def set_state(self, state):
        if state == "readonly":
            self._entry.configure(state="readonly", readonlybackground=T["surface_2"])
            self._inner.configure(bg=T["surface_2"])
        elif state == "disabled":
            self._entry.configure(state="disabled", disabledbackground=T["surface_2"],
                                  disabledforeground=T["text_d"])
            self._inner.configure(bg=T["surface_2"])
        else:
            self._entry.configure(state="normal", bg=T["surface"])
            self._inner.configure(bg=T["surface"])

    def get(self):
        return "" if self._ph_on else self._entry.get()

    def delete(self, *a):
        if self._ph_on:
            self._hide_ph()
            return
        self._entry.delete(*a)

    def insert(self, *a):
        if self._ph_on:
            self._hide_ph()
        self._entry.insert(*a)

    def bind(self, *a, **kw):
        return self._entry.bind(*a, **kw)

    def focus_set(self):
        self._entry.focus_set()

    @property
    def entry(self):
        return self._entry

    def configure(self, **kw):
        entry_keys = {"font", "justify", "textvariable", "show",
                      "disabledforeground", "readonlybackground"}
        if "state" in kw:
            self.set_state(kw.pop("state"))
        ekw = {k: kw.pop(k) for k in list(kw) if k in entry_keys}
        if ekw:
            self._entry.configure(**ekw)
        if kw:
            super().configure(**kw)
    config = configure


# ═══════════════════════════════════════════════════════════════════
#  CARD
# ═══════════════════════════════════════════════════════════════════
class Card(tk.Frame):
    """Carte blanche : bordure fine, ombre douce, en-tête optionnel.

    `body` est le conteneur où placer le contenu.
    """

    def __init__(self, parent, title="", subtitle="", icon="", accent=None,
                 padding=SP["lg"], **kw):
        surface = kw.pop("surface", None) or _parent_bg(parent)
        super().__init__(parent, bg=surface, **kw)

        shadow = tk.Frame(self, bg=T["shadow"])
        shadow.pack(fill="both", expand=True, padx=(1, 0), pady=(2, 0))
        shell = tk.Frame(shadow, bg=T["border"])
        shell.pack(fill="both", expand=True, padx=(0, 1), pady=(0, 2))
        card = tk.Frame(shell, bg=T["surface"])
        card.pack(fill="both", expand=True, padx=1, pady=1)
        self._card = card

        pad = max(padding, 0)
        hpad = max(pad, 14)          # marge minimale de l'en-tête
        if title:
            head = tk.Frame(card, bg=T["surface"])
            head.pack(fill="x", padx=hpad, pady=(max(hpad - 2, 0), 0))
            if accent:
                tk.Frame(head, bg=accent, width=3, height=20).pack(
                    side="left", padx=(0, 9))
            txt = tk.Frame(head, bg=T["surface"])
            txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=f"{icon}  {title}" if icon else title,
                     bg=T["surface"], fg=T["text"], font=F["section"],
                     anchor="w").pack(anchor="w")
            if subtitle:
                tk.Label(txt, text=subtitle, bg=T["surface"], fg=T["text_m"],
                         font=F["sm"], anchor="w").pack(anchor="w", pady=(1, 0))
            self.head = head
            tk.Frame(card, bg=T["border"], height=1).pack(
                fill="x", padx=hpad, pady=(max(hpad - 4, 0), 0))

        self.body = tk.Frame(card, bg=T["surface"])
        self.body.pack(fill="both", expand=True, padx=pad,
                       pady=(max(pad - 4, 0) if title else pad, pad))


# ═══════════════════════════════════════════════════════════════════
#  CHIP
# ═══════════════════════════════════════════════════════════════════
TONES = {
    "neutral": (T["surface_2"], T["text_m"]),
    "primary": (T["primary_l"], T["primary_d"]),
    "success": (T["success_l"], T["success_d"]),
    "danger":  (T["danger_l"],  T["danger_d"]),
    "warning": (T["warning_l"], T["warning_d"]),
    "violon":  (T["violon_l"],  T["violon"]),
    "accent":  (T["accent_l"],  "#0369A1"),
}


class Chip(tk.Canvas):
    """Pastille de statut arrondie."""

    def __init__(self, parent, text, tone="neutral", dot=False, **kw):
        surface = kw.pop("surface", None) or _parent_bg(parent)
        self._bg, self._fg = TONES.get(tone, TONES["neutral"])
        self._text, self._dot = text, dot
        f = tkfont.Font(font=F["sm_bold"])
        pad = 11
        w = f.measure(text) + pad * 2 + (14 if dot else 0)
        h = f.metrics("linespace") + 9
        super().__init__(parent, bg=surface, highlightthickness=0, bd=0,
                         width=w, height=h, **kw)
        round_rect(self, 0, 0, w - 1, h - 1, h / 2, fill=self._bg, outline="")
        x = pad
        if dot:
            cy = h / 2
            self.create_oval(x, cy - 3, x + 6, cy + 3, fill=self._fg, outline="")
            x += 12
        self.create_text(x, h / 2, text=text, fill=self._fg, font=F["sm_bold"],
                         anchor="w")


def chip(parent, text, tone="neutral", dot=False, **kw):
    return Chip(parent, text, tone, dot, **kw)


# ═══════════════════════════════════════════════════════════════════
#  SWITCH
# ═══════════════════════════════════════════════════════════════════
class Switch(tk.Canvas):
    """Interrupteur animé lié à une BooleanVar/IntVar."""
    W, H = 42, 23

    def __init__(self, parent, variable=None, command=None, color=None, **kw):
        surface = kw.pop("surface", None) or _parent_bg(parent)
        super().__init__(parent, bg=surface, highlightthickness=0, bd=0,
                         width=self.W, height=self.H, cursor="hand2", **kw)
        self.var = variable or tk.BooleanVar(value=False)
        self._cmd = command
        self._on_color = color or T["primary"]
        self._pos = 1.0 if self.var.get() else 0.0
        self.bind("<Button-1>", self._toggle)
        try:
            self.var.trace_add("write", lambda *a: self._sync())
        except AttributeError:
            self.var.trace("w", lambda *a: self._sync())
        self._render()

    def _render(self):
        self.delete("all")
        track = lerp(T["surface_3"], self._on_color, self._pos)
        round_rect(self, 0, 0, self.W - 1, self.H - 1, self.H / 2,
                   fill=track, outline="")
        r = (self.H - 6) / 2
        cx = 3 + r + self._pos * (self.W - 6 - 2 * r)
        cy = self.H / 2
        self.create_oval(cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1,
                         fill=lerp(track, "#000000", .08), outline="")
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill="white", outline="")

    def _sync(self):
        target = 1.0 if self.var.get() else 0.0
        if abs(target - self._pos) < 0.01:
            return
        start = self._pos

        def apply(t):
            self._pos = start + (target - start) * t
            self._render()
        anim(self, apply, steps=8, delay=12)

    def _toggle(self, _=None):
        self.var.set(not bool(self.var.get()))
        if self._cmd:
            self._cmd()


def switch_row(parent, label, variable, command=None, hint="", color=None,
               surface=None):
    """Ligne « libellé + interrupteur » alignée à droite."""
    bg = surface or _parent_bg(parent)
    row = tk.Frame(parent, bg=bg)
    txt = tk.Frame(row, bg=bg)
    txt.pack(side="left", fill="x", expand=True)
    tk.Label(txt, text=label, bg=bg, fg=T["text"], font=F["default"],
             anchor="w").pack(anchor="w")
    if hint:
        tk.Label(txt, text=hint, bg=bg, fg=T["text_m"], font=F["xs"],
                 anchor="w").pack(anchor="w")
    sw = Switch(row, variable=variable, command=command, color=color, surface=bg)
    sw.pack(side="right", padx=(10, 0))
    row.switch = sw
    return row


# ═══════════════════════════════════════════════════════════════════
#  SEGMENTED CONTROL
# ═══════════════════════════════════════════════════════════════════
class SegmentedControl(tk.Frame):
    """Sélecteur segmenté (type iOS / shadcn Tabs)."""

    def __init__(self, parent, options, variable=None, command=None,
                 font=None, pad=13, **kw):
        surface = kw.pop("surface", None) or _parent_bg(parent)
        super().__init__(parent, bg=T["surface_2"], padx=3, pady=3, **kw)
        self.var = variable or tk.StringVar(value=options[0][0] if options else "")
        self._cmd = command
        self._btns = {}
        f = font or F["sm_bold"]
        for value, label in options:
            b = tk.Label(self, text=label, font=f, padx=pad, pady=6,
                         cursor="hand2", bd=0)
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, v=value: self.select(v))
            self._btns[value] = b
        self._paint()

    def _paint(self):
        cur = self.var.get()
        for v, b in self._btns.items():
            if v == cur:
                b.configure(bg=T["surface"], fg=T["primary_d"])
            else:
                b.configure(bg=T["surface_2"], fg=T["text_m"])

    def select(self, value):
        self.var.set(value)
        self._paint()
        if self._cmd:
            self._cmd(value)


# ═══════════════════════════════════════════════════════════════════
#  TOAST
# ═══════════════════════════════════════════════════════════════════
class _ToastHost:
    """Pile de notifications ancrée en haut à droite de la fenêtre."""

    def __init__(self, root):
        self.root = root
        self.items = []

    def show(self, message, tone="success", title=None, duration=4200):
        bg, fg = {"success": (T["success_l"], T["success_d"]),
                  "danger":  (T["danger_l"],  T["danger_d"]),
                  "warning": (T["warning_l"], T["warning_d"]),
                  "info":    (T["primary_l"], T["primary_d"])}.get(
            tone, (T["primary_l"], T["primary_d"]))
        icon = {"success": "✓", "danger": "✕", "warning": "!",
                "info": "i"}.get(tone, "i")

        wrap = tk.Frame(self.root, bg=T["shadow_s"])
        shell = tk.Frame(wrap, bg=fg)
        shell.pack(fill="both", expand=True, padx=(0, 1), pady=(0, 1))
        body = tk.Frame(shell, bg=bg)
        body.pack(fill="both", expand=True, padx=(4, 1), pady=1)

        inner = tk.Frame(body, bg=bg, padx=14, pady=11)
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=icon, bg=bg, fg=fg,
                 font=(FAMILY, 12, "bold")).pack(side="left", padx=(0, 10))
        txt = tk.Frame(inner, bg=bg)
        txt.pack(side="left", fill="x", expand=True)
        if title:
            tk.Label(txt, text=title, bg=bg, fg=fg, font=F["bold"],
                     anchor="w", justify="left").pack(anchor="w")
        tk.Label(txt, text=message, bg=bg, fg=darken(fg, .05), font=F["sm"],
                 anchor="w", justify="left", wraplength=310).pack(anchor="w")
        close = tk.Label(inner, text="✕", bg=bg, fg=T["text_d"],
                         font=F["sm"], cursor="hand2")
        close.pack(side="right", padx=(10, 0))
        close.bind("<Button-1>", lambda e: self._dismiss(wrap))

        self.items.append(wrap)
        self._layout()
        wrap.lift()

        def slide(t):
            wrap.place_configure(x=int(-20 + (1 - t) * 380))
        anim(wrap, slide, steps=12, delay=13)
        if duration:
            wrap.after(duration, lambda: self._dismiss(wrap))
        return wrap

    def _layout(self):
        y = 18
        for w in self.items:
            w.place(relx=1.0, x=380, y=y, anchor="ne")
            w.update_idletasks()
            y += w.winfo_reqheight() + 10

    def _dismiss(self, w):
        if w not in self.items:
            return
        self.items.remove(w)

        def slide(t):
            if w.winfo_exists():
                w.place_configure(x=int(-20 + t * 400))
        anim(w, slide, steps=9, delay=12)
        w.after(140, lambda: (w.winfo_exists() and w.destroy(), self._layout()))


_host = None


def init_toasts(root):
    global _host
    _host = _ToastHost(root)
    return _host


def toast(message, tone="success", title=None, duration=4200):
    """Notification non bloquante. Sans hôte initialisé, ne fait rien."""
    if _host is None:
        return None
    try:
        return _host.show(message, tone, title, duration)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
#  EMPTY STATE / STAT TILE
# ═══════════════════════════════════════════════════════════════════
def empty_state(parent, icon="🗂", title="Rien à afficher", hint="",
                surface=None):
    bg = surface or _parent_bg(parent)
    f = tk.Frame(parent, bg=bg, pady=34)
    tk.Label(f, text=icon, bg=bg, fg=T["text_d"],
             font=(FAMILY, 32)).pack()
    tk.Label(f, text=title, bg=bg, fg=T["text"], font=F["bold"]).pack(pady=(8, 2))
    if hint:
        tk.Label(f, text=hint, bg=bg, fg=T["text_m"], font=F["sm"],
                 wraplength=340, justify="center").pack()
    return f


class StatTile(tk.Frame):
    """Tuile de chiffre clé (KPI)."""

    def __init__(self, parent, label, value, tone="primary", icon="", hint="", **kw):
        surface = kw.pop("surface", None) or _parent_bg(parent)
        super().__init__(parent, bg=surface, **kw)
        bg, fg = TONES.get(tone, TONES["primary"])
        shell = tk.Frame(self, bg=T["border"])
        shell.pack(fill="both", expand=True)
        card = tk.Frame(shell, bg=T["surface"], padx=16, pady=13)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        top = tk.Frame(card, bg=T["surface"])
        top.pack(fill="x")
        tk.Label(top, text=label.upper(), bg=T["surface"], fg=T["text_m"],
                 font=F["xs_bold"], anchor="w").pack(side="left")
        if icon:
            badge = tk.Frame(top, bg=bg, padx=6, pady=2)
            badge.pack(side="right")
            tk.Label(badge, text=icon, bg=bg, fg=fg, font=F["sm"]).pack()
        self.value_lbl = tk.Label(card, text=value, bg=T["surface"],
                                  fg=T["text"], font=F["kpi"], anchor="w")
        self.value_lbl.pack(anchor="w", pady=(6, 0))
        if hint:
            tk.Label(card, text=hint, bg=T["surface"], fg=T["text_m"],
                     font=F["xs"], anchor="w").pack(anchor="w")

    def set(self, value):
        self.value_lbl.configure(text=value)


# ═══════════════════════════════════════════════════════════════════
#  DIVERS
# ═══════════════════════════════════════════════════════════════════
def divider(parent, padx=0, pady=(8, 8), surface=None):
    tk.Frame(parent, bg=T["border"], height=1).pack(fill="x", padx=padx, pady=pady)


def field(parent, label, hint="", width=None, surface=None, placeholder="",
          **kw):
    """Bloc « libellé + champ » vertical. Retourne (frame, Entry)."""
    bg = surface or _parent_bg(parent)
    fr = tk.Frame(parent, bg=bg)
    tk.Label(fr, text=label, bg=bg, fg=T["text_m"], font=F["sm_bold"],
             anchor="w").pack(anchor="w", pady=(0, 4))
    e = Entry(fr, width=width, placeholder=placeholder, surface=bg, **kw)
    e.pack(fill="x")
    if hint:
        tk.Label(fr, text=hint, bg=bg, fg=T["text_d"], font=F["xs"],
                 anchor="w").pack(anchor="w", pady=(3, 0))
    return fr, e


def scrollable(parent, bg=None):
    """Zone scrollable verticale. Retourne (outer, inner)."""
    bg = bg or T["bg"]
    outer = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, bd=0, highlightthickness=0)
    vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=bg)
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

    def wheel(e):
        if canvas.winfo_exists() and outer.winfo_ismapped():
            canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", wheel, add="+")
    return outer, inner
