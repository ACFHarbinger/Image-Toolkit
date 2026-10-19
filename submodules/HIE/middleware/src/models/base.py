"""Dependency-light contracts for optional neural model adapters.

Heavy PyTorch/ONNX dependencies and weights stay optional. UI and pipeline
code can inspect model metadata and receive structured errors without importing
an unavailable runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    name: str
    version: str
    task: str
    backend: str = "unavailable"
    weights_uri: str | None = None
    weights_sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelProposal:
    """An inspectable model output; accepting it is a separate UI action."""

    operation: str
    confidence: float
    payload: dict[str, Any] = field(default_factory=dict)
    model: ModelSpec | None = None


class ModelUnavailable(RuntimeError):
    """Raised when an optional inference backend or weight artifact is absent."""


class ModelAdapter(ABC):
    """Common lifecycle and inference boundary for neural model adapters."""

    spec: ModelSpec

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the configured backend and weights can run locally."""

    @abstractmethod
    def propose(self, input_ref: str, **options: Any) -> ModelProposal:
        """Return a preview proposal without mutating a document."""

