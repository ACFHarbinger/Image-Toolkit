"""Image toolkit core image processing operations

  _models.py             -- AI model availability probes + lazy loaders
  _engines.py            -- OpenCV/Hugin/Overmix/sequential panorama engines
  _legacy_compositing.py -- unused advanced compositing helpers (preserved)
  _gif_video.py          -- GIF creation + scrolling-video export
  image_merger.py        -- ImageMerger, composed from all mixins above
  image_converter.py     -- image format conversion (H264, etc)

Horizontal/Vertical/Grid methods use the C++ Backend (``base`` extension).
"""

from .image_converter import ImageFormatConverter as ImageFormatConverter
from .image_merger import MERGE_DIR_IMAGES_PREFIX, MERGE_IMAGES_PREFIX, ImageMerger

__all__ = [
    "ImageFormatConverter",
    "ImageMerger",
    "MERGE_IMAGES_PREFIX",
    "MERGE_DIR_IMAGES_PREFIX",
]
