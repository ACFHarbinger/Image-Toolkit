"""VRAM refusal prefills a cloud spec and does not submit (#852)."""

from __future__ import annotations

from middleware.src.cloud.cost.catalogue import ComputePrice, PriceCatalogue
from middleware.src.core.gpu_lease_arbiter import CONSERVATIVE_VRAM_FRACTION
from middleware.src.services.cloud_offer.offer import PREFILL_VRAM_FRACTION, offer_for_vram_refusal

CATALOGUE = PriceCatalogue(
    [
        ComputePrice(
            provider="gcp",
            region="us-central1",
            mode="instance",
            sku="gpu",
            usd_per_hour=3.6,
            last_verified="2026-10-01",
        )
    ]
)


def test_the_ceiling_matches_the_arbiter() -> None:
    assert PREFILL_VRAM_FRACTION == CONSERVATIVE_VRAM_FRACTION


def test_a_fitting_estimate_is_not_offered() -> None:
    result = offer_for_vram_refusal(owner="generate", estimated_gb=1.0, device_gb=10.0)
    assert result["offered"] is False
    assert result["submitted"] is False
    assert result["job_id"] == ""


def test_a_vram_refusal_prefills_a_priced_spec() -> None:
    result = offer_for_vram_refusal(
        owner="train-lora",
        estimated_gb=9.1,
        device_gb=10.0,
        catalogue=CATALOGUE,
    )
    assert result["offered"] is True
    assert result["submitted"] is False
    assert result["kind"] == "lora_train"
    assert result["vram_gb_min"] == 9.1
    assert result["provider"] == "gcp"
    assert result["region"] == "us-central1"
    assert result["runtime_s"] == 600.0
    assert result["estimate_known"] is True
    assert result["estimate_usd"] > 0
    assert result["job_id"].startswith("cj-")
