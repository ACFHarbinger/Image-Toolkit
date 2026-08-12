"""Optional super-resolution adapter contract."""

from __future__ import annotations

from typing import Any, Dict

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class SuperResolutionAdapter(ModelAdapter):
    """Model-neutral adapter for an optional super-resolution backend (Real-ESRGAN/Real-ESRNet)."""

    def __init__(
        self,
        *,
        backend: str = "unavailable",
        weights_uri: str | None = None,
        weights_sha256: str | None = None,
        scale: int = 2,
        model_variant: str = "RealESRGAN_x4plus",
        tile_size: int = 512,
    ) -> None:
        if scale < 2 or scale > 8:
            raise ValueError("super-resolution scale must be between 2 and 8")
        self.scale = scale
        self.model_variant = model_variant
        self.tile_size = tile_size
        self.spec = ModelSpec(
            name="super-resolution",
            version="0.2",
            task="super_resolution",
            backend=backend,
            weights_uri=weights_uri,
            weights_sha256=weights_sha256,
            metadata={
                "scale": scale,
                "model_variant": model_variant,
                "tile_size": tile_size,
            },
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(
        self,
        input_ref: str,
        *,
        scale: int | None = None,
        tile_size: int | None = None,
        **options: Any,
    ) -> ModelProposal:
        if not self.is_available():
            raise ModelUnavailable(
                "super-resolution backend or verified weights are unavailable; "
                "install an optional inference extra and configure weights first"
            )

        active_scale = scale or self.scale
        active_tile = tile_size or self.tile_size

        if active_scale < 2 or active_scale > 8:
            raise ValueError("super-resolution scale must be between 2 and 8")

        payload: Dict[str, Any] = {
            "input_ref": input_ref,
            "scale": active_scale,
            "tile_size": active_tile,
            "model_variant": self.model_variant,
            "options": options,
        }

        return ModelProposal(
            operation="upscale",
            confidence=0.9,
            payload=payload,
            model=self.spec,
        )


SuperResModel = SuperResolutionAdapter

__all__ = ["SuperResolutionAdapter", "SuperResModel"]
