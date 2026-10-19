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

from backend.src.constants import IMAGE_TOOLKIT_DIR

DEFAULT_STORE_PATH = Path(IMAGE_TOOLKIT_DIR) / "cloud_jobs.db"
CLOUD_SCHEMA_VERSION = 1
SCHEMA_SQL = Path(__file__).with_name("schema.sql")

# base.database verifies the key with a read *before* setting busy_timeout,
# so two processes opening at the same instant can see "database is locked".
_OPEN_RETRIES = 20
_OPEN_BACKOFF_S = 0.1


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
    last: Optional[Exception] = None
    for _ in range(_OPEN_RETRIES):
        try:
            db = factory(str(target), secret, salt)
            break
        except RuntimeError as exc:
            if "locked" not in str(exc):
                raise StoreUnavailable(str(exc)) from exc
            last = exc
            sleep(_OPEN_BACKOFF_S)
    else:
        raise StoreUnavailable(f"store stayed locked: {last}")
    ensure_schema(db)
    return db


def ensure_schema(db: Any) -> None:
    db.apply_ddl(SCHEMA_SQL.read_text(encoding="utf-8"))
    db.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', ?)",
        (str(CLOUD_SCHEMA_VERSION),),
    )


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
