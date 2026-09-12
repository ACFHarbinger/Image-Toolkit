"""``FormatSubTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from PySide6.QtCore import Signal

from ....classes import AbstractClassTwoGalleries
from ._format_aspect_ratio import _AspectRatioMixin
from ._format_buttons import _FormatButtonsMixin
from ._format_config import _ConfigMixin
from ._format_conversion_worker import _ConversionWorkerMixin
from ._format_directory_browse import _DirectoryBrowseMixin
from ._format_preview_context import _PreviewContextMixin
from ._format_qml_handlers import _QmlHandlersMixin
from ._format_ui_builder import _UIBuilderMixin
from ._gallery_cards import _GalleryCardsMixin
from ._lifecycle import _LifecycleMixin


class FormatSubTab(
    # Mixins MUST precede AbstractClassTwoGalleries in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (_navigate_to_dir, cancel_loading,
    # closeEvent, create_card_widget, on_selection_changed, update_card_pixmap)
    # override same-named methods AbstractClassTwoGalleries itself defines.
    _UIBuilderMixin,
    _FormatButtonsMixin,
    _GalleryCardsMixin,
    _PreviewContextMixin,
    _DirectoryBrowseMixin,
    _AspectRatioMixin,
    _ConversionWorkerMixin,
    _ConfigMixin,
    _LifecycleMixin,
    _QmlHandlersMixin,
    AbstractClassTwoGalleries,
):
    qml_input_path_changed = Signal(str)

    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None
        self._build_ui()


__all__ = ["FormatSubTab"]
