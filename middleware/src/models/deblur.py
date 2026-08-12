"""Optional image deblurring model contract."""

from __future__ import annotations

from typing import Any, Dict

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class DeblurAdapter(ModelAdapter):
    """Model-neutral adapter for blind/non-blind blur restoration backends."""

    def __init__(
        self,
        *,
        backend: str = "unavailable",
        weights_uri: str | None = None,
        weights_sha256: str | None = None,
        method: str = "blind",
    ) -> None:
        if method not in {"blind", "non_blind"}:
            raise ValueError("deblur method must be 'blind' or 'non_blind'")
        self.method = method
        self.spec = ModelSpec(
            name="image-deblur",
            version="0.2",
            task="deblur",
            backend=backend,
            weights_uri=weights_uri,
            weights_sha256=weights_sha256,
            metadata={"method": method},
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(
        self,
        input_ref: str,
        *,
        kernel_size: int = 15,
        strength: float = 1.0,
        psf_estimate: str | None = None,
        **options: Any,
    ) -> ModelProposal:
        if not self.is_available():
            raise ModelUnavailable("deblur backend or verified weights are unavailable")

        if kernel_size < 3 or kernel_size % 2 == 0:
            raise ValueError("kernel_size must be an odd integer >= 3")
        if not 0.0 <= strength <= 2.0:
            raise ValueError("strength must be between 0.0 and 2.0")

        payload: Dict[str, Any] = {
            "input_ref": input_ref,
            "method": self.method,
            "kernel_size": kernel_size,
            "strength": strength,
            "psf_estimate": psf_estimate,
            "options": options,
        }

        confidence = 0.9 if psf_estimate else 0.8

        return ModelProposal("deblur", confidence, payload, self.spec)


DeblurModel = DeblurAdapter

__all__ = ["DeblurAdapter", "DeblurModel"]
