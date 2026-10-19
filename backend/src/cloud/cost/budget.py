"""Ledger-backed monthly budget (#832, Gate A review blocker 2).

Each accepted job reserves its *spend cap*, not its estimate: the engine
stops a job before it passes that cap, so the sum of open reservations plus
what already settled this month bounds the month's spend. The check runs
inside the same ``BEGIN IMMEDIATE`` transaction that writes the reservation,
so two submitters (GUI and daemon) can't both fit into the last few dollars.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..settings import CloudSettings
from ..spec import JobSpec
from ..store.ledger import KIND_ACTUAL, KIND_RESERVED, month_start
from .caps import effective_max_spend
from .estimate import Estimate


@dataclass(frozen=True)
class BudgetView:
    settled_this_month_usd: float   # actual spend of jobs that no longer hold a reservation
    open_commitments_usd: float     # per open job: max(reservation, spend so far)
    monthly_cap_usd: float

    @property
    def committed_usd(self) -> float:
        return self.settled_this_month_usd + self.open_commitments_usd

    @property
    def headroom_usd(self) -> float:
        return self.monthly_cap_usd - self.committed_usd


def reservation_for(spec: JobSpec, settings: CloudSettings, est: Estimate) -> float:
    """What a job holds against the month while it is open."""
    if settings.hard_caps_enabled:
        return effective_max_spend(spec, settings)
    return est.total_usd if est.known else 0.0


def budget_view(db: Any, settings: CloudSettings, now: float, exclude_job: Optional[str] = None) -> BudgetView:
    start = month_start(now)
    reserved: Dict[str, float] = {
        r[0]: float(r[1]) for r in db.query(
            "SELECT job_id, SUM(amount_usd) FROM spend_ledger WHERE kind = ? GROUP BY job_id", (KIND_RESERVED,))
        if r[0] != exclude_job}
    actual_all: Dict[str, float] = {
        r[0]: float(r[1]) for r in db.query(
            "SELECT job_id, SUM(amount_usd) FROM spend_ledger WHERE kind = ? GROUP BY job_id", (KIND_ACTUAL,))}
    running: Dict[str, float] = {
        r[0]: float(r[1]) for r in db.query(
            "SELECT job_id, SUM(cost_usd) FROM attempts WHERE ended_at IS NULL GROUP BY job_id", ())}
    settled = sum(float(r[1]) for r in db.query(
        "SELECT job_id, SUM(amount_usd) FROM spend_ledger WHERE kind = ? AND ts >= ? GROUP BY job_id",
        (KIND_ACTUAL, start)) if r[0] not in reserved and r[0] != exclude_job)
    open_jobs = sum(max(res, actual_all.get(j, 0.0) + running.get(j, 0.0)) for j, res in reserved.items())
    return BudgetView(settled, open_jobs, settings.monthly_cap_usd)


def monthly_cap_blocker(view: BudgetView, settings: CloudSettings, reservation_usd: float) -> Optional[str]:
    if not settings.hard_caps_enabled:
        return None
    if view.committed_usd + reservation_usd > settings.monthly_cap_usd:
        return (f"monthly cap: ${view.committed_usd:.2f} already committed this month plus this job's "
                f"${reservation_usd:.2f} cap is over ${settings.monthly_cap_usd:.2f}")
    return None
