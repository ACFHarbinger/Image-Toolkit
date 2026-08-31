"""Usage-row model + aggregation for the Cloud Compute Dashboards tab (#490).

Qt-free. Accepts worker ``usage.json`` (``infra/cloud/gcd/worker/server.py``)
and the looser UI dicts ``DashboardsPane.add_usage_row`` already takes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

# Cloud Run CPU-flex list prices (us-central1, approx) used when the worker
# did not attach a cost. Egress is Cloud-to-internet.
_VCPU_USD_PER_SEC = 0.00002400
_GIB_USD_PER_SEC = 0.00000250
_EGRESS_USD_PER_GIB = 0.12

_STATUS_SUCCESS = "success"
_STATUS_ERROR = "error"
_STATUS_IN_FLIGHT = "in_flight"


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().replace(",", "")
    if text in ("in flight", "pending", "running", "n/a", "-"):
        return default
    match = re.match(r"^\$?\s*([0-9]*\.?[0-9]+)", text)
    if not match:
        return default
    return float(match.group(1))


def parse_duration_seconds(value: Any) -> float:
    """``14.2``, ``"14.2s"``, ``"1m 30s"``, ``"In Flight"`` → seconds."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, float(value))
    text = str(value).strip().lower()
    if text in ("in flight", "pending", "running", "n/a", "-"):
        return 0.0
    if text.endswith("s") and "m" not in text and "h" not in text:
        return max(0.0, _as_float(text[:-1]))
    hours = minutes = seconds = 0.0
    for num, unit in re.findall(r"([0-9]*\.?[0-9]+)\s*([hms])", text):
        n = float(num)
        if unit == "h":
            hours = n
        elif unit == "m":
            minutes = n
        else:
            seconds = n
    if hours or minutes or seconds:
        return hours * 3600 + minutes * 60 + seconds
    return max(0.0, _as_float(text))


def parse_bytes(value: Any) -> int:
    """``1234``, ``"28.5 MB"``, ``"1.2 GiB"`` → bytes."""
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    text = str(value).strip().upper().replace(",", "")
    match = re.match(r"^~?\s*([0-9]*\.?[0-9]+)\s*([KMGT]I?B)?$", text)
    if not match:
        return 0
    n = float(match.group(1))
    unit = match.group(2) or "B"
    mul = {
        "B": 1,
        "KB": 1000,
        "KIB": 1024,
        "MB": 1000**2,
        "MIB": 1024**2,
        "GB": 1000**3,
        "GIB": 1024**3,
        "TB": 1000**4,
        "TIB": 1024**4,
    }.get(unit, 1)
    return max(0, int(n * mul))


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.1f}s" if seconds < 10 else f"{int(round(seconds))}s"
    minutes, sec = divmod(int(round(seconds)), 60)
    if minutes < 60:
        return f"{minutes}m {sec}s" if sec else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def format_bytes(n: int) -> str:
    if n <= 0:
        return "0 B"
    for unit, size in (("TB", 1000**4), ("GB", 1000**3), ("MB", 1000**2), ("KB", 1000)):
        if n >= size:
            val = n / size
            return f"{val:.1f} {unit}" if val < 10 else f"{val:.0f} {unit}"
    return f"{n} B"


def format_usd(amount: float) -> str:
    if amount <= 0:
        return "$0.00"
    if amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def estimate_cost_usd(
    duration_seconds: float,
    peak_rss_kib: float = 0.0,
    egress_bytes: int = 0,
    peak_vcpu: float = 1.0,
) -> float:
    if duration_seconds <= 0:
        return 0.0
    vcpu = peak_vcpu if peak_vcpu > 0 else 1.0
    gib = max(peak_rss_kib, 0.0) / (1024.0 * 1024.0)
    compute = duration_seconds * (vcpu * _VCPU_USD_PER_SEC + gib * _GIB_USD_PER_SEC)
    egress = (egress_bytes / (1024.0**3)) * _EGRESS_USD_PER_GIB
    return compute + egress


def _normalize_status(raw: Any, duration_label: Any = None) -> str:
    text = str(raw or "").strip().lower()
    if text in ("error", "failed", "failure"):
        return _STATUS_ERROR
    if text in ("in_flight", "inflight", "pending", "running"):
        return _STATUS_IN_FLIGHT
    if text in ("success", "ok", "done"):
        return _STATUS_SUCCESS
    label = str(duration_label or "").strip().lower()
    if label in ("in flight", "pending", "running"):
        return _STATUS_IN_FLIGHT
    return _STATUS_SUCCESS if text == "" else _STATUS_ERROR


@dataclass(frozen=True)
class UsageRow:
    """One cloud-job usage record."""

    job_id: str
    provider: str
    task: str
    status: str
    duration_seconds: float = 0.0
    timestamp: str = ""
    peak_rss_kib: float = 0.0
    peak_vcpu: float = 0.0
    peak_gpu: float = 0.0
    egress_bytes: int = 0
    cost_usd: float = 0.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "UsageRow":
        duration = parse_duration_seconds(
            data.get("duration_seconds", data.get("duration"))
        )
        rss = _as_float(data.get("peak_rss_kib", data.get("peak_memory_kib", 0)))
        vcpu = _as_float(data.get("peak_vcpu", data.get("vcpu", 0)))
        gpu = _as_float(data.get("peak_gpu", data.get("gpu", 0)))
        egress = parse_bytes(data.get("egress_bytes", data.get("egress", 0)))
        given_cost = data.get("cost_usd", data.get("cost"))
        cost = _as_float(given_cost) if given_cost not in (None, "") else 0.0
        if cost <= 0:
            cost = estimate_cost_usd(duration, rss, egress, vcpu)
        provider = str(data.get("provider", "") or "unknown")
        return cls(
            job_id=str(data.get("job_id", "") or ""),
            provider=provider.lower(),
            task=str(data.get("task", data.get("task_type", "")) or ""),
            status=_normalize_status(data.get("status"), data.get("duration")),
            duration_seconds=duration,
            timestamp=str(data.get("timestamp", data.get("created_at", "")) or ""),
            peak_rss_kib=rss,
            peak_vcpu=vcpu,
            peak_gpu=gpu,
            egress_bytes=egress,
            cost_usd=cost,
        )


@dataclass(frozen=True)
class ProviderStats:
    provider: str
    jobs: int = 0
    successes: int = 0
    failures: int = 0
    duration_seconds: float = 0.0
    egress_bytes: int = 0
    cost_usd: float = 0.0
    peak_rss_kib: float = 0.0

    @property
    def success_rate(self) -> float:
        finished = self.successes + self.failures
        return (self.successes / finished) if finished else 0.0


@dataclass(frozen=True)
class UsageSummary:
    total_jobs: int = 0
    successes: int = 0
    failures: int = 0
    in_flight: int = 0
    total_duration_seconds: float = 0.0
    total_egress_bytes: int = 0
    total_cost_usd: float = 0.0
    peak_rss_kib: float = 0.0
    by_provider: Dict[str, ProviderStats] = field(default_factory=dict)
    series: List[UsageRow] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        finished = self.successes + self.failures
        return (self.successes / finished) if finished else 1.0

    @property
    def total_jobs_label(self) -> str:
        return str(self.total_jobs)

    @property
    def compute_time_label(self) -> str:
        return format_duration(self.total_duration_seconds)

    @property
    def egress_label(self) -> str:
        return format_bytes(self.total_egress_bytes)

    @property
    def cost_label(self) -> str:
        return format_usd(self.total_cost_usd)

    @property
    def success_rate_label(self) -> str:
        return f"{self.success_rate * 100:.0f}%"


class UsageRowSource:
    """In-memory row store. Swap later for live provider metrics."""

    def __init__(self, rows: Optional[Sequence[UsageRow]] = None) -> None:
        self._rows: List[UsageRow] = list(rows or [])

    def add(self, row: UsageRow) -> None:
        self._rows.append(row)

    def load_rows(self) -> List[UsageRow]:
        return list(self._rows)

    def clear(self) -> None:
        self._rows.clear()


def aggregate_usage_rows(rows: Iterable[UsageRow]) -> UsageSummary:
    series = list(rows)
    successes = failures = in_flight = 0
    duration = 0.0
    egress = 0
    cost = 0.0
    peak = 0.0
    providers: Dict[str, Dict[str, Any]] = {}
    for row in series:
        if row.status == _STATUS_IN_FLIGHT:
            in_flight += 1
        elif row.status == _STATUS_ERROR:
            failures += 1
        else:
            successes += 1
        duration += row.duration_seconds
        egress += row.egress_bytes
        cost += row.cost_usd
        peak = max(peak, row.peak_rss_kib)
        bucket = providers.setdefault(
            row.provider,
            {
                "jobs": 0,
                "successes": 0,
                "failures": 0,
                "duration": 0.0,
                "egress": 0,
                "cost": 0.0,
                "peak": 0.0,
            },
        )
        bucket["jobs"] += 1
        if row.status == _STATUS_ERROR:
            bucket["failures"] += 1
        elif row.status != _STATUS_IN_FLIGHT:
            bucket["successes"] += 1
        bucket["duration"] += row.duration_seconds
        bucket["egress"] += row.egress_bytes
        bucket["cost"] += row.cost_usd
        bucket["peak"] = max(bucket["peak"], row.peak_rss_kib)
    by_provider = {
        name: ProviderStats(
            provider=name,
            jobs=int(b["jobs"]),
            successes=int(b["successes"]),
            failures=int(b["failures"]),
            duration_seconds=float(b["duration"]),
            egress_bytes=int(b["egress"]),
            cost_usd=float(b["cost"]),
            peak_rss_kib=float(b["peak"]),
        )
        for name, b in sorted(providers.items())
    }
    return UsageSummary(
        total_jobs=len(series),
        successes=successes,
        failures=failures,
        in_flight=in_flight,
        total_duration_seconds=duration,
        total_egress_bytes=egress,
        total_cost_usd=cost,
        peak_rss_kib=peak,
        by_provider=by_provider,
        series=series,
    )


__all__ = [
    "ProviderStats",
    "UsageRow",
    "UsageRowSource",
    "UsageSummary",
    "aggregate_usage_rows",
    "estimate_cost_usd",
    "format_bytes",
    "format_duration",
    "format_usd",
    "parse_bytes",
    "parse_duration_seconds",
]
