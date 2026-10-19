"""Deterministic total-job cost estimates and candidate ranking (#832).

An estimate is a pure function of (spec, placement, catalogue, runtime
model); the rows it used are snapshotted with the job so it can be replayed.
"Cheapest" means estimated *total* job cost: startup, compute with billing
rounding, IPv4, staging storage, egress, and expected retries.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..adapter import CapabilityManifest
from ..spec import JobSpec, Placement
from .catalogue import ComputePrice, PriceCatalogue, age_days, snapshot

_GB = 1024 ** 3
DEFAULT_RETRY_RATE = 0.1  # expected extra attempts per job; calibrated from the ledger over time


@dataclass(frozen=True)
class Estimate:
    known: bool
    total_usd: float = 0.0
    compute_usd: float = 0.0
    startup_usd: float = 0.0
    ipv4_usd: float = 0.0
    storage_usd: float = 0.0
    egress_usd: float = 0.0
    retries_usd: float = 0.0
    runtime_s: float = 0.0
    billed_s: float = 0.0
    egress_gb: float = 0.0
    upload_gb: float = 0.0
    price_age_days: Optional[int] = None
    rows: Tuple[Dict[str, Any], ...] = ()
    missing: Tuple[str, ...] = ()

    def breakdown(self) -> Dict[str, float]:
        return {"compute": self.compute_usd, "startup": self.startup_usd, "ipv4": self.ipv4_usd,
                "storage": self.storage_usd, "egress": self.egress_usd, "retries": self.retries_usd,
                "total": self.total_usd}


def sku_for(spec: JobSpec, placement: Optional[Placement] = None) -> str:
    pl = placement or spec.placement
    return pl.instance_type or spec.resources.gpu_class or "cpu"


def expected_runtime_s(spec: JobSpec) -> float:
    """Caller-provided model: ``params.expected_runtime_s`` or per-shard × shards."""
    if "expected_runtime_s" in spec.params:
        return float(spec.params["expected_runtime_s"])
    per_shard = float(spec.params.get("expected_shard_s", 0.0))
    return per_shard * len(spec.shards)


def _billed(seconds: float, price: ComputePrice) -> float:
    inc = max(1, price.billing_increment_s)
    return max(float(price.minimum_s), math.ceil(seconds / inc) * inc)


def estimate(spec: JobSpec, catalogue: PriceCatalogue, placement: Optional[Placement] = None,
             today: Optional[_dt.date] = None, retry_rate: float = DEFAULT_RETRY_RATE,
             runtime_s: Optional[float] = None) -> Estimate:
    pl = placement or spec.placement
    today = today or _dt.date.today()
    runtime = expected_runtime_s(spec) if runtime_s is None else runtime_s
    upload_gb = sum(b.size_bytes for b in spec.inputs.values()) / _GB
    egress_gb = float(spec.params.get("expected_output_gb", 0.0))

    price = catalogue.compute(pl.provider, pl.region, pl.mode.value, sku_for(spec, pl), spec.limits.spot_allowed)
    if price is None:
        return Estimate(False, runtime_s=runtime, egress_gb=egress_gb, upload_gb=upload_gb,
                        missing=(f"compute {pl.provider}/{pl.region}/{pl.mode.value}/{sku_for(spec, pl)}",))
    eg = catalogue.egress(pl.provider)
    st = catalogue.storage(pl.provider)

    billed = _billed(price.startup_s + runtime, price)
    hourly = price.usd_per_hour / 3600.0
    startup_usd = min(price.startup_s, billed) * hourly
    compute_usd = billed * hourly - startup_usd
    ipv4_usd = billed / 3600.0 * price.ipv4_usd_per_hour
    staged_days = max(1.0, billed / 86400.0)
    storage_usd = (st.usd_per_gb_month * (upload_gb + egress_gb) * staged_days / 30.0) if st else 0.0
    egress_usd = eg.usd_per_gb * egress_gb if eg else 0.0
    base = startup_usd + compute_usd + ipv4_usd
    retries_usd = base * retry_rate
    total = base + storage_usd + egress_usd + retries_usd

    ages = [a for a in (age_days(r.last_verified, today) for r in (price, eg, st) if r is not None)
            if a is not None]
    missing = tuple(m for m, needed in (
        ("egress", eg is None and egress_gb > 0),
        ("storage", st is None and egress_gb + upload_gb > 0),
        ("runtime", runtime <= 0),
    ) if needed)
    return Estimate(not missing, round(total, 4), compute_usd, startup_usd, ipv4_usd, storage_usd, egress_usd,
                    retries_usd, runtime, billed, egress_gb, upload_gb,
                    max(ages) if ages else None, tuple(snapshot((price, eg, st))), missing)


@dataclass(frozen=True)
class Candidate:
    placement: Placement
    estimate: Estimate
    compatible: bool
    same_region: bool
    meets_deadline: bool
    notes: Tuple[str, ...] = field(default_factory=tuple)


def rank_candidates(spec: JobSpec, placements: Sequence[Placement], catalogue: PriceCatalogue,
                    manifests: Mapping[str, CapabilityManifest], default_regions: Mapping[str, str],
                    now: float, deadline_ts: Optional[float] = None,
                    today: Optional[_dt.date] = None) -> List[Candidate]:
    """Compatible first; then those meeting the deadline; same-region; then by total cost."""
    out: List[Candidate] = []
    for pl in placements:
        man = manifests.get(pl.provider)
        compatible = man is not None and man.supports(pl.mode, spec.resources.needs_gpu)
        est = estimate(spec, catalogue, pl, today=today)
        same_region = default_regions.get(pl.provider, pl.region) == pl.region
        finish = now + (est.billed_s or est.runtime_s)
        meets = deadline_ts is None or finish <= deadline_ts
        notes = []
        if not same_region:
            notes.append("moves data across regions")
        if not est.known:
            notes.append("no price data")
        out.append(Candidate(pl, est, compatible, same_region, meets, tuple(notes)))

    def key(c: Candidate) -> Tuple[Any, ...]:
        return (not c.compatible, not c.meets_deadline, not c.estimate.known, not c.same_region,
                c.estimate.total_usd)

    return sorted(out, key=key)


def cheaper_cross_region(ranked: Sequence[Candidate]) -> Optional[Candidate]:
    """The cheapest cross-region option, if it beats the best same-region one (for the warning)."""
    usable = [c for c in ranked if c.compatible and c.meets_deadline and c.estimate.known]
    same = [c for c in usable if c.same_region]
    cross = [c for c in usable if not c.same_region]
    if not same or not cross:
        return None
    best_cross = min(cross, key=lambda c: c.estimate.total_usd)
    return best_cross if best_cross.estimate.total_usd < same[0].estimate.total_usd else None
