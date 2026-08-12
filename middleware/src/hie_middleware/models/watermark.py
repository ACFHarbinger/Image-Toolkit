"""Optional, consent-gated logo/watermark inpainting contract."""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable

_audit_log = logging.getLogger("hie_middleware.watermark_removal.audit")

#: Fallback confidence used when the caller hasn't computed `mask_coverage`
#: yet (e.g. `validate_inpainting_mask` runs later, in the runner) — matches
#: this adapter's confidence before coverage-based scoring was added, so
#: existing callers that don't pass `mask_coverage` see no behavior change.
_DEFAULT_CONFIDENCE = 0.92


def _confidence_from_coverage(mask_coverage: float) -> float:
    """Coverage-based confidence: smaller, more localized masks score higher.

    Watermarks/logos are typically small marks; a large mask is more likely
    an imprecise selection that will blend poorly, not a genuine watermark
    removal — this generally agrees with `validate_inpainting_mask`'s
    coverage safety limit (default max 50%) elsewhere in this package,
    without duplicating its hard rejection here (this adapter doesn't know
    the caller's chosen `max_coverage`). Floored at 0.5 rather than decaying
    to 0 — a rejected-by-`validate_inpainting_mask` mask never reaches this
    adapter anyway, so within the accepted range a "somewhat less certain"
    floor is more honest than an artificially low score.
    """
    return max(0.5, min(0.95, 0.95 - mask_coverage * 0.6))


class WatermarkRemovalAdapter(ModelAdapter):
    """Mask-guided inpainting adapter for images the user may edit."""

    def __init__(
        self,
        *,
        backend: str = "unavailable",
        weights_uri: str | None = None,
        weights_sha256: str | None = None,
    ) -> None:
        self.spec = ModelSpec(
            name="watermark-inpainting",
            version="0.2",
            task="masked_inpainting",
            backend=backend,
            weights_uri=weights_uri,
            weights_sha256=weights_sha256,
            metadata={"requires_mask": True, "consent_required": True},
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(
        self,
        input_ref: str,
        *,
        mask_ref: str | None = None,
        permission_confirmed: bool = False,
        edge_blur: int = 2,
        preserve_texture: bool = True,
        mask_coverage: float | None = None,
        **options: Any,
    ) -> ModelProposal:
        if not isinstance(mask_ref, str) or not mask_ref.strip():
            raise ValueError("watermark inpainting requires a user-supplied mask_ref")
        if permission_confirmed is not True:
            raise PermissionError("confirm ownership or permission before removal")
        if not self.is_available():
            raise ModelUnavailable("watermark inpainting backend or verified weights are unavailable")

        if mask_coverage is not None:
            if not 0.0 < mask_coverage < 1.0:
                raise ValueError("mask_coverage must be between 0 and 1 (exclusive)")
            confidence = _confidence_from_coverage(mask_coverage)
        else:
            confidence = _DEFAULT_CONFIDENCE

        # Audit trail: every fully-validated, permission-confirmed removal
        # request is logged (input/mask references only — no pixel data) so
        # a consent dispute can be traced later. Fires only after every
        # validation above passes, so it's a record of accepted requests,
        # not attempts.
        _audit_log.info(
            "watermark removal permission confirmed",
            extra={"input_ref": input_ref, "mask_ref": mask_ref, "mask_coverage": mask_coverage},
        )

        payload: Dict[str, Any] = {
            "input_ref": input_ref,
            "mask_ref": mask_ref,
            "edge_blur": edge_blur,
            "preserve_texture": preserve_texture,
            "mask_coverage": mask_coverage,
            "options": options,
        }

        return ModelProposal(
            "masked_inpainting",
            confidence,
            payload,
            self.spec,
        )


WatermarkModel = WatermarkRemovalAdapter

__all__ = ["WatermarkRemovalAdapter", "WatermarkModel"]
