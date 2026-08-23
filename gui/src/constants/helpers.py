"""Constants relocated from backend/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

import re
from typing import Dict, Tuple

from backend.src.constants import IMAGE_TOOLKIT_DIR

# --- from gui/src/helpers/video/storyboard.py ---
_OUT_TIME_RE = re.compile('out_time_ms=(\\d+)')
_STORYBOARD_CACHE_VERSION = 'v2'
_STORYBOARD_DIR = IMAGE_TOOLKIT_DIR / 'storyboard-cache'
TILE_WIDTH = 128
MIN_INTERVAL_MS = 100
MAX_TOTAL_TILES = 50000
MIN_TILES = 4
_MAX_PAGE_RAW_MB = 96

# --- from gui/src/helpers/image/batch_image_loader_worker.py ---
_NATIVE_SUPPORTS_RGB_CACHE = True

# --- from gui/src/helpers/image/card_thumb_worker.py ---
_INFLIGHT_PATHS: set[str] = set()

# --- from gui/src/helpers/core/sampler_worker.py ---
_PILLOW_FILTERS = {'lanczos': None, 'bicubic': None, 'bilinear': None, 'nearest': None}

# --- from gui/src/helpers/animation/annotation_canvas.py ---
_FLAW_COLORS: Dict[str, Tuple[int, int, int, int]] = {'seam': (255, 60, 60, 90), 'blur': (255, 220, 40, 90), 'misalignment': (255, 140, 40, 90), 'color_mismatch': (180, 60, 255, 90), 'dark_border': (120, 120, 120, 90), 'compression': (40, 220, 220, 90), 'ghosting': (60, 80, 255, 90), 'unknown': (200, 200, 200, 90)}
