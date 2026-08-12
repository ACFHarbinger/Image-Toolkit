"""Neural-network and other machine-learning model adapters."""

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable
from .matting import MattingAdapter

__all__ = ["MattingAdapter", "ModelAdapter", "ModelProposal", "ModelSpec", "ModelUnavailable"]
