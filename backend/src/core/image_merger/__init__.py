"""Image merging/stitching (§5.17 split, by concern).

  _models.py             -- AI model availability probes + lazy loaders
  _engines.py             -- OpenCV/Hugin/Overmix/sequential panorama engines
  _legacy_compositing.py -- unused advanced compositing helpers (preserved)
  _gif_video.py           -- GIF creation + scrolling-video export
  manager.py              -- ImageMerger, composed from all mixins above

Horizontal/Vertical/Grid methods use the C++ Backend (``base`` extension).
"""

from .manager import MERGE_DIR_IMAGES_PREFIX, MERGE_IMAGES_PREFIX, ImageMerger

__all__ = ["ImageMerger", "MERGE_IMAGES_PREFIX", "MERGE_DIR_IMAGES_PREFIX"]
