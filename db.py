# -*- coding: utf-8 -*-
"""
db.py — Couche d'accès unique : SQLite (mono-poste) ou PostgreSQL (multi-poste).

Le reste de l'application continue d'écrire du SQL « style SQLite » :

    conn = db.connect()
    row  = conn.execute("SELECT * FROM reservations WHERE id=?", (7,)).fetchone()
    print(row["nom_client"], row[0])
    conn.close()

Ce module se charge des différences de dialecte :
  · les marqueurs `?` deviennent `%s` sur PostgreSQL,
  · `INTEGER PRIMARY KEY AUTOINCREMENT` devient `SERIAL PRIMARY KEY`,
  · `TEXT DEFAULT CURRENT_TIMESTAMP` devient `TEXT DEFAULT (now())::text`,
  · `REAL` devient `DOUBLE PRECISION`,
  · `cur.lastrowid` fonctionne grâce à un `RETURNING id` ajouté aux INSERT,
  · `PRAGMA table_info` est remplacé par `table_columns()`.

Aucune dépendance nouvelle en mode SQLite. Le mode PostgreSQL requiert
`psycopg2-binary`, installé une fois sur chaque poste.
"""
import re
import sqlite3
import time

import config

# ── Chargement paresseux de psycopg2 ────────────────────────────────────────
_pg = None
_pg_extras = None


def _load_pg():
    global _pg, _pg_extras
    if _pg is None:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as ex:
            raise RuntimeError(
                "Le mode PostgreSQL nécessite psycopg2.\n"
                "Installe-le une fois sur ce poste :\n"
                "    pip install psycopg2-binary"
            ) from ex
        _pg, _pg_extras = psycopg2, psycopg2.extras
    return _pg, _pg_extras


class DatabaseError(Exception):
    """Erreur de connexion ou de requête, message destiné à l'utilisateur."""


# ═══════════════════════════════════════════════════════════════════
#  TRADUCTION DE DIALECTE
# ═══════════════════════════════════════════════════════════════════
_DDL_RE = re.compile(r"^\s*(CREATE|ALTER|DROP)\b", re.I)
_INSERT_RE = re.compile(r"^\s*INSERT\b", re.I)
_RETURNING_RE = re.compile(r"\bRETURNING\b", re.I)


def _qmark_to_pyformat(sql: str) -> str:
    """Traduit les marqueurs `?` en `%s`.

    Deux subtilités, toutes deux vérifiées par les tests :
      · un `?` DANS une chaîne SQL ('x?y') n'est pas un marqueur,
      · un `%` littéral doit être doublé PARTOUT, y compris dans une chaîne
        (`LIKE '2027-%'`), sinon psycopg2 le prend pour un marqueur de
        formatage et lève « tuple index out of range ».
    """
    out = []
    in_str = False
    quote = ""
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "%":                     # doublé quel que soit le contexte
            out.append("%%")
        elif in_str:
            out.append(c)
            if c == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1]); i += 1   # '' échappé
                else:
                    in_str = False
        elif c in ("'", '"'):
            in_str, quote = True, c
            out.append(c)
        elif c == "?":
            out.append("%s")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _translate_ddl(sql: str) -> str:
    sql = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
                 "SERIAL PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\bAUTOINCREMENT\b", "", sql, flags=re.I)
    sql = re.sub(r"\bTEXT\s+DEFAULT\s+CURRENT_TIMESTAMP\b",
                 "TEXT DEFAULT (now())::text", sql, flags=re.I)
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.I)
    return sql


def translate(sql: str) -> str:
    """Adapte une requête SQLite au dialecte actif."""
    if not config.is_postgres():
        return sql
    if _DDL_RE.match(sql):
        sql = _translate_ddl(sql)
    return _qmark_to_pyformat(sql)


# ═══════════════════════════════════════════════════════════════════
#  CURSEUR & CONNEXION
# ═══════════════════════════════════════════════════════════════════
class Cursor:
    """Curseur commun aux deux moteurs, avec un `lastrowid` qui marche."""

    def __init__(self, raw, lastrowid=None):
        self._raw = raw
        self._lastrowid = lastrowid

    @property
    def lastrowid(self):
        if self._lastrowid is not None:
            return self._lastrowid
        return getattr(self._raw, "lastrowid", None)

    @property
    def description(self):
        return self._raw.description

    @property
    def rowcount(self):
        return self._raw.rowcount

    def fetchone(self):
        return self._raw.fetchone()

    def fetchall(self):
        return self._raw.fetchall()

    def fetchmany(self, n):
        return self._raw.fetchmany(n)

    def __iter__(self):
        return iter(self._raw)


class Connection:
    """Connexion unifiée. `execute()` accepte le SQL style SQLite."""

    def __init__(self, raw, is_pg):
        self._raw = raw
        self._pg = is_pg
        self.closed = False

    # ── requêtes ──────────────────────────────────────────────────
    def execute(self, sql, params=()):
        query = translate(sql)
        if not self._pg:
            return Cursor(self._raw.execute(query, params))

        want_id = bool(_INSERT_RE.match(query)) and not _RETURNING_RE.search(query)
        if want_id:
            query = query.rstrip().rstrip(";") + " RETURNING id"
        cur = self._raw.cursor()
        try:
            cur.execute(query, params)
        except Exception as ex:
            pg = _pg
            undefined_col = (pg is not None
                             and isinstance(ex, pg.errors.UndefinedColumn))
            if want_id and undefined_col:
                # Table sans colonne `id` : on rejoue sans RETURNING.
                self._raw.rollback()
                cur = self._raw.cursor()
                cur.execute(translate(sql), params)
                return Cursor(cur)
            # Toute autre erreur est réelle : ne pas la masquer.
            self._raw.rollback()
            raise DatabaseError(str(ex).strip()) from ex
        last = None
        if want_id:
            try:
                row = cur.fetchone()
                last = row[0] if row else None
            except Exception:
                last = None
        return Cursor(cur, last)

    def executescript(self, script):
        for stmt in [s for s in script.split(";") if s.strip()]:
            self.execute(stmt)

    # ── transactions ──────────────────────────────────────────────
    def commit(self):
        self._raw.commit()

    def rollback(self):
        try:
            self._raw.rollback()
        except Exception:
            pass

    def close(self):
        if not self.closed:
            try:
                self._raw.close()
            finally:
                self.closed = True

    # ── contexte : commit si succès, rollback si exception ────────
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False

    @property
    def raw(self):
        return self._raw


# ═══════════════════════════════════════════════════════════════════
#  OUVERTURE
# ═══════════════════════════════════════════════════════════════════
def connect(retries=3):
    """Ouvre une connexion selon marassim.ini. Réessaie si la base est
    momentanément verrouillée (SQLite) ou injoignable (réseau)."""
    conf = config.CONF
    last_err = None
    for attempt in range(retries):
        try:
            if config.is_postgres():
                pg, extras = _load_pg()
                raw = pg.connect(
                    host=conf["host"], port=int(conf["port"]),
                    dbname=conf["name"], user=conf["user"],
                    password=conf["password"],
                    connect_timeout=int(conf["connect_timeout"]),
                    application_name=conf["app_name"],
                    cursor_factory=extras.DictCursor,
                )
                return Connection(raw, True)
            raw = sqlite3.connect(conf["path"], timeout=15)
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA busy_timeout=15000")
            raw.execute("PRAGMA foreign_keys=ON")
            return Connection(raw, False)
        except Exception as ex:
            last_err = ex
            if attempt < retries - 1:
                time.sleep(0.4 * (attempt + 1))
    raise DatabaseError(
        f"Connexion impossible à {config.describe()} — {last_err}")


# ═══════════════════════════════════════════════════════════════════
#  UTILITAIRES PORTABLES
# ═══════════════════════════════════════════════════════════════════
def table_columns(conn, table):
    """Noms des colonnes d'une table — remplace `PRAGMA table_info`."""
    if config.is_postgres():
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=?", (table,)).fetchall()
        return {r[0] for r in rows}
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def table_exists(conn, table):
    if config.is_postgres():
        r = conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=?", (table,)).fetchone()
        return r is not None
    r = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone()
    return r is not None


def upsert(conn, table, key_cols, data):
    """INSERT … ON CONFLICT portable (remplace `INSERT OR REPLACE`)."""
    cols = list(data)
    ph = ",".join("?" * len(cols))
    vals = [data[c] for c in cols]
    if config.is_postgres():
        updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c not in key_cols)
        sql = (f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph}) "
               f"ON CONFLICT ({','.join(key_cols)}) DO UPDATE SET {updates}")
    else:
        sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({ph})"
    return conn.execute(sql, vals)


def lock_row(conn, table, row_id):
    """Verrouille une ligne le temps de la transaction (PostgreSQL).
    Sans effet sur SQLite, qui verrouille déjà toute la base en écriture."""
    if config.is_postgres():
        conn.execute(f"SELECT 1 FROM {table} WHERE id=? FOR UPDATE", (row_id,))


def ping():
    """Teste la connexion. Retourne (ok: bool, message: str)."""
    try:
        c = connect(retries=1)
        c.execute("SELECT 1").fetchone()
        c.close()
        return True, config.describe()
    except Exception as ex:
        return False, str(ex)
