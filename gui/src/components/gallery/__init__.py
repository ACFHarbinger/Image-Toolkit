"""Gallery presentation components and models.

Includes the virtualized (QListView + QAbstractItemModel) gallery — GUI/UX
§2.1 Option A: a model/view gallery where Qt's viewport culling keeps the
widget/paint cost constant regardless of item count, replacing the
bounded-page QLabel-grid card surface. Formerly its own
``components/virtual_gallery`` package, merged in here since both packages
serve the same "gallery" concern.
"""

from .delegate import VirtualGalleryDelegate as VirtualGalleryDelegate
from .dual_widget import VirtualDualGallery as VirtualDualGallery
from .presentation_mode import (
    RATING_COLORS,
    GalleryOverlayConfig,
    GalleryPresentationMode,
)
from .virtual_gallery_model import VirtualGalleryModel as VirtualGalleryModel
from .virtual_gallery_view import VirtualGalleryView as VirtualGalleryView
from .widget import VirtualGallery as VirtualGallery

__all__ = [
    "GalleryOverlayConfig",
    "GalleryPresentationMode",
    "RATING_COLORS",
    "VirtualGalleryModel",
    "VirtualGalleryView",
    "VirtualGallery",
    "VirtualDualGallery",
    "VirtualGalleryDelegate",
]
