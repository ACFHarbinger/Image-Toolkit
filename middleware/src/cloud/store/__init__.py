"""Encrypted ``cloud_jobs.db`` store (#827)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .db import (
    CLOUD_SCHEMA_VERSION,
    DEFAULT_STORE_PATH,
    StoreUnavailable,
    ensure_schema,
    open_store_db,
    schema_version,
    transaction,
)
from .jobs import AttemptRow, JobRepo, UnknownJob
from .ledger import (
    KIND_ACTUAL,
    KIND_BILLED,
    KIND_ESTIMATE,
    KIND_RESERVED,
    SOURCE_JOBS,
    SOURCE_POC,
    LedgerEntry,
    SpendLedger,
    prune_history,
)


@dataclass
class CloudJobStore:
    db: Any
    jobs: JobRepo
    ledger: SpendLedger

    @classmethod
    def from_db(cls, db: Any, clock: Callable[[], float] = time.time) -> "CloudJobStore":
        ensure_schema(db)
        return cls(db, JobRepo(db, clock), SpendLedger(db, clock))

    @classmethod
    def open(cls, secret: str, salt: str, path: Optional[Path] = None,
             clock: Callable[[], float] = time.time, **kwargs: Any) -> "CloudJobStore":
        return cls.from_db(open_store_db(secret, salt, path, **kwargs), clock)

    def close(self) -> None:
        self.db.close()


__all__ = [
    "AttemptRow", "CLOUD_SCHEMA_VERSION", "CloudJobStore", "DEFAULT_STORE_PATH", "JobRepo",
    "KIND_ACTUAL", "KIND_BILLED", "KIND_ESTIMATE", "KIND_RESERVED", "LedgerEntry",
    "SOURCE_JOBS", "SOURCE_POC", "SpendLedger", "StoreUnavailable", "UnknownJob",
    "open_store_db", "prune_history", "schema_version", "transaction",
]
