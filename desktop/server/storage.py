"""One transaction for the complete legacy operation, including its rule reads."""
import contextvars
import sqlite3
from contextlib import contextmanager

active_connection = contextvars.ContextVar('marassim_transaction', default=None)


class TransactionView:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, *args):
        return self.raw.execute(*args)

    def commit(self):
        # Legacy helpers commit/close independently. The API owns the boundary.
        pass

    def close(self):
        pass

    def rollback(self):
        raise RuntimeError('Opération annulée ; aucune modification enregistrée.')


class Storage:
    def __init__(self, path):
        self.path = str(path)
        conn = self.connect()
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=FULL')
        finally:
            conn.close()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=30000')
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    @contextmanager
    def transaction(self, write=False):
        conn = self.connect()
        token = active_connection.set(TransactionView(conn))
        try:
            conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            active_connection.reset(token)
            conn.close()

    def legacy_connect(self):
        view = active_connection.get()
        if view is None:
            raise RuntimeError('Le moteur métier doit être appelé dans une transaction serveur.')
        return view
