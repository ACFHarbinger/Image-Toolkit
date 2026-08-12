"""Optional super-resolution adapter contract."""

from __future__ import annotations

from typing import Any

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable


class SuperResolutionAdapter(ModelAdapter):
    """Model-neutral adapter for an optional super-resolution backend."""

    def __init__(
        self,
        *,
        backend: str = "unavailable",
        weights_uri: str | None = None,
        weights_sha256: str | None = None,
        scale: int = 2,
    ) -> None:
        if scale < 2:
            raise ValueError("super-resolution scale must be at least 2")
        self.scale = scale
        self.spec = ModelSpec(
            name="super-resolution",
            version="0.1",
            task="super_resolution",
            backend=backend,
            weights_uri=weights_uri,
            weights_sha256=weights_sha256,
            metadata={"scale": scale},
        )

    def is_available(self) -> bool:
        return self.spec.backend != "unavailable" and bool(self.spec.weights_uri)

    def propose(self, input_ref: str, **options: Any) -> ModelProposal:
        if not self.is_available():
            raise ModelUnavailable(
                "super-resolution backend or verified weights are unavailable; "
                "install an optional inference extra and configure weights first"
            )
        return ModelProposal(
            operation="upscale",
            confidence=0.0,
            payload={"input_ref": input_ref, "scale": self.scale, "options": options},
            model=self.spec,
        )
