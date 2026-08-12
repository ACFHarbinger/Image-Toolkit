"""Model adapters for machine learning and deep learning tools."""

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable
from .deblur import DeblurAdapter
from .inpainting import InpaintingAdapter, InpaintingModel
from .matting import MattingAdapter, MattingModel
from .superres import SuperResolutionAdapter, SuperResModel
from .watermark import WatermarkRemovalAdapter

__all__ = [
    "DeblurAdapter",
    "InpaintingAdapter",
    "InpaintingModel",
    "MattingAdapter",
    "MattingModel",
    "ModelAdapter",
    "ModelProposal",
    "ModelSpec",
    "ModelUnavailable",
    "SuperResolutionAdapter",
    "SuperResModel",
    "WatermarkRemovalAdapter",
]
