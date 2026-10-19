"""The authoritative submission path (Gate A review blockers 1 and 2).

``CloudJobService.submit`` is the only way a job reaches the engine: it runs
preflight, insists on the acknowledgements preflight asked for, submits the
*sanitized* spec, and reserves the job's spend cap against the monthly
budget inside one ``BEGIN IMMEDIATE`` transaction. It also gives the engine
its revalidator, so scheduled starts and automatic fallbacks pass the same
checks with the same acknowledgements, never new ones nobody gave.

The GUI's Plan & cost sheet calls :meth:`preview`; B1's authenticated
command path calls :meth:`submit`.
"""

from __future__ import annotations

import datetime as _dt
import time
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Mapping, Optional, Tuple

from .acceptance import issue
from .cost.budget import budget_view, monthly_cap_blocker, reservation_for
from .cost.catalogue import PriceCatalogue
from .engine import JobEngine
from .preflight import Issue, PreflightReport, WeightClass, run_preflight
from .risk.engine import RuleSet, Severity, load_seed
from .settings import CloudSettings
from .spec import JobSpec
from .store import transaction


class SubmissionRefused(RuntimeError):
    def __init__(self, reason: str, report: Optional[PreflightReport] = None):
        super().__init__(reason)
        self.report = report


@dataclass
class CloudJobService:
    engine: JobEngine
    settings: CloudSettings
    catalogue: PriceCatalogue
    ruleset: Callable[[], RuleSet] = lambda: RuleSet(load_seed())
    weight_classes: Callable[[], Mapping[str, WeightClass]] = dict
    watchdog_configured: bool = False
    clock: Callable[[], float] = time.time
    today: Callable[[], _dt.date] = _dt.date.today

    def __post_init__(self) -> None:
        self.engine.revalidator = self.revalidate

    @property
    def _db(self):
        return self.engine.store.db

    def preview(self, spec: JobSpec, secret_decisions: Mapping[Tuple[str, str], str] = None,
                exclude_job: Optional[str] = None) -> PreflightReport:
        adapter = self.engine.adapters.get(spec.placement.provider)
        budget = budget_view(self._db, self.settings, self.clock(), exclude_job)
        report = run_preflight(
            spec, catalogue=self.catalogue, settings=self.settings, adapter=adapter,
            ruleset=self.ruleset(), month_to_date_usd=budget.committed_usd,
            weight_classes=self.weight_classes(), secret_decisions=secret_decisions or {},
            watchdog_configured=self.watchdog_configured, today=self.today())
        if exclude_job is None and report.stages_run[-1:] == ("risk",):
            # The sheet shows the same reservation-based check submit() enforces.
            why = monthly_cap_blocker(budget, self.settings,
                                      reservation_for(report.spec, self.settings, report.estimate))
            if why is not None:
                report = replace(report, issues=report.issues + (Issue("budget", Severity.BLOCK, why),))
        return report

    def submit(self, spec: JobSpec, acknowledged: Iterable[str] = (),
               secret_decisions: Mapping[Tuple[str, str], str] = None) -> str:
        if spec.placement.provider not in self.engine.adapters:
            raise SubmissionRefused(f"no adapter for provider {spec.placement.provider!r}")
        acks = tuple(sorted(set(acknowledged)))
        report = self.preview(spec, secret_decisions)  # network probes happen outside the write lock
        if not report.ok_to_submit(acks):
            missing = sorted(set(report.needs_ack) - set(acks))
            blocks = "; ".join(i.message for i in report.blocking)
            raise SubmissionRefused(blocks or f"acknowledgement needed: {', '.join(missing)}", report)
        reservation = reservation_for(report.spec, self.settings, report.estimate)
        accepted = issue(
            report.spec, reservation, report.capability_override, acks,
            tuple((n, f, c) for (n, f), c in sorted((secret_decisions or {}).items())),
            report.estimate.breakdown(), report.estimate.rows)
        with transaction(self._db):  # BEGIN IMMEDIATE: serializes the budget check with other submitters
            why = monthly_cap_blocker(budget_view(self._db, self.settings, self.clock()), self.settings,
                                      reservation)
            if why is not None:
                raise SubmissionRefused(why, report)
            return self.engine.submit(accepted)

    def revalidate(self, job_id: str, spec: JobSpec) -> Optional[str]:
        """Same preflight, same acknowledgements and secret choices as at acceptance; None means it passes."""
        record = self.engine.store.jobs.accepted_record(job_id)
        if not record:
            return "job has no acceptance record"
        decisions = {(n, f): c for n, f, c in record.get("secret_decisions", [])}
        report = self.preview(spec, decisions, exclude_job=job_id)
        acks = set(record.get("acknowledged", []))
        if report.blocking:
            return "; ".join(i.message for i in report.blocking)
        missing = sorted(set(report.needs_ack) - acks)
        if missing:
            return f"needs acknowledgement nobody gave: {', '.join(missing)}"
        if report.capability_override and not record.get("capability_override"):
            return "new placement needs a capability override the user didn't accept"
        reserved = float(record.get("reservation_usd", 0.0))
        if self.settings.hard_caps_enabled and report.estimate.known and report.estimate.total_usd > reserved:
            return f"estimate ${report.estimate.total_usd:.2f} exceeds the job's reserved ${reserved:.2f}"
        return None

