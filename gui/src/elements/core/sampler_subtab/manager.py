"""``SamplerSubTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from ....classes import AbstractClassTwoGalleries
from ._config import _ConfigMixin
from ._directory_browse import _DirectoryBrowseMixin
from ._gallery_cards import _GalleryCardsMixin
from ._lifecycle import _LifecycleMixin
from ._preview_context import _PreviewContextMixin
from ._resample_worker import _ResampleWorkerMixin
from ._scale_mode import _ScaleModeMixin
from ._ui_builder import _UIBuilderMixin


class SamplerSubTab(
    # Mixins MUST precede AbstractClassTwoGalleries in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (cancel_loading, closeEvent,
    # create_card_widget, on_selection_changed, update_card_pixmap) override
    # same-named methods AbstractClassTwoGalleries itself defines.
    _UIBuilderMixin,
    _ScaleModeMixin,
    _DirectoryBrowseMixin,
    _GalleryCardsMixin,
    _PreviewContextMixin,
    _ResampleWorkerMixin,
    _ConfigMixin,
    _LifecycleMixin,
    AbstractClassTwoGalleries,
):
    """Upsample / downsample images, GIFs, and videos."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self._build_ui()


__all__ = ["SamplerSubTab"]
