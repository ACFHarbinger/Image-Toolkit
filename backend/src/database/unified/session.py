"""Login-time construction and process-wide access to the library database.

The GUI opens the session once after vault unlock (the Argon2id KDF runs
exactly once, inside ``base.database.Database``); everything else calls
``get_session()``. Also owns schema application, shared with migration 001.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from backend.src.constants import IMAGE_TOOLKIT_DIR

SCHEMA_VERSION = 1
DEFAULT_DB_PATH = Path(IMAGE_TOOLKIT_DIR) / "library.db"

_SQL_DIR = Path(__file__).resolve().parent
SCHEMA_SQL_PATH = _SQL_DIR / "schema.sql"
SCHEMA_FTS_SQL_PATH = _SQL_DIR / "schema_fts.sql"

_lock = threading.Lock()
_db = None
_db_path: Optional[str] = None


def ensure_schema(db) -> None:
    """Apply schema v1 to *db* (idempotent) and stamp version + FTS flag.

    Core DDL always applies; the FTS5 layer applies only when the linked
    SQLCipher has FTS5 — ``schema_meta.fts_enabled`` records the outcome so
    search_repo can degrade to LIKE queries.
    """
    db.apply_ddl(SCHEMA_SQL_PATH.read_text())

    fts_enabled = False
    if db.has_fts5():
        db.apply_ddl(SCHEMA_FTS_SQL_PATH.read_text())
        fts_enabled = True

    db.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    db.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('fts_enabled', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        ("1" if fts_enabled else "0",),
    )


def open_session(password: str, salt: str, db_path: Optional[str] = None):
    """Open (creating if needed) the library DB and make it the session.

    Idempotent for the same path; raises if a session is already open on a
    different path. Wrong credentials raise RuntimeError from the engine.
    """
    global _db, _db_path
    path = str(db_path if db_path is not None else DEFAULT_DB_PATH)

    with _lock:
        if _db is not None:
            if _db_path == path and _db.is_open:
                return _db
            raise RuntimeError(
                f"unified session already open on {_db_path}; close it before "
                f"opening {path}"
            )

        import base  # deferred: keep module importable without the extension

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        db = base.database.Database(path, password, salt)
        try:
            ensure_schema(db)
        except Exception:
            db.close()
            raise
        _db, _db_path = db, path
        return db


def get_session():
    """Return the open session Database. Raises when none is open."""
    if _db is None or not _db.is_open:
        raise RuntimeError(
            "unified library database session is not open — call "
            "session.open_session(password, salt) after vault unlock"
        )
    return _db


def is_open() -> bool:
    return _db is not None and _db.is_open


def close_session() -> None:
    global _db, _db_path
    with _lock:
        if _db is not None:
            _db.close()
        _db, _db_path = None, None


def fts_enabled(db) -> bool:
    rows = db.query(
        "SELECT value FROM schema_meta WHERE key='fts_enabled'", ()
    )
    return bool(rows) and rows[0][0] == "1"
