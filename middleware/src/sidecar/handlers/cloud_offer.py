"""Sidecar handler for the run-in-cloud prefill (#852)."""

from __future__ import annotations

from typing import Any


def handle_prefill(params: dict[str, Any]) -> dict[str, Any]:
    # Imported on the call so `import middleware.src.sidecar` stays free of torch.
    from middleware.src.services.cloud_offer.offer import offer_for_vram_refusal

    return offer_for_vram_refusal(
        owner=str(params["owner"]),
        estimated_gb=float(params["estimated_gb"]),
        device_gb=float(params["device_gb"]),
    )
