"""
login_window.py — Fenêtre de connexion avec authentification
"""
import tkinter as tk
from tkinter import ttk, messagebox
import access_control

# Palette de couleurs (même que gui.py)
C = {
    "bg":         "#F0F4F8",
    "surface":    "#FFFFFF",
    "sidebar":    "#1A2B45",
    "sidebar_h":  "#243D60",
    "primary":    "#2563EB",
    "primary_d":  "#1D4ED8",
    "accent":     "#0EA5E9",
    "success":    "#16A34A",
    "danger":     "#DC2626",
    "text":       "#1E293B",
    "text_m":     "#64748B",
    "border":     "#E2E8F0",
}

FNT = {
    "default":  ("Segoe UI", 10),
    "sm":       ("Segoe UI", 9),
    "bold":     ("Segoe UI", 10, "bold"),
    "title":    ("Segoe UI", 18, "bold"),
    "large":    ("Segoe UI", 24, "bold"),
}


class RoundedEntry(tk.Frame):
    """Entry avec bordure arrondie (même que gui.py)."""
    def __init__(self, parent, bg_canvas=None, width=None, show=None, **kw):
        self._bg_canvas = bg_canvas or C["surface"]
        super().__init__(parent, bg=self._bg_canvas,
                         highlightthickness=1,
                         highlightbackground=C["border"],
                         highlightcolor=C["primary"])
        
        entry_args = {"relief": "flat", "bg": C["surface"],
                      "fg": C["text"], "insertbackground": C["text"],
                      "font": FNT["default"], "highlightthickness": 0, "bd": 0}
        if show:
            entry_args["show"] = show
        if width:
            entry_args["width"] = width
        
        self._entry = tk.Entry(self, **entry_args)
        self._entry.pack(fill="both", expand=True, padx=6, pady=5)
        
        self._entry.bind("<FocusIn>", lambda e: self.configure(
            highlightbackground=C["primary"], highlightcolor=C["primary"]))
        self._entry.bind("<FocusOut>", lambda e: self.configure(
            highlightbackground=C["border"], highlightcolor=C["border"]))
    
    def get(self):
        return self._entry.get()
    
    def delete(self, *a):
        self._entry.delete(*a)
    
    def insert(self, *a):
        self._entry.insert(*a)
    
    def bind(self, *a, **kw):
        return self._entry.bind(*a, **kw)
    
    def focus(self):
        self._entry.focus()


class LoginWindow(tk.Tk):
    """Fenêtre de connexion."""
    
    def __init__(self):
        super().__init__()
        self.title("Marassim — Connexion")
        self.resizable(True, True)
        self.configure(bg=C["bg"])
        self.minsize(380, 480)
        
        self.current_user = None
        
        # Taille relative à l'écran (40% largeur, 70% hauteur, min 480x580)
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = max(480, min(560, int(sw * 0.35)))
        h = max(560, min(680, int(sh * 0.75)))
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        self._build_ui()
    
    def _build_ui(self):
        # Root grid — header fixed, form expands
        self.rowconfigure(0, weight=0)  # header
        self.rowconfigure(1, weight=1)  # form
        self.columnconfigure(0, weight=1)

        # ── Header ───────────────────────────────────────────────
        header = tk.Frame(self, bg=C["sidebar"])
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        tk.Label(header, text="🏛", bg=C["sidebar"], fg="white",
                 font=("Segoe UI", 36)).pack(pady=(28, 8))
        tk.Label(header, text="MARASSIM", bg=C["sidebar"], fg="white",
                 font=FNT["large"]).pack()
        tk.Label(header, text="Système de gestion des réservations",
                 bg=C["sidebar"], fg="#94A3B8",
                 font=("Segoe UI", 9)).pack(pady=(5, 28))

        # ── Formulaire de connexion ──────────────────────────────
        form_outer = tk.Frame(self, bg=C["bg"])
        form_outer.grid(row=1, column=0, sticky="nsew")
        form_outer.rowconfigure(0, weight=1)
        form_outer.columnconfigure(0, weight=1)

        # Centering wrapper
        center = tk.Frame(form_outer, bg=C["bg"])
        center.grid(row=0, column=0, sticky="nsew", padx=32, pady=24)
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=1)

        # Card
        card = tk.Frame(center, bg=C["surface"])
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        # Accent bar
        tk.Frame(card, bg=C["primary"], height=4).pack(fill="x")

        # Card content — uses pack with expand so it fills card height
        content = tk.Frame(card, bg=C["surface"])
        content.pack(fill="both", expand=True, padx=28, pady=24)
        content.columnconfigure(0, weight=1)

        tk.Label(content, text="Connexion", bg=C["surface"],
                 fg=C["primary"], font=FNT["title"]).pack(anchor="w")
        tk.Label(content, text="Entrez vos identifiants pour accéder au système",
                 bg=C["surface"], fg=C["text_m"],
                 font=FNT["sm"]).pack(anchor="w", pady=(4, 20))

        # Username
        tk.Label(content, text="Nom d'utilisateur", bg=C["surface"],
                 fg=C["text_m"], font=FNT["sm"]).pack(anchor="w")
        self.username_entry = RoundedEntry(content)
        self.username_entry.pack(fill="x", pady=(4, 14), ipady=4)

        # Password
        tk.Label(content, text="Mot de passe", bg=C["surface"],
                 fg=C["text_m"], font=FNT["sm"]).pack(anchor="w")
        self.password_entry = RoundedEntry(content, show="●")
        self.password_entry.pack(fill="x", pady=(4, 6), ipady=4)

        # Status message
        self.status_label = tk.Label(content, text="", bg=C["surface"],
                                     fg=C["danger"], font=FNT["sm"])
        self.status_label.pack(anchor="w", pady=(4, 18))

        # Login button — full width
        login_btn = tk.Button(
            content, text="Se connecter",
            bg=C["primary"], fg="white",
            activebackground=C["primary_d"],
            activeforeground="white",
            relief="flat", font=FNT["bold"],
            cursor="hand2", padx=20, pady=10,
            command=self._do_login
        )
        login_btn.pack(fill="x")

        # Bind Enter key to login
        self.username_entry.bind("<Return>", lambda e: self._do_login())
        self.password_entry.bind("<Return>", lambda e: self._do_login())

        # Info text
        tk.Label(
            content,
            text="Par défaut : admin / admin123",
            bg=C["surface"], fg=C["text_m"],
            font=("Segoe UI", 8)
        ).pack(pady=(14, 0))

        # Focus username
        self.username_entry.focus()
    
    def _do_login(self):
        """Tentative de connexion."""
        self.status_label.configure(text="", fg=C["danger"])
        
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            self.status_label.configure(text="⚠ Veuillez remplir tous les champs")
            return
        
        # Authentifier
        user = access_control.authenticate(username, password)
        
        if user:
            self.current_user = user
            self.destroy()  # Fermer la fenêtre de login
        else:
            self.status_label.configure(
                text="✘ Identifiants incorrects ou compte inactif"
            )
            self.password_entry.delete(0, "end")
            self.password_entry.focus()


def show_login() -> dict:
    """Affiche la fenêtre de login et retourne l'utilisateur connecté.
    Retourne None si la fenêtre est fermée sans connexion.
    """
    # Initialiser la base de données d'accès
    access_control.init_access_db()
    
    login_win = LoginWindow()
    login_win.mainloop()
    
    return login_win.current_user
