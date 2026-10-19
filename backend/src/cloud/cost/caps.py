"""Effective limits, admission, and estimate-vs-actual calibration (#832)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple

from ..settings import CloudSettings
from ..spec import JobSpec


def effective_max_spend(spec: JobSpec, settings: CloudSettings) -> float:
    return spec.limits.max_spend_usd if spec.limits.max_spend_usd is not None else settings.default_max_spend_usd


def effective_max_runtime(spec: JobSpec, settings: CloudSettings) -> int:
    return spec.limits.max_runtime_s if spec.limits.max_runtime_s is not None else settings.default_max_runtime_s


@dataclass(frozen=True)
class AdmissionSnapshot:
    active_jobs: int
    active_gpu_instances: int
    reserved_usd: float


def admission_blockers(snapshot: AdmissionSnapshot, settings: CloudSettings, needs_gpu: bool,
                       reservation_usd: float) -> List[str]:
    """Why a queued job may not provision yet; empty means admit."""
    out = []
    if snapshot.active_jobs >= settings.max_concurrent_jobs:
        out.append(f"{snapshot.active_jobs} jobs already running (limit {settings.max_concurrent_jobs})")
    if needs_gpu and snapshot.active_gpu_instances >= settings.max_concurrent_gpu_instances:
        out.append(f"{snapshot.active_gpu_instances} GPU instances already running "
                   f"(limit {settings.max_concurrent_gpu_instances})")
    if snapshot.reserved_usd + reservation_usd > settings.max_reserved_usd:
        out.append(f"reserved spend would reach ${snapshot.reserved_usd + reservation_usd:.2f} "
                   f"(limit ${settings.max_reserved_usd:.2f})")
    return out


def budget_alert(month_to_date_usd: float, settings: CloudSettings) -> bool:
    """True once month-to-date spend reaches the warning fraction of the monthly cap."""
    return month_to_date_usd >= settings.warn_cap_fraction * settings.monthly_cap_usd


@dataclass(frozen=True)
class DriftReport:
    key: str
    samples: int
    mean_rel_error: float  # (actual - estimate) / estimate; positive = we under-estimate

    @property
    def flagged(self) -> bool:
        return self.samples >= 3 and abs(self.mean_rel_error) > 0.25


def calibration(pairs: Iterable[Tuple[str, float, float]]) -> Dict[str, DriftReport]:
    """``pairs`` = (catalogue row key, estimate, actual). Rows whose estimates drift get flagged."""
    groups: Mapping[str, List[float]] = defaultdict(list)
    for key, est, act in pairs:
        if est > 0:
            groups[key].append((act - est) / est)
    return {k: DriftReport(k, len(v), statistics.fmean(v)) for k, v in groups.items()}
