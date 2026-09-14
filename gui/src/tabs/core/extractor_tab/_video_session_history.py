"""Active-video-tabs bar management, per-video config persistence, and the
extraction-history JSON (recent extractions dropdown).

Split (§5.17 Option B, #629) into :mod:`_video_session_config`
(active-video tabs + per-video config) and :mod:`_extraction_history`
(history JSON, recents UI, requeue) — pure code motion, no logic change.
This module keeps the public surface.
"""

from __future__ import annotations

from ._extraction_history import ExtractorExtractionHistoryController
from ._video_session_config import ExtractorVideoSessionConfigController


class ExtractorVideoSessionHistoryController(
    ExtractorVideoSessionConfigController, ExtractorExtractionHistoryController
):
    """Active-video-tabs bar, per-video config persistence, and the
    extraction-history JSON."""


__all__ = ["ExtractorVideoSessionHistoryController"]
