"""Optional alpha-matting adapter contract (BiRefNet/FastSAM compatible)."""

from __future__ import annotations

from typing import Any

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class MattingAdapter(ModelAdapter):
    """Model-neutral matting adapter; a backend is injected by deployment code."""

    def __init__(self, *, backend: str = "unavailable", weights_uri: str | None = None,
                 weights_sha256: str | None = None) -> None:
        self.spec = ModelSpec(
            name="alpha-matting", version="0.1", task="alpha_matte",
            backend=backend, weights_uri=weights_uri, weights_sha256=weights_sha256,
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(self, input_ref: str, **options: Any) -> ModelProposal:
        if not self.is_available():
            raise ModelUnavailable(
                "alpha-matting backend or verified weights are unavailable; "
                "install an optional inference extra and configure weights first"
            )
        return ModelProposal(
            operation="matting",
            confidence=0.0,
            payload={"input_ref": input_ref, "options": options},
            model=self.spec,
        )

