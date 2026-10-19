"""Spend ledger (never pruned) and job-history retention (#827)."""

from __future__ import annotations

import calendar
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional

from ..poc.usage import UsageRow
from ..state import TERMINAL
from .db import transaction

KIND_ACTUAL = "actual"
KIND_ESTIMATE = "estimate"
KIND_RESERVED = "reserved"
KIND_BILLED = "billed"  # provider billing-API reconciliation
SOURCE_JOBS = "cloud_jobs"
SOURCE_POC = "poc"


@dataclass(frozen=True)
class LedgerEntry:
    job_id: str
    provider: str
    kind: str
    amount_usd: float
    attempt_id: str = ""
    task: str = ""
    status: str = ""
    duration_s: float = 0.0
    peak_rss_kib: float = 0.0
    peak_vcpu: float = 0.0
    peak_gpu: float = 0.0
    egress_bytes: int = 0
    ts: Optional[float] = None
    source: str = SOURCE_JOBS


_COLS = ("job_id, attempt_id, provider, task, status, kind, amount_usd, duration_s, "
         "peak_rss_kib, peak_vcpu, peak_gpu, egress_bytes, ts, source")


def month_start(ts: float) -> float:
    t = time.gmtime(ts)
    return float(calendar.timegm((t.tm_year, t.tm_mon, 1, 0, 0, 0)))


class SpendLedger:
    def __init__(self, db: Any, clock: Callable[[], float] = time.time):
        self._db = db
        self._clock = clock

    def add(self, entry: LedgerEntry) -> None:
        self._db.execute(
            f"INSERT INTO spend_ledger({_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (entry.job_id, entry.attempt_id, entry.provider, entry.task, entry.status, entry.kind,
             float(entry.amount_usd), entry.duration_s, entry.peak_rss_kib, entry.peak_vcpu,
             entry.peak_gpu, int(entry.egress_bytes),
             entry.ts if entry.ts is not None else self._clock(), entry.source))

    def release_reservation(self, job_id: str) -> None:
        self._db.execute("DELETE FROM spend_ledger WHERE job_id = ? AND kind = ?", (job_id, KIND_RESERVED))

    def total(self, kind: str = KIND_ACTUAL, since: Optional[float] = None, job_id: Optional[str] = None) -> float:
        sql = "SELECT COALESCE(SUM(amount_usd), 0) FROM spend_ledger WHERE kind = ?"
        params: List[Any] = [kind]
        if since is not None:
            sql += " AND ts >= ?"
            params.append(since)
        if job_id is not None:
            sql += " AND job_id = ?"
            params.append(job_id)
        return float(self._db.query(sql, params)[0][0])

    def month_to_date(self, now: Optional[float] = None) -> float:
        start = month_start(now if now is not None else self._clock())
        return self.total(KIND_ACTUAL, since=start)

    def reserved(self) -> float:
        return self.total(KIND_RESERVED)

    def usage_rows(self, source: Optional[str] = None) -> List[UsageRow]:
        """Actual-spend rows in the PoC's UsageRow shape, for the Dashboards charts."""
        sql = (f"SELECT {_COLS} FROM spend_ledger WHERE kind = ?"
               + (" AND source = ?" if source else "") + " ORDER BY ts")
        params = [KIND_ACTUAL] + ([source] if source else [])
        return [
            UsageRow(job_id=r[0], provider=r[2], task=r[3], status=r[4], duration_seconds=r[7],
                     timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r[12])),
                     peak_rss_kib=r[8], peak_vcpu=r[9], peak_gpu=r[10], egress_bytes=r[11],
                     cost_usd=r[6])
            for r in self._db.query(sql, params)
        ]

    def import_poc_rows(self, rows: Iterable[UsageRow]) -> int:
        """One-time UsageStore migration; idempotent on (job_id, source='poc')."""
        n = 0
        with transaction(self._db):
            for row in rows:
                if self._db.query("SELECT 1 FROM spend_ledger WHERE job_id = ? AND source = ?",
                                  (row.job_id, SOURCE_POC)):
                    continue
                self.add(LedgerEntry(
                    job_id=row.job_id, provider=row.provider, kind=KIND_ACTUAL,
                    amount_usd=row.cost_usd, task=row.task, status=row.status,
                    duration_s=row.duration_seconds, peak_rss_kib=row.peak_rss_kib,
                    peak_vcpu=row.peak_vcpu, peak_gpu=row.peak_gpu, egress_bytes=row.egress_bytes,
                    ts=_parse_ts(row.timestamp, self._clock()), source=SOURCE_POC))
                n += 1
        return n


def _parse_ts(text: str, default: float) -> float:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return float(calendar.timegm(time.strptime(text, fmt)))
        except (TypeError, ValueError):
            continue
    return default


def prune_history(db: Any, older_than_s: float, now: float, export_path: Optional[Path] = None) -> int:
    """Delete terminal jobs (cascading attempts, shards, events). The ledger is untouched.

    Jobs still owing a teardown are never pruned.
    """
    cutoff = now - older_than_s
    terminal = [s.value for s in TERMINAL]
    marks = ",".join("?" * len(terminal))
    ids = [r[0] for r in db.query(
        f"SELECT job_id FROM jobs WHERE state IN ({marks}) AND teardown_pending = 0 "
        "AND updated_at < ?", terminal + [cutoff])]
    if not ids:
        return 0
    if export_path is not None:
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("a", encoding="utf-8") as fh:
            for job_id in ids:
                job = db.query("SELECT job_id, kind, state, outcome, outcome_reason, spec_json, "
                               "created_at, updated_at FROM jobs WHERE job_id = ?", (job_id,))[0]
                events = db.query("SELECT ts, type, data_json FROM job_events WHERE job_id = ? ORDER BY id",
                                  (job_id,))
                fh.write(json.dumps({
                    "job_id": job[0], "kind": job[1], "state": job[2], "outcome": job[3],
                    "reason": job[4], "spec": json.loads(job[5]), "created_at": job[6],
                    "updated_at": job[7],
                    "events": [{"ts": e[0], "type": e[1], "data": json.loads(e[2])} for e in events],
                }, sort_keys=True) + "\n")
    with transaction(db):
        for job_id in ids:
            db.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
    return len(ids)
