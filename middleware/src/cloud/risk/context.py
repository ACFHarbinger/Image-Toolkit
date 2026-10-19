"""Flatten a job + provider facts + estimate + settings into the rule context (#830)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..adapter import CapabilityManifest
from ..cost.caps import effective_max_runtime, effective_max_spend
from ..cost.estimate import Estimate
from ..settings import CloudSettings
from ..spec import JobSpec


def build_context(
    spec: JobSpec,
    manifest: Optional[CapabilityManifest],
    estimate: Estimate,
    settings: CloudSettings,
    month_to_date_usd: float = 0.0,
    watchdog_configured: bool = False,
) -> Dict[str, Any]:
    pl, res = spec.placement, spec.resources
    ctx: Dict[str, Any] = {
        "placement.provider": pl.provider,
        "placement.region": pl.region,
        "placement.mode": pl.mode.value,
        "placement.instance_type": pl.instance_type or "",
        "resources.needs_gpu": res.needs_gpu,
        "resources.gpu_class": res.gpu_class or "",
        "resources.gpu_count": res.gpu_count,
        "storage": spec.storage.value,
        "data_class": spec.data_class.value,
        "image": spec.image,
        "limits.spot_allowed": spec.limits.spot_allowed,
        "limits.max_spend_usd": spec.limits.max_spend_usd,
        "limits.max_runtime_s": spec.limits.max_runtime_s,
        "limits.effective_max_spend_usd": effective_max_spend(spec, settings),
        "limits.effective_max_runtime_s": effective_max_runtime(spec, settings),
        "job.kind": spec.kind.value,
        "job.resumable": spec.resumable,
        "job.data_class": spec.data_class.value,
        "job.shards": len(spec.shards),
        "job.provider_allowlisted": pl.provider in settings.sensitive_allowlist,
        "job.cross_region": (settings.default_region(pl.provider) or pl.region) != pl.region,
        "job.user_image": bool(spec.params.get("user_image", False)),
        "job.workers_ai_translation": bool(spec.params.get("workers_ai_translation", False)),
        "estimate.known": estimate.known,
        "estimate.total_usd": round(estimate.total_usd, 2),
        "estimate.runtime_s": int(estimate.runtime_s),
        "estimate.egress_gb": round(estimate.egress_gb, 2),
        "estimate.upload_gb": round(estimate.upload_gb, 2),
        "estimate.price_age_days": estimate.price_age_days,
        "spend.month_to_date_usd": round(month_to_date_usd, 2),
        "spend.month_after_job_usd": round(month_to_date_usd + estimate.total_usd, 2),
        "env.watchdog_configured": watchdog_configured,
    }
    ctx.update({f"settings.{k}": v for k, v in settings.to_dict().items()
                if isinstance(v, (int, float, bool, str))})
    if manifest is not None:
        ctx.update(_capability_facts(spec, manifest))
    return ctx


def _capability_facts(spec: JobSpec, man: CapabilityManifest) -> Dict[str, Any]:
    pl, res = spec.placement, spec.resources
    return {
        "cap.mode_supported": pl.mode in man.modes,
        "cap.mode_cpu_only": pl.mode in man.cpu_only_modes,
        "cap.gpu_class_offered": (not res.gpu_class) or res.gpu_class in man.gpu_classes,
        "cap.storage_supported": spec.storage in man.storage,
        "cap.max_task_s": int(man.max_task_seconds.get(pl.mode.value, 0)),
        "cap.supports_spot": man.supports_spot,
        "cap.region_known": (not man.regions) or pl.region in man.regions,
        "cap.native_deadline": man.native_deadline,
        "cap.third_party_gpu_host": man.third_party_gpu_host,
        "cap.verified_on": man.verified_on,
    }
