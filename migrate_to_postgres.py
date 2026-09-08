# -*- coding: utf-8 -*-
"""
migrate_to_postgres.py — Copie la base SQLite existante vers PostgreSQL.

À lancer UNE SEULE FOIS, depuis le poste qui détient marassim.db, après avoir
créé la base PostgreSQL et renseigné marassim.ini.

    python migrate_to_postgres.py                  # utilise ./marassim.db
    python migrate_to_postgres.py chemin/vers.db   # une autre source

Le script :
  1. vérifie la connexion PostgreSQL,
  2. crée le schéma s'il n'existe pas,
  3. refuse d'écraser des données déjà présentes (sauf --force),
  4. copie chaque table, colonne par colonne (les colonnes absentes côté
     PostgreSQL sont ignorées, celles en trop restent à NULL),
  5. recale les compteurs d'ID,
  6. compare les totaux ligne à ligne et affiche un rapport.

La base SQLite n'est jamais modifiée.
"""
import os
import sqlite3
import sys

import config
import db as DB

# Ordre d'INSERTION : une table n'apparaît qu'après celles dont elle dépend.
# PostgreSQL fait respecter les clés étrangères, contrairement à SQLite qui
# les ignorait par défaut — l'ordre compte donc réellement.
TABLES = [
    "users", "module_access", "employees", "pointage", "paiement_employees",
    "reservations", "reservation_rules", "charges", "charges_omar",
    "recettes_omar_extra",
]


def sqlite_tables(src):
    return {r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def sqlite_columns(src, table):
    return [r[1] for r in src.execute(f"PRAGMA table_info({table})")]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv
    src_path = args[0] if args else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "marassim.db")

    print("=" * 66)
    print("  MIGRATION SQLite → PostgreSQL")
    print("=" * 66)

    if not os.path.exists(src_path):
        sys.exit(f"✖ Base source introuvable : {src_path}")
    if not config.is_postgres():
        sys.exit("✖ marassim.ini n'est pas configuré sur PostgreSQL.\n"
                 "  Renseigne [database] backend = postgres avant de migrer.")

    print(f"  Source      : {src_path}")
    print(f"  Destination : {config.describe()}")

    ok, msg = DB.ping()
    if not ok:
        sys.exit(f"✖ PostgreSQL injoignable :\n  {msg}")
    print("  Connexion   : OK\n")

    src = sqlite3.connect(src_path)
    src.row_factory = sqlite3.Row
    present = sqlite_tables(src)

    # Schéma côté PostgreSQL
    import database
    import access_control
    database.init_db()
    access_control.init_access_db()

    dst = DB.connect()

    # Garde-fou : ne pas écraser une base déjà remplie
    if not force:
        busy = []
        for t in TABLES:
            try:
                n = dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                n = 0
            # users/module_access contiennent l'admin créé automatiquement
            seuil = 1 if t == "users" else (len(access_control.ALL_MODULES)
                                            if t == "module_access" else 0)
            if n > seuil:
                busy.append(f"{t} ({n} lignes)")
        if busy:
            src.close(); dst.close()
            sys.exit("✖ La base PostgreSQL contient déjà des données :\n   "
                     + ", ".join(busy)
                     + "\n  Relance avec --force pour écraser, ou vide-la d'abord.")

    # Purge en ordre INVERSE : les tables enfants d'abord, sinon PostgreSQL
    # refuse de vider une table encore référencée.
    for table in reversed(TABLES):
        try:
            dst.execute(f"DELETE FROM {table}")
        except Exception:
            dst.rollback()
    dst.commit()

    print("  Copie des tables")
    print("  " + "-" * 62)
    total_src = total_dst = 0
    rapport = []

    for table in TABLES:
        if table not in present:
            rapport.append((table, 0, 0, "absente de la source"))
            continue
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        cols_src = sqlite_columns(src, table)
        cols_dst = DB.table_columns(dst, table)
        cols = [c for c in cols_src if c in cols_dst]
        ignorees = [c for c in cols_src if c not in cols_dst]

        if cols and rows:
            ph = ",".join("?" * len(cols))
            sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph}) RETURNING id"
            simple = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})"
            orphelines = []
            for r in rows:
                try:
                    dst.execute(simple if "id" not in cols_dst else sql,
                                [r[c] for c in cols])
                except Exception as ex:
                    dst.rollback()
                    orphelines.append((dict(r).get("id"), str(ex).split("\n")[0]))
            if orphelines:
                print(f"    ⚠ {table} : {len(orphelines)} ligne(s) refusée(s) "
                      f"(référence invalide)")
                for oid, msg in orphelines[:3]:
                    print(f"        id={oid} — {msg[:80]}")
        dst.commit()

        n_dst = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        total_src += len(rows); total_dst += n_dst
        note = f"{len(ignorees)} colonne(s) ignorée(s)" if ignorees else ""
        flag = "OK" if n_dst == len(rows) else "✖ ÉCART"
        rapport.append((table, len(rows), n_dst, f"{flag} {note}".strip()))
        print(f"    {table:22s} {len(rows):5d} → {n_dst:5d}   {flag} {note}")

    # Recaler les compteurs d'ID
    print("\n  Recalage des compteurs d'ID")
    for table in TABLES:
        if table not in present:
            continue
        try:
            dst.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
                f"(SELECT MAX(id) IS NOT NULL FROM {table}))")
        except Exception as ex:
            print(f"    {table}: {ex}")
    dst.commit()

    src.close(); dst.close()

    print("\n" + "=" * 66)
    ecarts = [r for r in rapport if r[3].startswith("✖")]
    if ecarts:
        print(f"  ⚠ MIGRATION INCOMPLÈTE — {len(ecarts)} table(s) en écart")
        for t, a, b, _ in ecarts:
            print(f"    {t} : {a} attendues, {b} copiées")
        sys.exit(1)
    print(f"  ✅ MIGRATION RÉUSSIE — {total_dst} lignes copiées")
    print("     La base SQLite d'origine est intacte ; garde-la en sauvegarde.")
    print("=" * 66)


if __name__ == "__main__":
    main()
