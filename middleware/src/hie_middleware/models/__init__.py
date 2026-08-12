"""Neural-network and other machine-learning model adapters."""

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable
from .deblur import DeblurAdapter
from .matting import MattingAdapter
from .superres import SuperResolutionAdapter
from .watermark import WatermarkRemovalAdapter

__all__ = [
    "DeblurAdapter",
    "MattingAdapter",
    "ModelAdapter",
    "ModelProposal",
    "ModelSpec",
    "ModelUnavailable",
    "SuperResolutionAdapter",
    "WatermarkRemovalAdapter",
]
