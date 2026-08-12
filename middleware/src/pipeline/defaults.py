"""Standard dependency-light registry used by standalone HIE frontends."""

from .orchestrator import ProposalPipeline
from ..models import (
    DeblurAdapter,
    InpaintingAdapter,
    MattingAdapter,
    SuperResolutionAdapter,
    WatermarkRemovalAdapter,
)
from ..policies import BrushAssistantPolicy, CropCompositionPolicy, GlobalTonePolicy


def build_default_pipeline() -> ProposalPipeline:
    """Build the Phase 1 capability registry without downloading model weights."""
    pipeline = ProposalPipeline()
    pipeline.register_policy("brush-assistant", BrushAssistantPolicy())
    pipeline.register_policy("global-tone", GlobalTonePolicy())
    pipeline.register_policy("crop-composition", CropCompositionPolicy())
    pipeline.register_model("alpha-matting", MattingAdapter())
    pipeline.register_model("image-deblur", DeblurAdapter())
    pipeline.register_model("neural-inpainting", InpaintingAdapter())
    pipeline.register_model("super-resolution", SuperResolutionAdapter())
    pipeline.register_model("watermark-inpainting", WatermarkRemovalAdapter())
    return pipeline
