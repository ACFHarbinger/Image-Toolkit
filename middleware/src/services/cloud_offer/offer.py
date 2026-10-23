"""Prefill a cloud job when local VRAM admission refuses (#852).

The threshold matches ``gpu_lease_arbiter`` (conservative fraction of device
VRAM). Building the spec does not submit it.
"""

from __future__ import annotations

from typing import Any

from middleware.src.cloud.cost.catalogue import PriceCatalogue
from middleware.src.cloud.cost.estimate import estimate
from middleware.src.cloud.spec import (
    ExecutionMode,
    JobSpec,
    Placement,
    Resources,
    ShardSpec,
    WorkloadKind,
)

# Same ceiling as gpu_lease_arbiter.CONSERVATIVE_VRAM_FRACTION. Kept as a
# number so this module does not import middleware.src.core: that package
# init loads image and video code, which pulls torch into the sidecar.
PREFILL_VRAM_FRACTION = 0.90
PREFILL_RUNTIME_S = 600.0
PREFILL_PROVIDER = "gcp"
PREFILL_REGION = "us-central1"


def _empty(reason: str) -> dict[str, Any]:
    return {
        "offered": False,
        "submitted": False,
        "reason": reason,
        "estimate_usd": 0.0,
        "estimate_known": False,
        "kind": "",
        "vram_gb_min": 0.0,
        "provider": "",
        "region": "",
        "runtime_s": 0.0,
        "job_id": "",
    }


def offer_for_vram_refusal(
    *,
    owner: str,
    estimated_gb: float,
    device_gb: float,
    catalogue: PriceCatalogue | None = None,
) -> dict[str, Any]:
    """Return a prefilled spec when the estimate exceeds the arbiter ceiling."""
    ceiling = PREFILL_VRAM_FRACTION * device_gb
    if device_gb <= 0 or estimated_gb <= ceiling:
        return _empty("local admission was not refused for VRAM")
    kind = WorkloadKind.LORA_TRAIN if "train" in owner.lower() else WorkloadKind.COMFY_BATCH
    spec = JobSpec(
        kind=kind,
        placement=Placement(
            provider=PREFILL_PROVIDER,
            region=PREFILL_REGION,
            mode=ExecutionMode.INSTANCE,
        ),
        shards=(ShardSpec(index=0),),
        resources=Resources(gpu_count=1, gpu_class="gpu", vram_gb_min=estimated_gb),
        params={"expected_runtime_s": PREFILL_RUNTIME_S},
        title=owner,
    )
    spec.validate()
    priced = estimate(spec, catalogue if catalogue is not None else PriceCatalogue.load())
    return {
        "offered": True,
        "submitted": False,
        "reason": (
            f"GPU admission refused: estimated {estimated_gb:.1f} GB exceeds "
            f"{PREFILL_VRAM_FRACTION:.0%} of {device_gb:.1f} GB device VRAM "
            "(conservative profile)."
        ),
        "estimate_usd": priced.total_usd if priced.known else 0.0,
        "estimate_known": priced.known,
        "kind": kind.value,
        "vram_gb_min": estimated_gb,
        "provider": PREFILL_PROVIDER,
        "region": PREFILL_REGION,
        "runtime_s": PREFILL_RUNTIME_S,
        "job_id": spec.job_id,
    }
