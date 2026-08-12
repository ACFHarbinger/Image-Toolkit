"""Optional image deblurring model contract."""

from __future__ import annotations

from typing import Any

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class DeblurAdapter(ModelAdapter):
    """Model-neutral adapter for blind/non-blind blur restoration backends."""

    def __init__(self, *, backend: str = "unavailable", weights_uri: str | None = None,
                 weights_sha256: str | None = None, method: str = "blind") -> None:
        if method not in {"blind", "non_blind"}:
            raise ValueError("deblur method must be 'blind' or 'non_blind'")
        self.spec = ModelSpec(
            name="image-deblur", version="0.1", task="deblur", backend=backend,
            weights_uri=weights_uri, weights_sha256=weights_sha256,
            metadata={"method": method},
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(self, input_ref: str, **options: Any) -> ModelProposal:
        if not self.is_available():
            raise ModelUnavailable("deblur backend or verified weights are unavailable")
        return ModelProposal("deblur", 0.0, {"input_ref": input_ref, "options": options}, self.spec)
