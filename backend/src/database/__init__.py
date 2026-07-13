"""Database backends.

Phase DB (DB.6): the app runs on the unified SQLCipher store
(``backend.src.database.unified``). The legacy PostgreSQL backend below is
kept importable ONLY for migration 003 and pending archival — importing it
must stay lazy so the package (and the unified subpackage) does not require
psycopg2 at import time.
"""


def __getattr__(name):
    if name == "PgvectorImageDatabase":
        from .image_database import PgvectorImageDatabase
        return PgvectorImageDatabase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
