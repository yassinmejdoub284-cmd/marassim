# -*- coding: utf-8 -*-
"""
config.py — Configuration de la connexion à la base.

Lit `marassim.ini` placé à côté de l'application. Si le fichier est absent,
l'application fonctionne exactement comme avant : SQLite en local.

Exemple de marassim.ini pour un poste client :

    [database]
    backend  = postgres
    host     = 192.168.1.10
    port     = 5432
    name     = marassim
    user     = marassim
    password = motdepasse

⚠ Ce fichier contient un mot de passe : il est exclu du dépôt Git.
"""
import configparser
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INI_PATH = os.path.join(BASE_DIR, "marassim.ini")

DEFAULTS = {
    "backend": "sqlite",
    "path": "marassim.db",
    "host": "localhost",
    "port": "5432",
    "name": "marassim",
    "user": "marassim",
    "password": "",
    "connect_timeout": "8",
    "app_name": "Marassim",
}


def _load():
    cfg = dict(DEFAULTS)
    parser = configparser.ConfigParser()
    if os.path.exists(INI_PATH):
        try:
            parser.read(INI_PATH, encoding="utf-8")
            if parser.has_section("database"):
                for k, v in parser.items("database"):
                    cfg[k.strip().lower()] = v.strip()
        except Exception as ex:               # fichier illisible → repli SQLite
            print(f"[config] marassim.ini ignoré ({ex}) — repli sur SQLite local.")
    # Variables d'environnement prioritaires (pratique pour les tests)
    for k in list(cfg):
        env = os.environ.get(f"MARASSIM_DB_{k.upper()}")
        if env:
            cfg[k] = env
    cfg["backend"] = cfg["backend"].lower()
    if cfg["backend"] in ("postgresql", "psql", "pg"):
        cfg["backend"] = "postgres"
    if not os.path.isabs(cfg["path"]):
        cfg["path"] = os.path.join(BASE_DIR, cfg["path"])
    return cfg


CONF = _load()


def reload():
    """Relit marassim.ini (utile après modification sans redémarrer)."""
    global CONF
    CONF = _load()
    return CONF


def backend():
    return CONF["backend"]


def is_postgres():
    return CONF["backend"] == "postgres"


def describe():
    """Résumé lisible de la connexion courante, sans le mot de passe."""
    if is_postgres():
        return (f"PostgreSQL {CONF['user']}@{CONF['host']}:{CONF['port']}"
                f"/{CONF['name']}")
    return f"SQLite {CONF['path']}"
