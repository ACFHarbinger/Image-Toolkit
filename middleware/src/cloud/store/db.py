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


def _default_factory(path: str, *args: Any, **kwargs: Any) -> Any:
    import backend  # compiled extension; imported lazily so pure modules stay importable

    expected_store = kwargs.get("expected_store", "cloud_jobs")
    sup_session = kwargs.get("expected_supervisor_session", "")
    key_path = kwargs.get("daemon_key_path", "")

    if len(args) == 1 and isinstance(args[0], str) and args[0].startswith("itkl_"):
        return backend.database.Database.from_lease(
            path,
            args[0],
            expected_store=expected_store,
            expected_supervisor_session=sup_session,
            daemon_key_path=key_path,
        )
    if "lease" in kwargs and kwargs["lease"]:
        return backend.database.Database.from_lease(
            path,
            kwargs["lease"],
            expected_store=expected_store,
            expected_supervisor_session=sup_session,
            daemon_key_path=key_path,
        )
    return backend.database.Database(path, *args, **kwargs)


def open_store_db(
    secret: Optional[str] = None,
    salt: Optional[str] = None,
    path: Optional[Path] = None,
    lease: Optional[str] = None,
    expected_supervisor_session: Optional[str] = None,
    daemon_key_path: Optional[str] = None,
    factory: Optional[Callable[..., Any]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    actual_factory = factory or _default_factory
    target = Path(path) if path is not None else DEFAULT_STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    lease_token = lease or (secret if secret and secret.startswith("itkl_") else None)

    kwargs: dict[str, Any] = {}
    if expected_supervisor_session is not None:
        kwargs["expected_supervisor_session"] = expected_supervisor_session
    if daemon_key_path is not None:
        kwargs["daemon_key_path"] = daemon_key_path

    if lease_token:
        open_args: tuple[Any, ...] = (str(target), lease_token)
    elif secret and salt:
        open_args = (str(target), secret, salt)
    else:
        raise StoreUnavailable("no store secret or lease: unlock the vault in the app first")

    waited, delay = 0.0, _OPEN_BACKOFF_S[0]
    while True:
        try:
            db = actual_factory(*open_args, **kwargs)
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
