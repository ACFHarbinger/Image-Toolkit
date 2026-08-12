"""Model adapters for machine learning and deep learning tools."""

from .base import ModelAdapter, ModelProposal, ModelSpec, ModelUnavailable
from .deblur import DeblurAdapter, DeblurModel
from .inpainting import InpaintingAdapter, InpaintingModel
from .matting import MattingAdapter, MattingModel
from .superres import SuperResolutionAdapter, SuperResModel
from .watermark import WatermarkModel, WatermarkRemovalAdapter

__all__ = [
    "DeblurAdapter",
    "DeblurModel",
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
    "WatermarkModel",
    "WatermarkRemovalAdapter",
]
