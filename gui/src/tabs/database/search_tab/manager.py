"""``SearchTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Signal

from gui.src.helpers import SearchWorker

from ....classes import AbstractClassTwoGalleries
from ._config import _ConfigMixin
from ._file_actions import _FileActionsMixin
from ._format_filters import _FormatFiltersMixin
from ._gallery_cards import _GalleryCardsMixin
from ._group_filters import _GroupFiltersMixin
from ._lifecycle import _LifecycleMixin
from ._qml_wrappers import _QmlWrappersMixin
from ._search_worker import _SearchWorkerMixin
from ._semantic_search import _SemanticSearchMixin
from ._tab_communication import _TabCommunicationMixin
from ._tag_filters import _TagFiltersMixin
from ._ui_builder import _UIBuilderMixin


class SearchTab(
    # Mixins MUST precede AbstractClassTwoGalleries in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (_update_found_card_styles,
    # cancel_loading, closeEvent, create_card_widget, get_default_config,
    # on_selection_changed, set_config, update_card_pixmap) override
    # same-named methods AbstractClassTwoGalleries itself defines.
    _UIBuilderMixin,
    _GalleryCardsMixin,
    _SearchWorkerMixin,
    _SemanticSearchMixin,
    _QmlWrappersMixin,
    _FormatFiltersMixin,
    _TagFiltersMixin,
    _GroupFiltersMixin,
    _TabCommunicationMixin,
    _FileActionsMixin,
    _ConfigMixin,
    _LifecycleMixin,
    AbstractClassTwoGalleries,
):
    # Signal to send image to another tab: (target_tab_name, image_path)
    send_to_tab_signal = Signal(str, str)

    def __init__(self, db_tab_ref, dropdown=True):
        # Initialize Base Class (Two Galleries)
        super().__init__()

        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown

        self.open_preview_windows = []
        self.selected_formats = None
        self._db_was_connected = False

        # Search specific worker
        self.current_search_worker: Optional[SearchWorker] = None
        # Tag cache (populated on DB connect)
        self._all_tags_cache: List[Dict] = []

        self._build_ui()


__all__ = ["SearchTab"]
