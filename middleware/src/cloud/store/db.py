"""Opening ``cloud_jobs.db`` and running transactions on it (#827).

The store has its own long-lived secret (kept in VaultManager; the GUI hands
it to the daemon over IPC), not the vault password: it must open before any
job exists, for the job list, the orphan sweep and WAL replay.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from middleware.src.constants import IMAGE_TOOLKIT_DIR

DEFAULT_STORE_PATH = Path(IMAGE_TOOLKIT_DIR) / "cloud_jobs.db"
CLOUD_SCHEMA_VERSION = 2
SCHEMA_SQL = Path(__file__).with_name("schema.sql")

# base.database verifies the key with a read *before* setting busy_timeout,
# so an open can see "database is locked" while another process writes. Keep
# retrying past the engine's own 5 s busy_timeout before giving up.
_OPEN_DEADLINE_S = 8.0
_OPEN_BACKOFF_S = (0.05, 0.5)  # first, max


class StoreUnavailable(RuntimeError):
    """The store can't be opened (no secret, wrong secret, or held locked)."""


def _default_factory(path: str, secret: str, salt: str) -> Any:
    import base  # compiled extension; imported lazily so pure modules stay importable

    return base.database.Database(path, secret, salt)


def open_store_db(
    secret: str,
    salt: str,
    path: Optional[Path] = None,
    factory: Callable[[str, str, str], Any] = _default_factory,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    if not secret or not salt:
        raise StoreUnavailable("no store secret: unlock the vault in the app first")
    target = Path(path) if path is not None else DEFAULT_STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    waited, delay = 0.0, _OPEN_BACKOFF_S[0]
    while True:
        try:
            db = factory(str(target), secret, salt)
            break
        except RuntimeError as exc:
            if "locked" not in str(exc):
                raise StoreUnavailable(str(exc)) from exc
            if waited >= _OPEN_DEADLINE_S:
                raise StoreUnavailable(f"store stayed locked for {waited:.1f}s: {exc}") from exc
            sleep(delay)
            waited += delay
            delay = min(delay * 2, _OPEN_BACKOFF_S[1])
    try:
        ensure_schema(db)
    except StoreUnavailable:
        db.close()
        raise
    return db


def ensure_schema(db: Any) -> None:
    has_meta = db.query("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'", ())
    found = schema_version(db) if has_meta else 0
    if found > CLOUD_SCHEMA_VERSION:
        # A newer build wrote this store; applying our older DDL over it could lose data.
        raise StoreUnavailable(f"cloud_jobs.db is schema v{found}; this build understands v{CLOUD_SCHEMA_VERSION}")
    if found == 1:
        _migrate_v1_to_v2(db)
    db.apply_ddl(SCHEMA_SQL.read_text(encoding="utf-8"))
    db.execute(
        "INSERT INTO schema_meta(key, value) VALUES ('version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(CLOUD_SCHEMA_VERSION),),
    )


def _migrate_v1_to_v2(db: Any) -> None:
    """v2: per-shard collection state, so collection can outlive teardown."""
    cols = {r[1] for r in db.query("PRAGMA table_info(shards)", ())}
    for col in ("ready", "durable", "collect_attempts", "collect_failed"):
        if col not in cols:
            db.execute(f"ALTER TABLE shards ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0", ())


def schema_version(db: Any) -> int:
    rows = db.query("SELECT value FROM schema_meta WHERE key = 'version'", ())
    return int(rows[0][0]) if rows else 0


@contextlib.contextmanager
def transaction(db: Any) -> Iterator[Any]:
    """Atomic block; nests by joining an already-open transaction."""
    if db.in_transaction:
        yield db
        return
    db.begin()
    try:
        yield db
    except BaseException:
        db.rollback()
        raise
    else:
        db.commit()
