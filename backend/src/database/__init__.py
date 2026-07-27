"""Database backends.

Phase DB (DB.6): the app runs on the unified SQLCipher store
(``backend.src.database.unified``). The legacy PostgreSQL backend
(``PgvectorImageDatabase``/``PooledPgvectorDatabase``) was archived to
``archive/python/database/`` 2026-07-27 (DB.6 P3b) — the last production
call sites (``phash_deduplicator.py``, ``utils/io/dispatcher.py``) were
re-pointed at the unified store first. Migration 003
(``backend.migrations.migrate_pgvector``) still imports ``psycopg2``
directly, deferred and guarded, for one-time imports from a pre-DB.6
Postgres library — that import does not go through this package.
"""
