# -*- coding: utf-8 -*-
"""
main.py — Point d'entrée. Lance : python main.py

Avant d'ouvrir la fenêtre de connexion, vérifie que la base est joignable.
En multi-poste (PostgreSQL), le serveur peut être éteint ou le réseau coupé :
mieux vaut un message clair qu'une trace Python.
"""
import sys
import tkinter as tk
from tkinter import messagebox

import config
import db


def _erreur_connexion(message: str):
    """Fenêtre d'erreur lisible, avec la marche à suivre."""
    root = tk.Tk()
    root.withdraw()
    if config.is_postgres():
        detail = (
            f"Impossible de joindre le serveur de base de données.\n\n"
            f"Configuration ({config.INI_PATH}) :\n"
            f"    {config.describe()}\n\n"
            f"Détail technique :\n    {message}\n\n"
            f"À vérifier, dans cet ordre :\n"
            f"  1. Le PC serveur est-il allumé ?\n"
            f"  2. Ce poste est-il bien sur le réseau du complexe ?\n"
            f"  3. Le service PostgreSQL tourne-t-il sur le serveur ?\n"
            f"  4. L'adresse et le mot de passe dans marassim.ini sont-ils bons ?"
        )
    else:
        detail = (f"Impossible d'ouvrir la base locale.\n\n"
                  f"    {config.describe()}\n\n"
                  f"Détail technique :\n    {message}")
    messagebox.showerror("Marassim — base de données inaccessible", detail)
    root.destroy()


if __name__ == "__main__":
    ok, message = db.ping()
    if not ok:
        _erreur_connexion(message)
        sys.exit(1)

    from login_window import show_login
    from gui import run

    user = show_login()
    if user:
        run(user)
    else:
        print("Connexion annulée")
