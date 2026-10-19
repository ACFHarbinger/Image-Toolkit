"""Optional alpha-matting adapter contract (BiRefNet/FastSAM compatible)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class MattingAdapter(ModelAdapter):
    """Model-neutral matting adapter for BiRefNet and FastSAM alpha matting backends."""

    def __init__(
        self,
        *,
        backend: str = "unavailable",
        weights_uri: str | None = None,
        weights_sha256: str | None = None,
        model_variant: str = "birefnet-general",
    ) -> None:
        self.model_variant = model_variant
        self.spec = ModelSpec(
            name="alpha-matting",
            version="0.2",
            task="alpha_matte",
            backend=backend,
            weights_uri=weights_uri,
            weights_sha256=weights_sha256,
            metadata={"model_variant": model_variant},
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(
        self,
        input_ref: str,
        *,
        fg_points: List[Tuple[int, int]] | None = None,
        bg_points: List[Tuple[int, int]] | None = None,
        box: Tuple[int, int, int, int] | None = None,
        feather_radius: int = 0,
        **options: Any,
    ) -> ModelProposal:
        if not self.is_available():
            raise ModelUnavailable(
                "alpha-matting backend or verified weights are unavailable; "
                "install an optional inference extra and configure weights first"
            )

        payload: Dict[str, Any] = {
            "input_ref": input_ref,
            "fg_points": fg_points or [],
            "bg_points": bg_points or [],
            "box": box,
            "feather_radius": feather_radius,
            "options": options,
        }

        return ModelProposal(
            operation="matting",
            confidence=0.95 if (fg_points or box) else 0.85,
            payload=payload,
            model=self.spec,
        )


MattingModel = MattingAdapter

__all__ = ["MattingAdapter", "MattingModel"]
