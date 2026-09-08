"""
access_control.py — Module de gestion des accès avec authentification et contrôle des modules
"""
import sqlite3
import hashlib
import os

import db as _db
import config as _config

DB_PATH = _config.CONF["path"]   # compatibilité (mode SQLite local)

# ═══════════════════════════════════════════════════════════════════
#  SCHEMA & INITIALISATION
# ═══════════════════════════════════════════════════════════════════

SCHEMA_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nom TEXT NOT NULL,
    prenom TEXT,
    role TEXT NOT NULL,           -- 'admin' | 'manager' | 'employe'
    actif INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_MODULE_ACCESS = """
CREATE TABLE IF NOT EXISTS module_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    module_name TEXT NOT NULL,
    can_access INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, module_name)
);
"""

# Liste des modules disponibles dans l'application
ALL_MODULES = [
    "Nouvelle réservation",
    "Réservations",
    "Calendrier",
    "Ajouter un acompte",
    "Charges",
    "Charges Omar",
    "Journal de Caisse",
    "Journal Caisse Omar",
    "Modifier réservation",
    "Export Excel",
    "Ajouter employé",
    "Liste employés",
    "Pointage",
    "Centre de Réception",
    "Règles de réservation",
]


def get_connection():
    return _db.connect()


def init_access_db():
    """Initialise les tables d'accès et crée un utilisateur admin par défaut."""
    conn = get_connection()
    conn.execute(SCHEMA_USERS)
    conn.execute(SCHEMA_MODULE_ACCESS)
    conn.commit()
    
    # Vérifier si un admin existe déjà
    admin = conn.execute("SELECT * FROM users WHERE username=?", ("admin",)).fetchone()
    if not admin:
        # Créer un admin par défaut (username: admin, password: admin123)
        admin_id = create_user({
            "username": "admin",
            "password": "admin123",
            "nom": "Administrateur",
            "prenom": "Système",
            "role": "admin",
        })
        # Donner accès à tous les modules pour l'admin
        for module in ALL_MODULES:
            grant_module_access(admin_id, module)

    # Migration : les comptes admin existants reçoivent automatiquement
    # les modules ajoutés après leur création (ex: « Règles de réservation »).
    for row in conn.execute("SELECT id FROM users WHERE role='admin'").fetchall():
        have = {r["module_name"] for r in conn.execute(
            "SELECT module_name FROM module_access WHERE user_id=?", (row["id"],))}
        for module in ALL_MODULES:
            if module not in have:
                _db.upsert(conn, "module_access", ("user_id", "module_name"),
                           {"user_id": row["id"], "module_name": module,
                            "can_access": 1})
    conn.commit()

    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  GESTION DES UTILISATEURS
# ═══════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """Hash un mot de passe avec SHA256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def create_user(data: dict) -> int:
    """Crée un nouvel utilisateur.
    data doit contenir : username, password, nom, prenom (opt), role
    """
    conn = get_connection()
    
    try:
        # Hasher le mot de passe
        password_hash = hash_password(data["password"])
        
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, nom, prenom, role, actif) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (data["username"], password_hash, data["nom"], 
             data.get("prenom", ""), data["role"], 1)
        )
        conn.commit()
        user_id = cur.lastrowid
        return user_id
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict:
    """Authentifie un utilisateur.
    Retourne le dict de l'utilisateur si succès, None sinon.
    """
    conn = get_connection()
    password_hash = hash_password(password)
    
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=? AND actif=1",
        (username, password_hash)
    ).fetchone()
    
    conn.close()
    return dict(row) if row else None


def get_all_users(actif_only=True):
    """Récupère tous les utilisateurs."""
    conn = get_connection()
    if actif_only:
        rows = conn.execute("SELECT * FROM users WHERE actif=1 ORDER BY nom, prenom").fetchall()
    else:
        rows = conn.execute("SELECT * FROM users ORDER BY nom, prenom").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id: int) -> dict:
    """Récupère un utilisateur par son ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(user_id: int, data: dict):
    """Met à jour un utilisateur.
    Si data contient 'password', il sera hashé automatiquement.
    """
    conn = get_connection()
    
    # Si le mot de passe est dans les données, le hasher
    if "password" in data:
        data["password_hash"] = hash_password(data.pop("password"))
    
    sets = ", ".join(f"{k}=?" for k in data)
    conn.execute(f"UPDATE users SET {sets} WHERE id=?", list(data.values()) + [user_id])
    conn.commit()
    conn.close()


def delete_user(user_id: int):
    """Désactive un utilisateur (soft delete)."""
    conn = get_connection()
    conn.execute("UPDATE users SET actif=0 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """Change le mot de passe d'un utilisateur après vérification de l'ancien."""
    conn = get_connection()
    old_hash = hash_password(old_password)
    
    user = conn.execute(
        "SELECT * FROM users WHERE id=? AND password_hash=?",
        (user_id, old_hash)
    ).fetchone()
    
    if not user:
        conn.close()
        return False
    
    new_hash = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user_id))
    conn.commit()
    conn.close()
    return True


# ═══════════════════════════════════════════════════════════════════
#  GESTION DES ACCÈS AUX MODULES
# ═══════════════════════════════════════════════════════════════════

def grant_module_access(user_id: int, module_name: str):
    """Accorde l'accès à un module pour un utilisateur."""
    conn = get_connection()
    _db.upsert(conn, "module_access", ("user_id", "module_name"),
               {"user_id": user_id, "module_name": module_name, "can_access": 1})
    conn.commit()
    conn.close()


def revoke_module_access(user_id: int, module_name: str):
    """Révoque l'accès à un module pour un utilisateur."""
    conn = get_connection()
    _db.upsert(conn, "module_access", ("user_id", "module_name"),
               {"user_id": user_id, "module_name": module_name, "can_access": 0})
    conn.commit()
    conn.close()


def get_user_modules(user_id: int) -> list:
    """Récupère la liste des modules accessibles par un utilisateur."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT module_name FROM module_access "
        "WHERE user_id=? AND can_access=1 ORDER BY module_name",
        (user_id,)
    ).fetchall()
    conn.close()
    return [r["module_name"] for r in rows]


def get_all_user_module_permissions(user_id: int) -> dict:
    """Récupère tous les modules avec leur statut d'accès pour un utilisateur.
    Retourne un dict {module_name: bool}
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT module_name, can_access FROM module_access WHERE user_id=?",
        (user_id,)
    ).fetchall()
    conn.close()
    
    # Créer un dict avec tous les modules (par défaut False)
    perms = {module: False for module in ALL_MODULES}
    
    # Mettre à jour avec les permissions existantes
    for r in rows:
        if r["module_name"] in perms:
            perms[r["module_name"]] = bool(r["can_access"])
    
    return perms


def set_user_modules(user_id: int, modules: list):
    """Définit la liste complète des modules accessibles par un utilisateur.
    Les modules non listés seront révoqués.
    """
    conn = get_connection()
    
    # D'abord, révoquer tous les accès
    conn.execute("DELETE FROM module_access WHERE user_id=?", (user_id,))
    
    # Ensuite, accorder les nouveaux accès
    for module in modules:
        if module in ALL_MODULES:
            conn.execute(
                "INSERT INTO module_access (user_id, module_name, can_access) "
                "VALUES (?, ?, 1)",
                (user_id, module)
            )
    
    conn.commit()
    conn.close()


def can_access_module(user_id: int, module_name: str) -> bool:
    """Vérifie si un utilisateur a accès à un module spécifique."""
    conn = get_connection()
    row = conn.execute(
        "SELECT can_access FROM module_access "
        "WHERE user_id=? AND module_name=?",
        (user_id, module_name)
    ).fetchone()
    conn.close()
    
    if row:
        return bool(row["can_access"])
    return False


# ═══════════════════════════════════════════════════════════════════
#  GESTION DES RÔLES (HELPERS)
# ═══════════════════════════════════════════════════════════════════

ROLE_PERMISSIONS = {
    "admin": ALL_MODULES,  # Admin a accès à tout
    "manager": [  # Manager : gestion complète sauf accès employés
        "Nouvelle réservation",
        "Réservations",
        "Calendrier",
        "Ajouter un acompte",
        "Charges",
        "Journal de Caisse",
        "Modifier réservation",
        "Export Excel",
        "Centre de Réception",
        "Règles de réservation",
    ],
    "employe": [  # Employé : consultation et opérations de base
        "Réservations",
        "Calendrier",
        "Ajouter un acompte",
    ]
}


def apply_role_template(user_id: int, role: str):
    """Applique un template de permissions basé sur le rôle."""
    if role in ROLE_PERMISSIONS:
        set_user_modules(user_id, ROLE_PERMISSIONS[role])


# ═══════════════════════════════════════════════════════════════════
#  RECHERCHE
# ═══════════════════════════════════════════════════════════════════

def search_users(query: str):
    """Recherche des utilisateurs par username, nom ou prénom."""
    conn = get_connection()
    q = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM users WHERE "
        "(username LIKE ? OR nom LIKE ? OR prenom LIKE ?) AND actif=1 "
        "ORDER BY nom, prenom",
        (q, q, q)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
