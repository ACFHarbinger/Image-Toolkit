"""``CodecSubTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Optional, Set

from ....classes import AbstractClassTwoGalleries
from ....helpers import CodecConversionWorker, CodecScanWorker
from ._codec_config import _ConfigMixin
from ._codec_conversion_worker import _ConversionWorkerMixin
from ._codec_directory_browse import _DirectoryBrowseMixin
from ._codec_filters import _CodecFiltersMixin
from ._codec_preview_context import _PreviewContextMixin
from ._codec_probe import _CodecProbeMixin
from ._codec_ui_builder import CodecUIBuilder
from ._gallery_cards import _GalleryCardsMixin
from ._lifecycle import _LifecycleMixin


class CodecSubTab(
    # Mixins MUST precede AbstractClassTwoGalleries in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (_navigate_to_dir, cancel_loading,
    # closeEvent, create_card_widget, on_selection_changed, update_card_pixmap)
    # override same-named methods AbstractClassTwoGalleries itself defines.
    CodecUIBuilder,
    _CodecFiltersMixin,
    _GalleryCardsMixin,
    _PreviewContextMixin,
    _DirectoryBrowseMixin,
    _CodecProbeMixin,
    _ConversionWorkerMixin,
    _ConfigMixin,
    _LifecycleMixin,
    AbstractClassTwoGalleries,
):
    """Convert tab subtab for re-encoding a video's video and/or audio stream
    to a different codec (e.g. HEVC -> AV1) while keeping the container.
    """

    def __init__(self):
        super().__init__()
        self.worker: Optional[CodecConversionWorker] = None
        self._codec_scan_worker: Optional[CodecScanWorker] = None
        self._codec_probe_results: dict = {}
        self.selected_video_codecs: Set[str] = set()
        self.selected_audio_codecs: Set[str] = set()

        self._build_ui()


__all__ = ["CodecSubTab"]
