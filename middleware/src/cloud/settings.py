"""User-editable Cloud Jobs safeguards and defaults.

One source for the cost caps (#832) and the risk-rule thresholds (#830):
rules reference these fields by name as ``settings.<field>``, so changing a
threshold here changes both the warning and the cap.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, Mapping, Optional, Tuple

PACKING_ONE_TO_ONE = "one_to_one"
PACKING_CHAINED = "chained"
PACKING_PARALLEL = "parallel"
PACKING_MODES = (PACKING_ONE_TO_ONE, PACKING_CHAINED, PACKING_PARALLEL)


@dataclass(frozen=True)
class CloudSettings:
    # Which safeguards are on (Harbinger: all of them, each switchable).
    estimates_enabled: bool = True
    warnings_enabled: bool = True
    hard_caps_enabled: bool = True

    # Hard caps.
    default_max_runtime_s: int = 6 * 3600
    default_max_spend_usd: float = 10.0
    monthly_cap_usd: float = 100.0

    # Warning thresholds.
    warn_job_spend_usd: float = 5.0
    warn_runtime_s: int = 3 * 3600
    warn_egress_gb: float = 20.0
    warn_price_age_days: int = 30
    warn_cap_fraction: float = 0.8  # "budget at 80%" notification

    # Admission (jobs past these wait in `queued` and don't provision).
    max_concurrent_jobs: int = 4
    max_concurrent_gpu_instances: int = 2
    max_reserved_usd: float = 50.0

    # Recovery.
    max_attempts: int = 3
    fallback_enabled: bool = False

    # Placement.
    default_regions: Mapping[str, str] = field(default_factory=dict)  # provider -> region
    sensitive_allowlist: Tuple[str, ...] = ()  # providers allowed for sensitive data

    # Instances and retention.
    packing_mode: str = PACKING_ONE_TO_ONE
    share_cache_volumes: bool = True
    history_retention_days: int = 90
    staged_input_ttl_days: int = 0  # 0 = delete right after verified collection
    cache_ttl_days: int = 30
    cache_budget_gb: float = 200.0
    output_retention_days: int = 14

    # Notifications (roadmap: daemon desktop notices plus a webhook or
    # email sink for when the desktop is off — both set in Settings).
    notify_desktop: bool = True
    notify_webhook_url: str = ""
    notify_email: str = ""

    def validate(self) -> None:
        if self.packing_mode not in PACKING_MODES:
            raise ValueError(f"packing_mode must be one of {PACKING_MODES}")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if not 0 < self.warn_cap_fraction <= 1:
            raise ValueError("warn_cap_fraction must be in (0, 1]")

    def default_region(self, provider: str) -> Optional[str]:
        return self.default_regions.get(provider)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["default_regions"] = dict(self.default_regions)
        data["sensitive_allowlist"] = list(self.sensitive_allowlist)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CloudSettings":
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        if "sensitive_allowlist" in kwargs:
            kwargs["sensitive_allowlist"] = tuple(kwargs["sensitive_allowlist"])
        settings = cls(**kwargs)
        settings.validate()
        return settings
