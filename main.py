"""
main.py — Point d'entrée. Lance : python main.py
"""
from login_window import show_login
from gui import run

if __name__ == "__main__":
    # Afficher la fenêtre de login
    user = show_login()
    
    # Si l'utilisateur s'est connecté, lancer l'application
    if user:
        run(user)
    else:
        print("Connexion annulée")
