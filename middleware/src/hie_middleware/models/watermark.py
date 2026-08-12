"""Optional, consent-gated logo/watermark inpainting contract."""

from __future__ import annotations

from typing import Any

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class WatermarkRemovalAdapter(ModelAdapter):
    """Mask-guided inpainting adapter for images the user may edit."""

    def __init__(self, *, backend: str = "unavailable", weights_uri: str | None = None,
                 weights_sha256: str | None = None) -> None:
        self.spec = ModelSpec(
            name="watermark-inpainting", version="0.1", task="masked_inpainting",
            backend=backend, weights_uri=weights_uri, weights_sha256=weights_sha256,
            metadata={"requires_mask": True, "consent_required": True},
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(self, input_ref: str, **options: Any) -> ModelProposal:
        mask_ref = options.get("mask_ref")
        if not isinstance(mask_ref, str) or not mask_ref.strip():
            raise ValueError("watermark inpainting requires a user-supplied mask_ref")
        if options.get("permission_confirmed") is not True:
            raise PermissionError("confirm ownership or permission before removal")
        if not self.is_available():
            raise ModelUnavailable("watermark inpainting backend or verified weights are unavailable")
        return ModelProposal(
            "masked_inpainting", 0.0,
            {"input_ref": input_ref, "mask_ref": mask_ref, "options": options}, self.spec,
        )
