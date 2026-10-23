"""Cloud offer when local GPU admission refuses (#852)."""

from middleware.src.services.cloud_offer.offer import offer_for_vram_refusal

__all__ = ["offer_for_vram_refusal"]
