"""Optional neural inpainting & outpainting adapter contract (PyTorch/Diffusers compatible)."""

from __future__ import annotations

from typing import Any

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class InpaintingAdapter(ModelAdapter):
    """Model-neutral inpainting & outpainting adapter with mask and bbox support."""

    def __init__(
        self,
        *,
        backend: str = "unavailable",
        weights_uri: str | None = None,
        weights_sha256: str | None = None,
        model_variant: str = "sd-inpainting",
    ) -> None:
        self.model_variant = model_variant
        self.spec = ModelSpec(
            name="neural-inpainting",
            version="0.1",
            task="inpainting_outpainting",
            backend=backend,
            weights_uri=weights_uri,
            weights_sha256=weights_sha256,
            metadata={"variant": model_variant},
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(
        self,
        input_ref: str,
        *,
        mask_ref: str | None = None,
        strokes: list[dict[str, Any]] | None = None,
        prompt: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        mode: str = "inpaint",
        **options: Any,
    ) -> ModelProposal:
        if not self.is_available():
            raise ModelUnavailable(
                "neural inpainting backend or verified weights are unavailable; "
                "install an optional inference extra and configure weights first"
            )

        if mode not in ("inpaint", "outpaint"):
            raise ValueError(f"Invalid mode '{mode}': must be 'inpaint' or 'outpaint'")

        if mode == "inpaint" and not mask_ref and not strokes:
            raise ValueError(
                "inpaint mode requires either mask_ref (a precomputed mask) or "
                "strokes (raw stroke-guided mask points, rasterized downstream) "
                "so the model knows which region to fill"
            )

        if mode == "outpaint":
            if bbox is None:
                raise ValueError("outpaint mode requires bbox (the canvas expansion rectangle)")
            x0, y0, x1, y1 = bbox
            if not (x1 > x0 and y1 > y0):
                raise ValueError(f"invalid outpaint bbox {bbox}: expected x1 > x0 and y1 > y0")

        payload: dict[str, Any] = {
            "input_ref": input_ref,
            "mask_ref": mask_ref,
            "strokes": strokes,
            "prompt": prompt,
            "bbox": bbox,
            "mode": mode,
            "options": options,
        }

        return ModelProposal(
            operation=f"neural_{mode}",
            confidence=0.0,
            payload=payload,
            model=self.spec,
        )


# Convenient alias
InpaintingModel = InpaintingAdapter

__all__ = ["InpaintingAdapter", "InpaintingModel"]
