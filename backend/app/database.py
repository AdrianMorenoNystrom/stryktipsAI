"""Postgres storage adapter for the existing parameterized repository contract.

SQL definitions are versioned in migrations. Business services stay database-neutral.
Payload JSON remains immutable text; indexed timestamp columns are TIMESTAMPTZ in PG.
"""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
from uuid import uuid4
from app.storage import SQLiteArchive, iso, now_utc


class Record(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    @staticmethod
    def row(value):
        return Record({k: iso(v) if isinstance(v, datetime) else v for k, v in value.items()}) if value is not None else None

    def fetchone(self):
        return self.row(self.cursor.fetchone())

    def fetchall(self):
        return [self.row(r) for r in self.cursor.fetchall()]

    def __iter__(self):
        return (self.row(r) for r in self.cursor)


class PostgresConnection:
    def __init__(self, con):
        self.con = con

    def execute(self, query, params=()):
        # Repository SQL is internal, parameterized, and contains no literal '?'.
        query = query.replace('?', '%s')
        if 'INSERT OR IGNORE' in query:
            query = query.replace('INSERT OR IGNORE', 'INSERT') + ' ON CONFLICT DO NOTHING'
        return Cursor(self.con.execute(query, params))


class PersistentArchive(SQLiteArchive):
    @property
    def database_url(self):
        return os.getenv('DATABASE_URL', '')

    @contextmanager
    def connection(self):
        if not self.database_url:
            with super().connection() as con:
                yield con
            return
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=10) as con:
            con.execute("SET TIME ZONE 'UTC'")
            yield PostgresConnection(con)

    def save_raw(self, raw):
        if not self.database_url:
            return super().save_raw(raw)
        key = hashlib.sha256(raw).hexdigest()
        with self.connection() as con:
            con.execute('INSERT OR IGNORE INTO provider_raw_blobs(id,content,created_at) VALUES (?,?,?)', (key, raw, iso(now_utc())))
        return 'db:' + key

    def read_raw(self, reference):
        if not reference.startswith('db:'):
            return (self.root / reference).read_bytes()
        with self.connection() as con:
            row = con.execute('SELECT content FROM provider_raw_blobs WHERE id=?', (reference[3:],)).fetchone()
            if not row:
                raise ValueError('Archived raw payload missing')
            return bytes(row[0])

    @contextmanager
    def lock(self, name):
        """One collector/refresh across replicas. PG session lock releases on crash."""
        if self.database_url:
            import psycopg
            key = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], 'big', signed=True)
            with psycopg.connect(self.database_url, autocommit=True, connect_timeout=10) as con:
                acquired = con.execute('SELECT pg_try_advisory_lock(%s)', (key,)).fetchone()[0]
                try:
                    yield acquired
                finally:
                    if acquired:
                        con.execute('SELECT pg_advisory_unlock(%s)', (key,))
            return
        from datetime import timedelta
        owner = uuid4().hex
        at = now_utc()
        with self.connection() as con:
            con.execute('DELETE FROM collection_leases WHERE name=? AND expires_at<?', (name, iso(at)))
            acquired = con.execute('INSERT OR IGNORE INTO collection_leases VALUES (?,?,?)', (name, owner, iso(at + timedelta(minutes=30)))).rowcount > 0
        try:
            yield acquired
        finally:
            if acquired:
                with self.connection() as con:
                    con.execute('DELETE FROM collection_leases WHERE name=? AND owner=?', (name, owner))


def migrate(url=None):
    import psycopg
    url = url or os.getenv('DATABASE_URL')
    if not url:
        raise ValueError('DATABASE_URL is required for migrations')
    directory = Path(__file__).resolve().parents[1] / 'migrations'
    with psycopg.connect(url, connect_timeout=10) as con:
        con.execute('SELECT pg_advisory_xact_lock(49700004)')
        con.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())')
        for path in sorted(directory.glob('*.sql')):
            content = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(content.encode()).hexdigest()
            existing = con.execute('SELECT checksum FROM schema_migrations WHERE version=%s', (path.name,)).fetchone()
            if existing:
                if existing[0] != checksum:
                    raise ValueError('Applied migration checksum changed: ' + path.name)
                continue
            con.execute(content, prepare=False)
            con.execute('INSERT INTO schema_migrations(version,checksum) VALUES (%s,%s)', (path.name, checksum))
